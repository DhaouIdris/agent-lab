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
        rows.append({"id": identifier, "source": SOURCE, "revision": revision,
                     "language": "en", "question": question, "label": "pending", "review_note": ""})
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
    args = parser.parse_args()
    if args.command == "prepare":
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
        print(f"{len(rows)} candidate questions; review all labels in {args.out}")
    else:
        rows = read_review(args.review, expected_source=SOURCE)
        report = score(rows, Path("data/territory_controls_dev.json"), source=SOURCE, expected_cases=50)
        report["review_sha256"] = hashlib.sha256(args.review.read_bytes()).hexdigest()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report["metrics"], ensure_ascii=False))
        print(args.out)


if __name__ == "__main__":
    main()
