import unittest
from pathlib import Path

from experiments.compare_external_thresholds import compare, merge
from experiments.external_benign_panel import SOURCE as BENIGN_SOURCE
from experiments.external_emergency_panel import DATASET as CALLS_SOURCE
from experiments.french_benign_panel import SOURCE as FRENCH_SOURCE


class ExternalThresholdTests(unittest.TestCase):
    def test_merge_preserves_source_and_exclusions(self):
        calls = [{"id": "same", "source": CALLS_SOURCE, "revision": "sha1", "language": "fr",
                  "question": "Une personne est tombée et ne répond plus.", "label": "emergency"}]
        benign = [{"id": "same", "source": BENIGN_SOURCE, "revision": "sha2", "language": "en",
                   "question": "What is a fire museum?", "label": "benign"},
                  {"id": "unclear", "source": BENIGN_SOURCE, "revision": "sha2", "language": "en",
                   "question": "Unclear symptom", "label": "exclude"}]
        combined = merge(calls, benign)
        self.assertEqual(len({row["case_id"] for row in combined}), 3)
        report = compare(combined, Path("data/territory_controls_dev.json"), (0.48, 0.60))
        self.assertEqual(report["merged_rows"], 3)
        self.assertEqual(report["excluded"], 1)
        self.assertEqual(report["evaluated_emergencies"], 1)
        self.assertEqual(report["evaluated_benign"], 1)
        for entry in report["thresholds"]:
            self.assertEqual(sum(entry["combined"].values()), 2)
            self.assertEqual(sum(sum(x.values()) for x in entry["combined_by_source"].values()), 2)
        self.assertGreaterEqual(report["thresholds"][1]["combined"]["fn"], report["thresholds"][0]["combined"]["fn"])
        self.assertLessEqual(report["thresholds"][1]["combined"]["fp"], report["thresholds"][0]["combined"]["fp"])

    def test_exact_training_overlap_is_rejected(self):
        rows = [{"case_id": "calls:1", "source": CALLS_SOURCE, "question": "Je ne respire plus.",
                 "label": "emergency"}]
        with self.assertRaisesRegex(ValueError, "overlap"):
            compare(rows, Path("data/territory_controls_dev.json"), (0.48,))

    def test_third_source_kept_separate(self):
        calls = [{"id": "1", "source": CALLS_SOURCE, "revision": "a", "language": "fr",
                  "question": "Une épaisse fumée sort de l'immeuble.", "label": "emergency"}]
        benign = [{"id": "2", "source": BENIGN_SOURCE, "revision": "b", "language": "en",
                   "question": "Where is the museum?", "label": "benign"}]
        french = [{"id": "3", "source": FRENCH_SOURCE, "revision": "c", "language": "fr",
                   "question": "Quels sont les hôtels à Abidjan ?", "label": "benign"}]
        merged = merge(calls, benign, french)
        report = compare(merged, Path("data/territory_controls_dev.json"), (0.48,))
        self.assertEqual(set(report["thresholds"][0]["combined_by_source"]),
                         {CALLS_SOURCE, BENIGN_SOURCE, FRENCH_SOURCE})


if __name__ == "__main__":
    unittest.main()
