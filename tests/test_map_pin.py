"""Exercise a user-selected map point through the existing route ranking."""
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import Mock

from experiments.map_pin import make_handler, nearby_from_pin


class MapPinTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.db=Path(folder.name)/'places.sqlite'
        con=sqlite3.connect(self.db)
        con.execute('CREATE TABLE places (source_id TEXT,name TEXT,category TEXT,district TEXT,latitude REAL,longitude REAL)')
        con.executemany('INSERT INTO places VALUES (?,?,?,?,?,?)',[
            ('node/1','Café A','cafe','',5.331,-4.02),
            ('node/2','Café B','cafe','',5.332,-4.02)])
        con.commit();con.close()
        self.matrix=Mock(return_value={'status':'ok','distances_m':[400,100],
                                       'durations_s':[300,70],'source':'openrouteservice / OpenStreetMap'})
        self.body={'category':'cafe','mode':'walk','lat':5.33,'lon':-4.02}

    def test_nearby_map_point_uses_routed_distance_and_hides_coordinates(self):
        status,result=nearby_from_pin(self.body,self.db,self.matrix)
        self.assertEqual(status,200)
        self.assertEqual(result['status'],'ok')
        self.assertEqual([p['name'] for p in result['places']],['Café B','Café A'])
        self.assertEqual(result['places'][0]['distance'],'100 m')
        self.assertEqual(result['places'][0]['duration'],'environ 1 min')
        self.assertEqual(result['places'][0]['url'],'https://www.openstreetmap.org/node/2')
        self.assertNotIn('5.33',json.dumps(result))
        self.assertNotIn('-4.02',json.dumps(result))
        self.matrix.assert_called_once()

    def test_invalid_input_and_failure_never_invent_route(self):
        for value in (None,True,91,float('nan'),'5.33'):
            with self.subTest(value=value):
                status,response=nearby_from_pin({**self.body,'lat':value},self.db,self.matrix)
                self.assertEqual(status,400)
                self.assertEqual(response['status'],'invalid_location')
        self.assertEqual(nearby_from_pin({**self.body,'lon':0},self.db,self.matrix)[0],400)
        self.assertEqual(nearby_from_pin({**self.body,'category':'museum'},self.db,self.matrix)[0],400)
        self.assertEqual(nearby_from_pin({**self.body,'mode':'bus'},self.db,self.matrix)[0],400)
        self.matrix.assert_not_called()
        self.matrix.return_value={'status':'unavailable','reason':'rate_limited'}
        status,result=nearby_from_pin(self.body,self.db,self.matrix)
        self.assertEqual(status,200)
        self.assertEqual(result['places'],[])
        self.assertNotIn('100 m',json.dumps(result))

    def test_loopback_http_requires_token_origin_and_does_not_return_location(self):
        server=HTTPServer(('127.0.0.1',0),make_handler(self.db,'test-token',self.matrix))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port=server.server_port
        conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
        self.addCleanup(conn.close)
        conn.request('GET','/')
        response=conn.getresponse();html=response.read().decode('utf-8')
        self.assertEqual(response.status,200)
        self.assertIn('test-token',html)
        self.assertNotIn('ORS_API_KEY',html)
        self.assertNotIn('5.33, -4.02',html)
        conn.request('GET','/',headers={'Host':'not-local.example'})
        blocked_page=conn.getresponse();blocked_page.read();self.assertEqual(blocked_page.status,403)
        data=json.dumps(self.body)
        headers={'Content-Type':'application/json','Origin':f'http://127.0.0.1:{port}',
                 'X-Map-Token':'test-token'}
        conn.request('POST','/api/nearby',data,headers={**headers,'X-Map-Token':'wrong'})
        blocked=conn.getresponse();blocked.read();self.assertEqual(blocked.status,403)
        self.matrix.assert_not_called()
        conn.request('POST','/api/nearby',data,headers=headers)
        accepted=conn.getresponse();body=accepted.read().decode('utf-8')
        self.assertEqual(accepted.status,200)
        self.assertEqual(json.loads(body)['places'][0]['name'],'Café B')
        self.assertNotIn('5.33',body)
        self.assertEqual(self.matrix.call_count,1)


if __name__=='__main__':unittest.main()
