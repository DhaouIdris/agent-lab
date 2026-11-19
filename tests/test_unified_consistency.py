import unittest
from unittest.mock import Mock, patch
from experiments.unified_agent_consistency import campaign

class ConsistencyTests(unittest.TestCase):
    def test_interleaves_repetitions_and_continues_model_errors(self):
        cases=[{'id':'a'},{'id':'b'}]
        def response(client,db,docs,one,timeout):
            if one[0]['id']=='a' and response.count==0:
                row={'id':'a','status':'execution_error','diagnostic_code':'invalid_json','output':None,'provider_calls':[]}
            else:
                row={'id':one[0]['id'],'status':'model_output','output':{'abstain':True},'observed_tools':[],'provider_calls':[]}
            response.count+=1
            return {'results':[row]}
        response.count=0
        with patch('experiments.unified_agent_consistency.run',side_effect=response):
            report=campaign(Mock(),None,[],cases,repeat=2)
        self.assertTrue(report['campaign_complete'])
        self.assertEqual([(r['id'],r['repetition']) for r in report['results']],[('a',1),('b',1),('a',2),('b',2)])
        self.assertEqual(report['summary']['execution_errors'],1)
        self.assertEqual(report['per_case'][0]['model_outputs'],1)
        self.assertEqual(report['per_case'][0]['abstentions'],1)

    def test_provider_error_stops_and_checkpoints(self):
        row={'id':'a','status':'execution_error','diagnostic_code':'provider_error','output':None,'provider_calls':[]}
        progress=Mock()
        with patch('experiments.unified_agent_consistency.run',return_value={'results':[row]}):
            report=campaign(Mock(),None,[],[{'id':'a'},{'id':'b'}],repeat=2,on_progress=progress)
        self.assertFalse(report['campaign_complete'])
        self.assertEqual(report['summary']['runs_completed'],1)
        self.assertEqual(report['stop_reason'],'provider_or_deadline_error')
        progress.assert_called_once()
