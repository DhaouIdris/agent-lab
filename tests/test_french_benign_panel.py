import unittest

from experiments.french_benign_panel import EXPECTED, prepare


class FrenchBenignPanelTests(unittest.TestCase):
    def test_selection_is_stable_and_explicitly_provisional(self):
        rows = prepare()
        self.assertEqual(len(rows), EXPECTED)
        self.assertEqual(len({row["id"] for row in rows}), EXPECTED)
        self.assertTrue(all(row["language"] == "fr" and row["label"] == "benign" for row in rows))
        self.assertTrue(all(row["review_note"].startswith("Provisional") for row in rows))
        self.assertEqual(len({row["revision"] for row in rows}), 1)


if __name__ == "__main__":
    unittest.main()
