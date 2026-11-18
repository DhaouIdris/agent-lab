import json
import unittest
from pathlib import Path
from unittest.mock import Mock
from experiments.document_rag import load_corpus
from experiments.document_rag_batch import run_batch
from experiments.prompt_shield import ShieldUnavailable

class EndToEndTests(unittest.TestCase):
    def test_pilot_schema_and_labels(self):
        cases=json.loads(Path('data/rag_end_to_end_dev.json').read_text(encoding='utf8'))
        docs=load_corpus('data/rag_seed_extended.json')
        self.assertEqual(len(cases),18)
        self.assertEqual(sum(c['expected_behavior']=='abstain' for c in cases),9)
        self.assertTrue(all(set(c['relevant_ids'])<={d['id'] for d in docs} for c in cases))

    def test_shield_unavailable_stops_without_model_call(self):
        docs=load_corpus('data/rag_seed_extended.json');client=Mock();client.calls=[]
        shield=Mock();shield.inspect.side_effect=ShieldUnavailable()
        case={'id':'x','question':'Grand Bassam','expected_behavior':'answer','relevant_ids':['CI_UNESCO_BASSAM'],'human_expectation':'review'}
        report=run_batch(client,docs,[case,case],shield=shield)
        self.assertFalse(report['campaign_complete'])
        self.assertEqual(report['summary']['guard_unavailable_runs'],1)
        self.assertIsNone(report['results'][0]['behavior_match'])
        client.chat.assert_not_called()

    def test_shield_block_recorded_separately(self):
        docs=load_corpus('data/rag_seed_extended.json');client=Mock();client.calls=[]
        shield=Mock();shield.inspect.return_value={'user_attack':False,'flagged_source_ids':['CI_UNESCO_BASSAM']}
        case={'id':'x','question':'Grand Bassam','expected_behavior':'answer','relevant_ids':['CI_UNESCO_BASSAM'],'human_expectation':'review'}
        report=run_batch(client,docs,[case],shield=shield)
        self.assertEqual(report['summary']['guard_blocked_runs'],1)
        self.assertIsNone(report['results'][0]['behavior_match'])
        client.chat.assert_not_called()
