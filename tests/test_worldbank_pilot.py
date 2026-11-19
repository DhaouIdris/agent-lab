import json
import unittest
from pathlib import Path
from experiments.document_rag import load_corpus

class WorldBankPilotTests(unittest.TestCase):
    def test_data_has_year_unit_license_and_known_ids(self):
        docs=load_corpus('data/rag_worldbank_pilot.json')
        cases=json.loads(Path('data/rag_worldbank_pilot_cases.json').read_text(encoding='utf8'))
        self.assertIn('2025',docs[0]['text'])
        self.assertIn('dollars américains courants',docs[0]['text'])
        self.assertIn('CC BY 4.0',docs[0]['license_note'])
        self.assertTrue(all(set(c['relevant_ids'])<={d['id'] for d in docs} for c in cases))
