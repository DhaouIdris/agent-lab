import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from experiments.unified_agent_batch import run

class RealisticBatteryTests(unittest.TestCase):
    def test_scenario_files_and_security_expectations(self):
        cases=[]
        for i in range(1,4):
            batch=json.loads(Path(f'data/realistic_agent_battery_{i}.json').read_text(encoding='utf8'))
            self.assertEqual(len(batch),10);cases.extend(batch)
        self.assertEqual(len({x['id'] for x in cases}),30)
        attacks=[c for c in cases if c['category']=='injection']
        self.assertEqual(len(attacks),10)
        self.assertTrue(all(c['outcome_checks']['status']=='blocked_suspected_injection' and c['outcome_checks']['max_provider_calls']==0 for c in attacks))
    def test_pre_model_check_flags_provider_call(self):
        case={'id':'a','question':'q','category':'injection','human_expectation':'block','required_tools':[],
              'outcome_checks':{'status':'blocked_suspected_injection','max_provider_calls':0}}
        result={'guard_status':'blocked_suspected_injection','trace':[],
                'output':{'answer':'stop','document_ids':[],'place_ids':[],'abstain':True}}
        client=Mock();client.calls=[]
        def fake(*args,**kwargs):
            client.calls.append({'usage':{}})
            return result
        with patch('experiments.unified_agent_batch.ask',side_effect=fake):
            row=run(client,'unused',[],[case])['results'][0]
        self.assertFalse(row['outcome_checks']['max_provider_calls'])
        self.assertFalse(row['outcome_checks_pass'])
