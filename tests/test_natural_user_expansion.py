"""Check the new natural panel against the evidence corpus and local boundaries."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from experiments.audit_campaign import load_cases


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'data/natural_user_expansion_36.json'


class NaturalUserExpansionTests(unittest.TestCase):
    def test_case_ids_and_document_evidence_exist(self):
        rows = load_cases(CASES, False)
        self.assertEqual(len(rows), 36)
        self.assertEqual(len(load_cases(CASES, True)), 8)
        self.assertEqual(len({row['id'] for row in rows}), len(rows))
        self.assertEqual({row['category'] for row in rows},
                         {'catalogue', 'preuves', 'affaires', 'trajets', 'dialogue', 'securite'})
        corpus = json.loads((ROOT / 'data/rag_integrated_dev.json').read_text(encoding='utf-8'))
        existing = {passage['id'] for passage in corpus}
        for row in rows:
            with self.subTest(case=row['id']):
                self.assertTrue(set(row['evidence_checks'].get('required_document_ids', [])) <= existing)
                self.assertNotIn('2022', row['question'])

    def test_local_cases_do_not_need_model_or_route(self):
        from experiments.audit_campaign import NoChat, evaluate_case, no_route
        from experiments.document_rag import load_corpus

        rows = load_cases(CASES, False)
        expected = {**dict.fromkeys(('E-S01', 'E-S02', 'E-S03'), 'blocked_suspected_injection'),
                    'E-T03': 'invalid_coordinates',
                    **dict.fromkeys(('E-T04', 'E-T05', 'E-T06'), 'unsupported_routing')}
        docs = load_corpus(ROOT / 'data/rag_integrated_dev.json')
        with TemporaryDirectory() as temp:
            db = Path(temp) / 'empty.sqlite'
            db.touch()
            for case in rows:
                if case['id'] not in expected:
                    continue
                with self.subTest(case=case['id']):
                    result = evaluate_case(case, NoChat(), False, db, docs, 5)
                    self.assertEqual(result['status'], expected[case['id']])
                    self.assertTrue(result['automatic_checks_pass'])
                    self.assertFalse(result['provider_calls'])


if __name__ == '__main__':
    unittest.main()
