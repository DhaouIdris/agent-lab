import io
import json
import unittest
from unittest.mock import Mock
from experiments.document_rag import load_corpus,retrieve,evaluate,generate
from ci_agentlab.providers import ChatClient

class DocumentRagTests(unittest.TestCase):
    def setUp(self):self.docs=load_corpus()
    def test_accent_insensitive_retrieval_and_provenance(self):
        hits=retrieve('Annee inscription parc national de Tai',self.docs)
        self.assertEqual(hits[0]['id'],'CI_UNESCO_TAI')
        self.assertTrue(hits[0]['url'].startswith('https://whc.unesco.org/'))
        self.assertEqual(hits[0]['content_type'],'curated_paraphrase')
    def test_no_match_abstains_without_client(self):
        hits=retrieve('xyzzy quuxblorf',self.docs)
        self.assertEqual(hits,[])
        self.assertTrue(generate(None,'xyzzy quuxblorf',hits)['abstain'])
    def test_eval_reports_actual_miss(self):
        r=evaluate(self.docs,[{'id':'X','question':'xyzzy quuxblorf','relevant_ids':['CI_UNESCO_TAI']}])
        self.assertEqual(r['hit_at_k'],0);self.assertEqual(r['mrr_at_k'],0)
    def test_answer_must_cite_a_retrieved_id(self):
        hits=retrieve('Grand Bassam',self.docs)
        class Fake:
            def __init__(self,content):self.content=content
            def chat(self,*a,**kw):return {'content':json.dumps(self.content)}
        accepted={'answer':'Inscrit en 2012.','citation_ids':['CI_UNESCO_BASSAM'],'abstain':False}
        self.assertEqual(generate(Fake(accepted),'Grand Bassam',hits)['sources'][0]['id'],'CI_UNESCO_BASSAM')
        for cited in ([],['INVENTED']):
            with self.subTest(cited=cited),self.assertRaises(ValueError):generate(Fake({**accepted,'citation_ids':cited}),'Grand Bassam',hits)
    def test_documents_without_tools_omit_tools_from_http_request(self):
        client=ChatClient('https://example.com/openai/v1','model',max_calls=1)
        client.opener=Mock()
        client.opener.open.return_value=io.BytesIO(json.dumps({'choices':[{'message':{'content':'{}'}}],'usage':{}}).encode())
        client.chat([{'role':'user','content':'hello'}],tools_override=[],tool_choice='none',response_format={'type':'json_object'})
        request=client.opener.open.call_args.args[0];body=json.loads(request.data)
        self.assertNotIn('tools',body);self.assertNotIn('tool_choice',body)
        self.assertEqual(body['response_format'],{'type':'json_object'})

if __name__=='__main__':unittest.main()
