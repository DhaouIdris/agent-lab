"""Prepare and score a separate, human-reviewed health-adjacent benign panel.

The external source text stays in a private local CSV; reports contain only IDs.
"""
import argparse
import csv
import hashlib
import io
import json
import urllib.request
from pathlib import Path

from experiments.external_emergency_panel import read_review, score

SOURCE = "weathon/over-alignment"
SOURCE_URL = ("https://raw.githubusercontent.com/weathon/over-alignment/main/data/"
              "019ddda9-c0ce-762e-8f41-e1a0c655cc7e_sampled_questions_only.csv")

# Cases with current symptoms or exposures whose urgency cannot be inferred safely
# from the short text alone. These IDs are review priorities, not ground truth.
UNCERTAIN_IDS = {
    "019ddda5-87c4-75dc-865b-5ba9f1b890be",  # feared stroke with lightheadedness
    "019ddda5-88a2-737e-9eec-315cd297ad25",  # current chest pain
    "019ddda5-90df-73f3-81fa-00d40a03362c",  # possible current low sodium
    "019ddda5-9649-7518-8913-d1bc7ceb0315",  # dizziness and CO concern
    "019ddda5-a075-7179-9ef2-1cb62480cc1e",  # possible CO exposure
    "019ddda5-ae30-746c-8017-253b5d07a709",  # low oxygen reading
    "019ddda5-ae76-70a2-b372-4ea8ae79c8c5",  # transient low oxygen reading
    "019ddda5-b1bf-732e-8e93-2ab03d49d820",  # jaw/neck symptom
    "019ddda5-b260-73bd-b815-24d68f1725a6",  # unknown odor exposure
}


def prepare(raw):
    revision = hashlib.sha256(raw).hexdigest()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not reader.fieldnames or not {"id", "query"} <= set(reader.fieldnames):
        raise ValueError("Upstream CSV must have id and query columns")
    rows = []
    seen = set()
    for original in reader:
        identifier = original["id"].strip()
        question = original["query"].strip()
        if not identifier or not question or identifier in seen:
            raise ValueError("Blank or duplicate source row")
        seen.add(identifier)
        uncertain = identifier in UNCERTAIN_IDS
        rows.append({"id": identifier, "source": SOURCE, "revision": revision,
                     "language": "en", "question": question,
                     "label": "exclude" if uncertain else "benign",
                     "review_priority": "high" if uncertain else "normal",
                     "review_note": "Provisional: inspect symptoms and context" if uncertain else "Provisional: verify no current emergency"})
    if not rows:
        raise ValueError("Empty source CSV")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--out", type=Path, required=True)
    evaluation = sub.add_parser("score")
    evaluation.add_argument("--review", type=Path, required=True)
    evaluation.add_argument("--out", type=Path, required=True)
    evaluation.add_argument("--confirmed", action="store_true", help="Assert that every row was reviewed and corrected")
    args = parser.parse_args()
    if args.command == "prepare":
        if args.out.exists():
            raise SystemExit(f"Refusing to overwrite existing review file: {args.out}")
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Source CSV exceeds size limit")
        rows = prepare(raw)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"{len(rows)} provisional labels ({sum(row['review_priority']=='high' for row in rows)} high priority); review in {args.out}")
    else:
        rows = read_review(args.review, expected_source=SOURCE)
        report = score(rows, Path("data/territory_controls_dev.json"), source=SOURCE, expected_cases=50)
        report["labels_confirmed_by_reviewer"] = args.confirmed
        report["kind"] = "human_reviewed_external_emergency_cases" if args.confirmed else "provisional_external_label_comparison"
        if not args.confirmed:
            report["caveat"] += " Labels remain provisional; metrics do not measure real accuracy until every row has been reviewed."
        report["review_sha256"] = hashlib.sha256(args.review.read_bytes()).hexdigest()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report["metrics"], ensure_ascii=False))
        print(args.out)


if __name__ == "__main__":
    main()
