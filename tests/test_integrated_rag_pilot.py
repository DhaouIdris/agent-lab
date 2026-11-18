import json
import unittest
from pathlib import Path
from experiments.document_rag import load_corpus, retrieve

class IntegratedPilotTests(unittest.TestCase):
    def test_cases_and_corpus_consistency(self):
        docs=load_corpus('data/rag_integrated_dev.json')
        cases=json.loads(Path('data/rag_integrated_dev_cases.json').read_text(encoding='utf8'))
        ids={d['id'] for d in docs}
        self.assertEqual((len(docs),len(cases)),(12,16))
        self.assertEqual(len({c['id'] for c in cases}),len(cases))
        for case in cases:
            self.assertTrue(set(case['relevant_ids'])<=ids)
            self.assertEqual(case['expected_behavior']=='answer',bool(case['relevant_ids']))
            if case['relevant_ids']:
                self.assertTrue(set(case['relevant_ids']) & {d['id'] for d in retrieve(case['question'],docs)})
