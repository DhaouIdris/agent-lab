import io
import json
import unittest
from unittest.mock import Mock
from experiments.document_rag import generate
from experiments.hybrid_retrieval import cosine, hybrid, rrf, embeddings
from experiments.prompt_shield import AzurePromptShield, ShieldUnavailable


class HybridTests(unittest.TestCase):
    def test_rrf_combines_rankings(self):
        self.assertEqual(rrf(['A','B'],['B','C'],k=3), ['B','A','C'])
        with self.assertRaises(ValueError):rrf(['A','A'],[],k=2)

    def test_cosine_and_hybrid(self):
        docs=[{'id':'a','title':'Musée', 'text':'Histoire locale'}, {'id':'b','title':'Parc', 'text':'Nature'}]
        result=hybrid('musée',docs,[[1.,0.],[0.,1.],[1.,0.]],k=2)
        self.assertEqual(set(d['id'] for d in result['passages']), {'a','b'})
        with self.assertRaises(ValueError):cosine([0,0],[1,0])

    def test_azure_embedding_indices_and_validation(self):
        opener=Mock(); opener.open.return_value=io.BytesIO(json.dumps({'data':[{'index':1,'embedding':[1,0]},{'index':0,'embedding':[0,1]}]}).encode())
        result=embeddings('https://demo.openai.azure.com/openai/v1','secret','deploy',['a','b'],opener)
        self.assertEqual(result, [[0,1],[1,0]])
        with self.assertRaises(ValueError):embeddings('https://evil.example/openai/v1','key','x',['a'],opener)


class ShieldTests(unittest.TestCase):
    def test_blocks_before_generation(self):
        client=Mock();shield=Mock();shield.inspect.return_value={'user_attack':False,'flagged_source_ids':['d']}
        out=generate(client,'question',[{'id':'d','title':'Musée','text':'Testville'}],shield=shield)
        self.assertEqual(out['guard_status'],'blocked_suspected_injection')
        client.chat.assert_not_called()

    def test_unavailable_fails_closed(self):
        client=Mock();shield=Mock();shield.inspect.side_effect=ShieldUnavailable()
        out=generate(client,'question',[{'id':'d','text':'ok'}],shield=shield)
        self.assertEqual(out['guard_status'],'guard_unavailable')
        client.chat.assert_not_called()

    def test_bad_schema_fails_closed(self):
        opener=Mock();opener.open.return_value=io.BytesIO(b'{"userPromptAnalysis":{"attackDetected":false},"documentsAnalysis":[]}')
        shield=AzurePromptShield('https://example.cognitiveservices.azure.com','key',opener)
        with self.assertRaises(ShieldUnavailable):shield.inspect('q',[{'id':'d','text':'content'}])

    def test_no_secrets_redirects_or_untrusted_endpoint(self):
        with self.assertRaises(ValueError):AzurePromptShield('https://evil.example','secret')
        with self.assertRaises(ValueError):AzurePromptShield('https://a.cognitiveservices.azure.com/?key=secret','secret')

    def test_batches_all_passages(self):
        class Fake:
            def __init__(self):self.calls=[]
            def open(self,request,timeout):
                data=json.loads(request.data); self.calls.append(data)
                return io.BytesIO(json.dumps({'userPromptAnalysis':{'attackDetected':False},'documentsAnalysis':[{'attackDetected':i==0} for i in range(len(data['documents']))]}).encode())
        fake=Fake();shield=AzurePromptShield('https://demo.cognitiveservices.azure.com','key',fake)
        result=shield.inspect('q',[{'id':str(i),'text':'a'} for i in range(6)])
        self.assertEqual(result['flagged_source_ids'],['0','5']);self.assertEqual(len(fake.calls),2)
