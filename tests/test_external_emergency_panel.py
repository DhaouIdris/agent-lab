import csv
import tempfile
import unittest
from pathlib import Path

from experiments.external_emergency_panel import first_caller_turn, load_metadata, metadata_path, prepare, read_review, score


class ExternalEmergencyPanelTests(unittest.TestCase):
    def test_metadata_discovery_in_subdirectory(self):
        self.assertEqual(metadata_path(["README.md", "test/metadata.csv", "test/audio/1.mp3"]), "test/metadata.csv")
        with self.assertRaises(ValueError):
            metadata_path(["metadata.csv", "test/metadata.csv"])

    def test_prepare_extracts_first_caller_turn_only(self):
        rows = prepare([{"call_id": "anglais_1.1", "language": "en",
                         "translation": "Operator: Bonjour\nCaller: Il y a un blessé.\nOperator: Où ?\nCaller: À la gare."}], "fixed-sha")
        self.assertEqual(rows[0]["question"], "Il y a un blessé.")
        self.assertEqual(rows[0]["label"], "pending")

    def test_inline_transcript_and_metadata_without_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["call_id", "language", "translation", "file_name"])
                writer.writeheader()
                writer.writerow({"call_id": "anglais_1.1", "language": "en", "file_name": "audio.mp3",
                                 "translation": "Operator: Bonjour. Caller: Un feu se propage. Operator: Où ? Caller: Chez moi."})
            rows = prepare(load_metadata(path), "fixed-sha")
            self.assertEqual(rows[0]["question"], "Un feu se propage.")

    def test_labels_must_be_reviewed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id", "source", "revision", "language", "question", "label"])
                writer.writeheader()
                writer.writerow({"id": "1", "source": "SoumiaDermouche/multilingual-emergency-calls",
                                 "revision": "abc", "language": "fr", "question": "Au secours", "label": "pending"})
            with self.assertRaises(ValueError):
                read_review(path)

    def test_scoring_uses_frozen_threshold_and_excludes_reviewed_rows(self):
        rows = [{"id": "e", "language": "fr", "label": "emergency", "question": "Je ne respire plus.", "revision": "abc"},
                {"id": "b", "language": "fr", "label": "benign", "question": "Quels sont les horaires du musée ?", "revision": "abc"},
                {"id": "x", "language": "fr", "label": "exclude", "question": "Inconnu", "revision": "abc"}]
        report = score(rows, Path("data/territory_controls_dev.json"))
        self.assertEqual(report["threshold"], 0.48)
        self.assertEqual(report["excluded"], 1)
        self.assertEqual(len(report["results"]), 2)
        self.assertEqual(report["reviewed_rows"], 3)
        self.assertFalse(report["campaign_complete"])


if __name__ == "__main__":
    unittest.main()
