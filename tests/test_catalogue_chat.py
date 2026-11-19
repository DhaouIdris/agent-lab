import csv
import json
import tempfile
import unittest
from pathlib import Path
from experiments.place_catalog import import_csv
from experiments.catalogue_chat import ask
from ci_agentlab.providers import ProviderError

class CatalogueChatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);csv_path=root/'input.csv';self.db=root/'db.sqlite'
        with csv_path.open('w',encoding='utf8',newline='') as f:
            w=csv.writer(f);w.writerow(['id','nom_de_l_etablissement','categorie','geometry','ville_ou_commune'])
            w.writerow(['node/1','Glacier Test','Ice-Cream',json.dumps({'type':'Point','coordinates':[-4,5]}),''])
        import_csv(csv_path,self.db)

    def test_roundtrip_only_returns_observed_catalogue_records(self):
        class Fake:
            def __init__(self):self.count=0;self.evidence=None
            def chat(self,messages,timeout,tools_override):
                self.count+=1
                if self.count==1:return {'tool_calls':[{'id':'1','type':'function','function':{'name':'search_catalogue','arguments':'{"category":"ice_cream"}'}}]}
                self.evidence=json.loads(messages[-1]['content'])
                return {'content':'Glacier Test — données historiques non vérifiées.'}
        client=Fake();answer=ask(client,self.db,'Un glacier ?')
        self.assertIn('Glacier Test',answer)
        self.assertEqual(client.evidence['items'][0]['source_id'],'node/1')
        self.assertFalse(client.evidence['current_status_verified'])

    def test_unknown_tool_or_extra_parameters_are_rejected(self):
        for name,args in [('execute_shell','{}'),('search_catalogue','{"category":"bar","admin":true}')]:
            class Fake:
                def chat(self,*a,**kw):return {'tool_calls':[{'id':'1','function':{'name':name,'arguments':args}}]}
            with self.subTest(name=name),self.assertRaises(ProviderError):ask(Fake(),self.db,'question')

    def test_unknown_database_fails_before_provider_call(self):
        class Fake:
            def chat(self,*a,**kw):raise AssertionError('provider should not be called')
        with self.assertRaises(ValueError):ask(Fake(),self.db.parent/'missing','question')

if __name__=='__main__':unittest.main()
