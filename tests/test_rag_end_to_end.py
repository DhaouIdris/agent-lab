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

    def test_missing_requirements_are_explicitly_disallowed_in_prompt(self):
        docs=load_corpus('data/rag_corpus_licensed_pilot.json');client=Mock()
        client.chat.return_value={'content':json.dumps({'answer':'Je ne sais pas.','abstain':True,'citation_ids':[]})}
        from experiments.document_rag import retrieve,generate
        generate(client,'Quels documents pour une SARL au CEPICI ?',retrieve('SARL CEPICI',docs))
        prompt=client.chat.call_args.args[0][0]['content']
        self.assertIn('do not suggest specific examples of required documents',prompt)

    def test_licensed_pilot_cases_refer_to_corpus(self):
        docs=load_corpus('data/rag_corpus_licensed_pilot.json')
        cases=json.loads(Path('data/rag_licensed_pilot_cases.json').read_text(encoding='utf8'))
        self.assertEqual(len(docs),13)
        self.assertTrue(all(set(c['relevant_ids']) <= {d['id'] for d in docs} for c in cases))
        self.assertEqual(sum(c['expected_behavior']=='abstain' for c in cases),1)

    def test_comprehensive_case_set_is_bounded_and_has_known_ids(self):
        docs=load_corpus('data/rag_corpus_licensed_pilot.json')
        cases=json.loads(Path('data/rag_comprehensive_dev.json').read_text(encoding='utf8'))
        self.assertEqual(len(cases),20)
        self.assertEqual(len({c['id'] for c in cases}),len(cases))
        self.assertTrue(all(set(c['relevant_ids']) <= {d['id'] for d in docs} for c in cases))
        self.assertEqual(sum(c['expected_behavior']=='answer' for c in cases),10)
