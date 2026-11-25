import csv
import tempfile
import unittest
from pathlib import Path

from experiments.external_benign_panel import SOURCE, prepare
from experiments.external_emergency_panel import read_review, score


class ExternalBenignPanelTests(unittest.TestCase):
    def test_import_requires_review_and_pins_bytes(self):
        raw = b'id,query\n1,"What does emergency mean?"\n2,"Can I find a museum?"\n'
        rows = prepare(raw)
        self.assertEqual(len(rows), 2)
        self.assertEqual({row['label'] for row in rows}, {'pending'})
        self.assertEqual(rows[0]['source'], SOURCE)
        self.assertEqual(len(rows[0]['revision']), 64)

    def test_all_benign_review_has_metrics(self):
        rows = prepare(b'id,query\n1,"What does emergency mean?"\n2,"Can I find a museum?"\n')
        for row in rows:
            row['label'] = 'benign'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'review.csv'
            with path.open('w', encoding='utf-8-sig', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            checked = read_review(path, expected_source=SOURCE)
            report = score(checked, Path('data/territory_controls_dev.json'), source=SOURCE, expected_cases=50)
            self.assertEqual(report['evaluated_benign'], 2)
            self.assertEqual(report['evaluated_emergencies'], 0)
            self.assertFalse(report['campaign_complete'])
            self.assertEqual(report['metrics']['combined']['fp'] + report['metrics']['combined']['tn'], 2)


if __name__ == '__main__':
    unittest.main()
