import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch
from experiments.route_service import route
from experiments.unified_agent import ask

def call(args):
    return {'tool_calls':[{'id':'r1','type':'function','function':{'name':'calculate_route','arguments':json.dumps(args)}}]}

class RouteTests(unittest.TestCase):
    def test_request_converts_latlon_and_result(self):
        transport=Mock();transport.open.return_value=io.BytesIO(json.dumps({'routes':[{'summary':{'distance':1250,'duration':180}}]}).encode())
        result=route((5.32,-4.02),(5.34,-4.01),'car','TEST_KEY',opener=transport)
        request=transport.open.call_args.args[0]
        self.assertEqual(json.loads(request.data)['coordinates'],[[-4.02,5.32],[-4.01,5.34]])
        self.assertEqual(result['distance_m'],1250)
        self.assertNotIn('TEST_KEY',str(result))
    def test_invalid_missing_key_and_server_failures(self):
        transport=Mock()
        self.assertEqual(route((5.32,-4.02),(5.34,-4.01),'car','',opener=transport)['status'],'unavailable')
        self.assertEqual(route((float('nan'),0),(0,0),'car','x',opener=transport)['status'],'invalid_coordinates')
        transport.open.side_effect=urllib.error.HTTPError('https://example.invalid',429,'x',{},None)
        self.assertEqual(route((5.32,-4.02),(5.34,-4.01),'car','x',opener=transport)['reason'],'rate_limited')
    def test_agent_faithfully_returns_route_and_does_not_log_positions(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'x';db.touch();client=Mock()
            args={'origin_lat':5.32,'origin_lon':-4.02,'destination_lat':5.34,'destination_lon':-4.01,'mode':'car'}
            client.chat.return_value=call(args)
            with patch('experiments.unified_agent.route',return_value={'status':'ok','distance_m':1250,'duration_s':180,'mode':'car'}):
                result=ask(client,db,[],'Quel itinéraire en voiture entre 5.32, -4.02 et 5.34, -4.01 ?')
            self.assertIn('1.25 km',result['output']['answer']);self.assertIn('3 minutes',result['output']['answer'])
            self.assertNotIn('5.32',str(result['trace']))
            self.assertEqual(client.chat.call_count,1)
    def test_agent_rejects_fabricated_coordinates(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'x';db.touch();client=Mock()
            client.chat.return_value=call({'origin_lat':5.32,'origin_lon':-4.02,'destination_lat':5.35,'destination_lon':-4.01,'mode':'car'})
            with patch('experiments.unified_agent.route') as service:
                with self.assertRaises(Exception):ask(client,db,[],'Itinéraire voiture entre 5.32, -4.02 et 5.34, -4.01 ?')
                service.assert_not_called()
    def test_model_cannot_fabricate_final_route(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'x';db.touch();client=Mock()
            client.chat.return_value={'content':json.dumps({'answer':'1 km','document_ids':[],'place_ids':[],'abstain':False})}
            result=ask(client,db,[],'Itinéraire voiture entre 5.32, -4.02 et 5.34, -4.01 ?')
            self.assertEqual(result['diagnostic_code'],'route_not_called')
            self.assertTrue(result['output']['abstain'])
