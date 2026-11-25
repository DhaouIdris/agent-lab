"""Prepare local French domain questions as a provisional benign review panel."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

SOURCE = "agent-lab/french-domain-development"
SOURCES = {
    "data/natural_user_pilot_24.json": None,
    "data/natural_user_expansion_36_v2.json": None,
    "data/natural_nearby_8.json": {"G01", "G02", "G03", "G04", "G05", "G07", "G08"},
    "data/named_origin_shortlist_4.json": None,
    "data/holdout_response_followup_5.json": None,
}
EXPECTED = 56


def prepare(root=Path(".")):
    digest = hashlib.sha256()
    rows = []
    for filename, selected in SOURCES.items():
        raw = (root / filename).read_bytes()
        digest.update(filename.encode("utf-8") + b"\0" + raw)
        cases = json.loads(raw.decode("utf-8-sig"))
        for case in cases:
            identifier = case["id"]
            if selected is not None and identifier not in selected:
                continue
            if filename.endswith(("natural_user_pilot_24.json", "natural_user_expansion_36_v2.json")):
                if identifier.split("-", 1)[-1][0] not in ("C", "D", "A", "L"):
                    continue
            rows.append({"id": f"{Path(filename).stem}:{identifier}", "source": SOURCE,
                         "revision": "", "language": "fr", "question": case["question"],
                         "label": "benign", "review_priority": "normal",
                         "review_note": "Provisional domain question: verify no current emergency"})
    if len(rows) != EXPECTED or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("French panel selection changed; review its manifest")
    for row in rows:
        row["revision"] = digest.hexdigest()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"Refusing to overwrite existing review CSV: {args.out}")
    rows = prepare()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} provisional French domain labels; review in {args.out}")


if __name__ == "__main__":
    main()
