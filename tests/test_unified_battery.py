import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from experiments.unified_agent_batch import run

class BatteryTests(unittest.TestCase):
    def test_battery_metadata(self):
        cases=[]
        for i in (1,2,3):
            batch=json.loads(Path(f'data/unified_agent_battery_{i}.json').read_text(encoding='utf8'))
            self.assertEqual(len(batch),8);cases.extend(batch)
        self.assertEqual(len({c['id'] for c in cases}),24)
        self.assertTrue(all(c['human_expectation'] and set(c['required_tools'])<={'search_catalogue','search_documents'} for c in cases))

    def test_argument_and_forbidden_tool_checks_are_separate(self):
        c={'id':'T','question':'q','human_expectation':'review','required_tools':['search_catalogue'],
           'tool_arg_checks':[{'tool':'search_catalogue','equals':{'category':'hotel'}}],
           'forbidden_tools':['search_documents']}
        result={'output':{'answer':'ok','place_ids':[],'document_ids':[],'abstain':False},
          'trace':[{'tool':'search_catalogue','arguments':{'category':'cafe'}},{'tool':'search_documents','arguments':{'query':'q'}}]}
        client=Mock();client.calls=[]
        with patch('experiments.unified_agent_batch.ask',return_value=result):r=run(client,'unused',[],[c])
        row=r['results'][0]
        self.assertTrue(row['tool_selection_match'])
        self.assertFalse(row['argument_checks_pass'])
        self.assertFalse(row['forbidden_tools_pass'])
        self.assertEqual(r['summary']['forbidden_tool_violations'],1)
