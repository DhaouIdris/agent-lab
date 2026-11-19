import io
import json
import os
import random
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch
from experiments.route_service import route, valid_coordinates
from experiments.unified_agent import ask

def call(args):
    return {'tool_calls':[{'id':'r1','type':'function','function':{'name':'calculate_route','arguments':json.dumps(args)}}]}

class RouteTests(unittest.TestCase):
    def test_coordinate_bounds_and_types(self):
        for point in [(-90,-180),(90,180),(0,0),(5.32,-4.02)]:
            self.assertTrue(valid_coordinates(point))
        for point in [(90.00001,0),(-90.00001,0),(0,180.00001),(0,-180.00001),(float('nan'),0),(float('inf'),0),(True,0),('5',0),None,(0,)]:
            self.assertFalse(valid_coordinates(point))

    def test_ten_thousand_generated_points_offline(self):
        rng=random.Random(20261118)
        for _ in range(10000):
            lat=rng.uniform(-120,120);lon=rng.uniform(-220,220)
            self.assertEqual(valid_coordinates((lat,lon)), -90<=lat<=90 and -180<=lon<=180)

    def test_invalid_points_stop_before_model_and_routing(self):
        rng=random.Random(42)
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'x';db.touch();client=Mock()
            with patch('experiments.unified_agent.route') as service:
                for i in range(1000):
                    lat=(1 if i%2==0 else -1)*rng.uniform(90.01,99.99) if i%4<2 else 5.3200
                    lon=(1 if i%2==0 else -1)*rng.uniform(180.01,199.99) if i%4>=2 else -4.0100
                    bad=f'{lat:.5f}, {lon:.5f}'
                    start,end=(bad,'5.3200, -4.0200') if i%2==0 else ('5.3200, -4.0200',bad)
                    question=f'Itinéraire voiture entre {start} et {end}.'
                    result=ask(client,db,[],question)
                    self.assertEqual(result['guard_status'],'invalid_coordinates')
                    self.assertTrue(result['output']['abstain'])
                client.chat.assert_not_called()
                service.assert_not_called()
    def test_load_key_from_dotenv_and_environment_precedence(self):
        from experiments.route_service import load_route_key
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'.env').write_text('ORS_API_KEY=from_file\n',encoding='utf8')
            module_path=root/'experiments'/'route_service.py'
            with patch('experiments.route_service.__file__',str(module_path)),patch.dict(os.environ,{},clear=True):
                self.assertEqual(load_route_key(),'from_file')
                os.environ['ORS_API_KEY']='from_environment'
                self.assertEqual(load_route_key(),'from_environment')
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
            client.chat.assert_not_called()
    def test_coordinates_followed_by_full_stop(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'x';db.touch();client=Mock()
            client.chat.return_value=call({'origin_lat':5.319,'origin_lon':-4.0116,'destination_lat':5.3237,'destination_lon':-4.0169,'mode':'car'})
            with patch('experiments.unified_agent.route',return_value={'status':'ok','distance_m':1250,'duration_s':180,'mode':'car'}) as service:
                result=ask(client,db,[],"Donne l’itinéraire en voiture de 5.3190, -4.0116 à 5.3237, -4.0169.")
            self.assertFalse(result['output']['abstain'])
            service.assert_called_once()
    def test_agent_rejects_fabricated_coordinates(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'x';db.touch();client=Mock()
            client.chat.return_value=call({'origin_lat':5.32,'origin_lon':-4.02,'destination_lat':5.35,'destination_lon':-4.01,'mode':'car'})
            with patch('experiments.unified_agent.route',return_value={'status':'unavailable'}) as service:
                ask(client,db,[],'Itinéraire voiture entre 5.32, -4.02 et 5.34, -4.01 ?')
                self.assertEqual(service.call_args.args[:3],((5.32,-4.02),(5.34,-4.01),'car'))
                client.chat.assert_not_called()
    def test_model_cannot_fabricate_final_route(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'x';db.touch();client=Mock()
            client.chat.return_value={'content':json.dumps({'answer':'1 km','document_ids':[],'place_ids':[],'abstain':False})}
            with patch('experiments.unified_agent.route',return_value={'status':'unavailable'}):
                result=ask(client,db,[],'Itinéraire voiture entre 5.32, -4.02 et 5.34, -4.01 ?')
            client.chat.assert_not_called()
            self.assertNotIn('1 km',result['output']['answer'])
            self.assertTrue(result['output']['abstain'])
