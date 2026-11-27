import unittest
from unittest.mock import Mock

from ci_agentlab.providers import ProviderError
from experiments.provider_probe import probe


class ProviderProbeTests(unittest.TestCase):
    def test_reports_only_structure_and_safe_error_fields(self):
        client=Mock()
        client.calls=[]
        def call(*args,**kwargs):
            if not client.calls:
                client.calls.append({'usage':{}})
                return {'content':'{"ok":true}'}
            client.calls.append({'http_status':400,'provider_error_param':'tools'})
            raise ProviderError('Sensitive server body')
        client.chat.side_effect=call
        result=probe(client)
        self.assertEqual(result[0]['stage'],'json_only')
        self.assertTrue(result[0]['valid_json_object'])
        self.assertEqual(result[1],{'stage':'tool_auto','status':'provider_error',
                                    'http_status':400,'provider_error_param':'tools'})
        self.assertNotIn('Sensitive',str(result))
