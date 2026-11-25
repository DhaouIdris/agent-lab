"""Merge two reviewed CSVs locally and compare fixed emergency thresholds offline."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from experiments.external_benign_panel import SOURCE as BENIGN_SOURCE
from experiments.external_emergency_panel import DATASET as CALLS_SOURCE, read_review
from experiments.french_benign_panel import EXPECTED as FRENCH_EXPECTED, SOURCE as FRENCH_SOURCE
from experiments.request_controls import check_emergency_intent

DEFAULT_THRESHOLDS = (0.40, 0.45, 0.48, 0.50, 0.52, 0.55, 0.60, 0.65)
FIELDS = ("case_id", "source", "revision", "language", "question", "label", "review_priority", "review_note")


def merge(calls, benign, french=None):
    result = []
    groups = (("calls", CALLS_SOURCE, calls), ("benign", BENIGN_SOURCE, benign))
    if french is not None:
        groups += (("french", FRENCH_SOURCE, french),)
    for prefix, source, rows in groups:
        for row in rows:
            if row["source"] != source:
                raise ValueError("Unexpected source in review CSV")
            result.append({"case_id": f"{prefix}:{row['id']}", "source": source,
                           "revision": row["revision"], "language": row["language"],
                           "question": row["question"], "label": row["label"],
                           "review_priority": row.get("review_priority", ""),
                           "review_note": row.get("review_note", "")})
    if len({row["case_id"] for row in result}) != len(result):
        raise ValueError("Duplicate merged case ID")
    return result


def confusion(rows, predictions):
    return {"tp": sum(row["label"] == "emergency" and predicted for row, predicted in zip(rows, predictions)),
            "fn": sum(row["label"] == "emergency" and not predicted for row, predicted in zip(rows, predictions)),
            "fp": sum(row["label"] == "benign" and predicted for row, predicted in zip(rows, predictions)),
            "tn": sum(row["label"] == "benign" and not predicted for row, predicted in zip(rows, predictions))}


def compare(merged, train_path, thresholds=DEFAULT_THRESHOLDS):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    if not thresholds or any(not 0 < t < 1 for t in thresholds):
        raise ValueError("Thresholds must be between 0 and 1")
    train = json.loads(Path(train_path).read_text(encoding="utf-8"))
    rows = [row for row in merged if row["label"] != "exclude"]
    if not rows:
        raise ValueError("No evaluable rows")
    if {x["question"].strip().casefold() for x in train} & {x["question"].strip().casefold() for x in rows}:
        raise ValueError("Exact question overlap with training set")
    model = make_pipeline(TfidfVectorizer(analyzer="char", ngram_range=(2, 5)),
                          LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42))
    model.fit([x["question"] for x in train], [x["label"] == "emergency" for x in train])
    probabilities = model.predict_proba([x["question"] for x in rows])[:, list(model.classes_).index(True)]
    lexical = [bool(check_emergency_intent(x["question"])) for x in rows]
    output = []
    for threshold in thresholds:
        semantic = [bool(p >= threshold) for p in probabilities]
        combined = [s or l for s, l in zip(semantic, lexical)]
        by_source = {}
        for source in sorted({row["source"] for row in merged}):
            positions = [i for i, row in enumerate(rows) if row["source"] == source]
            by_source[source] = confusion([rows[i] for i in positions], [combined[i] for i in positions])
        output.append({"threshold": threshold, "semantic": confusion(rows, semantic),
                       "combined": confusion(rows, combined), "combined_by_source": by_source,
                       "combined_false_negatives": [row["case_id"] for row, p in zip(rows, combined)
                                                    if row["label"] == "emergency" and not p],
                       "combined_false_positives": [row["case_id"] for row, p in zip(rows, combined)
                                                    if row["label"] == "benign" and p]})
    return {"kind": "external_threshold_sweep_exploratory", "training_cases": len(train),
            "merged_rows": len(merged), "evaluated_emergencies": sum(x["label"] == "emergency" for x in rows),
            "evaluated_benign": sum(x["label"] == "benign" for x in rows),
            "excluded": len(merged) - len(rows), "lexical": confusion(rows, lexical),
            "thresholds": output,
            "caveat": "Previously inspected external cases and provisional labels: threshold comparisons are exploratory, not an independent selection or production safety validation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", type=Path, required=True)
    parser.add_argument("--benign", type=Path, required=True)
    parser.add_argument("--french", type=Path, help="Optional French domain benign review CSV")
    parser.add_argument("--merged-csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--train", type=Path, default=Path("data/territory_controls_dev.json"))
    parser.add_argument("--thresholds", type=float, nargs="+", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--labels-reviewed", action="store_true",
                        help="Assert every included label in both input files was human reviewed")
    args = parser.parse_args()
    if args.merged_csv.exists():
        raise SystemExit(f"Refusing to overwrite merged CSV: {args.merged_csv}")
    calls = read_review(args.calls, CALLS_SOURCE)
    benign = read_review(args.benign, BENIGN_SOURCE)
    french = read_review(args.french, FRENCH_SOURCE) if args.french else None
    merged = merge(calls, benign, french)
    report = compare(merged, args.train, args.thresholds)
    report["source_rows"] = {CALLS_SOURCE: len(calls), BENIGN_SOURCE: len(benign)}
    report["source_expected"] = {CALLS_SOURCE: 77, BENIGN_SOURCE: 50}
    if french is not None:
        report["source_rows"][FRENCH_SOURCE] = len(french)
        report["source_expected"][FRENCH_SOURCE] = FRENCH_EXPECTED
    report["campaign_complete"] = all(report["source_rows"][source] == count
                                      for source, count in report["source_expected"].items())
    report["labels_reviewed"] = args.labels_reviewed
    report["input_sha256"] = {"calls": hashlib.sha256(args.calls.read_bytes()).hexdigest(),
                              "benign": hashlib.sha256(args.benign.read_bytes()).hexdigest()}
    if args.french:
        report["input_sha256"]["french"] = hashlib.sha256(args.french.read_bytes()).hexdigest()
    report["training_sha256"] = hashlib.sha256(args.train.read_bytes()).hexdigest()
    if not args.labels_reviewed:
        report["caveat"] += " Input labels have not been confirmed by the reviewer."
    args.merged_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.merged_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(merged)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {len(merged)} rows ({report['evaluated_emergencies']} emergency, "
          f"{report['evaluated_benign']} benign, {report['excluded']} excluded).")
    for result in report["thresholds"]:
        counts = result["combined"]
        print(f"threshold={result['threshold']:.2f} FN={counts['fn']} FP={counts['fp']} "
              f"TP={counts['tp']} TN={counts['tn']}")
    print(f"CSV: {args.merged_csv}\nReport: {args.out}")


if __name__ == "__main__":
    main()
