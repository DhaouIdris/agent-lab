"""Prepare a public emergency-call panel for human labels, then score a frozen guard.

Reads only the dataset's metadata.csv. No audio, provider calls, or model weights.
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

DATASET = "SoumiaDermouche/multilingual-emergency-calls"
METADATA_NAME = "metadata.csv"


def metadata_path(repo_files):
    matches = [path for path in repo_files if path.rsplit("/", 1)[-1] == METADATA_NAME]
    if len(matches) != 1:
        raise ValueError(f"Expected one {METADATA_NAME} in dataset repository, found {len(matches)}")
    return matches[0]


def first_caller_turn(transcript):
    if not isinstance(transcript, str):
        raise ValueError("Missing transcript")
    match = re.search(r"\bCaller:\s*(.*?)(?=\s*\b(?:Operator|Caller):|\Z)",
                      transcript, re.IGNORECASE | re.DOTALL)
    if not match or not match.group(1).strip():
        raise ValueError("No first caller turn; inspect source format")
    return " ".join(match.group(1).split())


def prepare(rows, revision):
    result = []
    seen = set()
    for row in rows:
        source_id = str(row["call_id"])
        if source_id in seen:
            raise ValueError("Duplicate call_id")
        seen.add(source_id)
        result.append({"id": source_id, "source": DATASET, "revision": revision,
                       "language": row["language"],
                       "question": first_caller_turn(row["translation"]),
                       "label": "pending", "review_note": ""})
    return sorted(result, key=lambda x: x["id"])


def load_metadata(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"call_id", "language", "translation"} <= set(reader.fieldnames):
            raise ValueError("Metadata CSV missing call_id, language, or translation")
        return list(reader)


def read_review(path, expected_source=DATASET):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not all(set(("id", "source", "revision", "language", "question", "label")) <= row.keys() for row in rows):
        raise ValueError("Invalid or empty review CSV")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate IDs")
    if any(row["label"] not in ("emergency", "benign", "exclude") for row in rows):
        raise ValueError("Review every row: emergency, benign, or exclude")
    if (any(row["source"] != expected_source or not row["revision"] or not row["question"].strip() for row in rows)
            or len({row["revision"] for row in rows}) != 1):
        raise ValueError("Missing source, revision, or text")
    return rows


def score(rows, train_path, source=DATASET, expected_cases=77):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from experiments.eval_semantic_emergency import SEMANTIC_THRESHOLD
    from experiments.request_controls import check_emergency_intent

    train = json.loads(Path(train_path).read_text(encoding="utf-8"))
    evaluated = [row for row in rows if row["label"] != "exclude"]
    if not evaluated:
        raise ValueError("Review must contain evaluated cases")
    model = make_pipeline(TfidfVectorizer(analyzer="char", ngram_range=(2, 5)),
                          LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42))
    model.fit([x["question"] for x in train], [x["label"] == "emergency" for x in train])
    scores = model.predict_proba([x["question"] for x in evaluated])[:, list(model.classes_).index(True)]
    results = []
    for row, probability in zip(evaluated, scores):
        lexical = bool(check_emergency_intent(row["question"]))
        semantic = bool(probability >= SEMANTIC_THRESHOLD)
        results.append({"id": row["id"], "language": row["language"], "label": row["label"],
                        "lexical": lexical, "semantic": semantic, "combined": lexical or semantic})
    metrics = {}
    for method in ("lexical", "semantic", "combined"):
        metrics[method] = {
            "tp": sum(x["label"] == "emergency" and x[method] for x in results),
            "fn": sum(x["label"] == "emergency" and not x[method] for x in results),
            "fp": sum(x["label"] == "benign" and x[method] for x in results),
            "tn": sum(x["label"] == "benign" and not x[method] for x in results),
        }
    return {"kind": "human_reviewed_external_emergency_cases", "source": source,
            "revision": evaluated[0]["revision"], "threshold": SEMANTIC_THRESHOLD,
            "source_expected_cases": expected_cases, "reviewed_rows": len(rows),
            "campaign_complete": len(rows) == expected_cases,
            "excluded": len(rows) - len(evaluated), "evaluated_emergencies": sum(x["label"] == "emergency" for x in evaluated),
            "evaluated_benign": sum(x["label"] == "benign" for x in evaluated),
            "metrics": metrics, "results": results,
            "caveat": "Source distribution differs from Côte d'Ivoire assistant queries; labels require human review; this does not establish operational safety."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--out", type=Path, required=True)
    score_parser = sub.add_parser("score")
    score_parser.add_argument("--review", type=Path, required=True)
    score_parser.add_argument("--out", type=Path, required=True)
    score_parser.add_argument("--train", type=Path, default=Path("data/territory_controls_dev.json"))
    args = parser.parse_args()
    if args.command == "prepare":
        try:
            from huggingface_hub import HfApi, hf_hub_download
        except ImportError as exc:
            raise SystemExit("Install optional dependency: python -m pip install huggingface_hub") from exc
        api = HfApi()
        revision = api.dataset_info(DATASET).sha
        filename = metadata_path(api.list_repo_files(DATASET, repo_type="dataset", revision=revision))
        metadata = hf_hub_download(repo_id=DATASET, repo_type="dataset", filename=filename,
                                   revision=revision)
        rows = prepare(load_metadata(metadata), revision)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"{len(rows)} rows; review labels in {args.out}")
    else:
        rows = read_review(args.review)
        report = score(rows, args.train)
        report["review_sha256"] = hashlib.sha256(args.review.read_bytes()).hexdigest()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report["metrics"], ensure_ascii=False))
        print(args.out)


if __name__ == "__main__":
    main()
