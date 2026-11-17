import json
import unittest
from unittest.mock import patch
from ci_agentlab.providers import ProviderError
from experiments.document_rag import load_corpus
from experiments.document_rag_batch import run_batch,CASES

class BatchTests(unittest.TestCase):
    def setUp(self):
        self.docs=load_corpus();self.cases=json.loads(CASES.read_text(encoding='utf-8'))

    def test_answer_and_abstention_are_evaluated_separately(self):
        class Fake:
            def __init__(self):self.calls=[]
            def chat(self,messages,**kwargs):
                payload=json.loads(messages[-1]['content'])
                assert 'human_expectation' not in payload and 'expected_behavior' not in payload
                self.calls.append({'usage':{'prompt_tokens':10,'completion_tokens':5}})
                abstain='horaires' in payload['question']
                return {'content':json.dumps({'answer':'Réponse','abstain':abstain,'citation_ids':[payload['passages'][0]['id']]})}
        p=[];r=run_batch(Fake(),self.docs,[self.cases[0],self.cases[4]],on_progress=lambda x:p.append(len(x)))
        self.assertTrue(r['campaign_complete']);self.assertEqual(p,[1,2])
        self.assertEqual(r['summary']['behavior_matches'],2)
        self.assertEqual(r['summary']['provider_attempts'],2)
        self.assertEqual(r['summary']['prompt_tokens_reported'],20)
        self.assertIsNone(r['summary']['human_success_rate'])

    def test_provider_error_marks_partial_and_keeps_trace(self):
        class Fake:
            def __init__(self):self.calls=[]
            def chat(self,*a,**kw):
                self.calls.append({'usage':{},'error':'http','http_status':429})
                raise ProviderError('Endpoint HTTP 429')
        r=run_batch(Fake(),self.docs,self.cases)
        self.assertFalse(r['campaign_complete']);self.assertEqual(len(r['results']),1)
        self.assertIsNone(r['results'][0]['behavior_match'])
        self.assertFalse(r['summary']['usage_complete'])
        self.assertIsNone(r['summary']['cost'])

    def test_no_retrieval_abstains_without_network(self):
        class Fake:
            def __init__(self):self.calls=[]
            def chat(self,*a,**kw):raise AssertionError('unexpected call')
        cases=[{'id':'X','question':'xyzzy quuxblorf','expected_behavior':'abstain','relevant_ids':[],'human_expectation':'No answer'}]
        r=run_batch(Fake(),self.docs,cases)
        self.assertTrue(r['results'][0]['output']['abstain']);self.assertEqual(r['summary']['provider_attempts'],0)

if __name__=='__main__':unittest.main()
