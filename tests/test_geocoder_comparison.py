"""Check comparison geometry, private output, and cached reruns without network calls."""
import json
import tempfile
import unittest
from pathlib import Path

from experiments.geocoder_comparison import (haversine_m, load_cases, parse_candidates,
                                              request_for, run)


class GeocoderComparisonTests(unittest.TestCase):
    def test_reference_cases_and_distance(self):
        cases,_=load_cases('data/geocoding_reference_8.json')
        self.assertEqual(len(cases),8)
        self.assertEqual({c['id'] for c in cases},{f'G{i:02d}' for i in range(1,9)})
        self.assertEqual(haversine_m((5.3,-4),(5.3,-4)),0)
        self.assertGreater(haversine_m((5.3,-4),(5.31,-4)),1000)

    def test_requests_are_bounded_and_key_stays_out_of_url(self):
        pelias=request_for('pelias','10 Avenue du Général de Gaulle, Abidjan','SECRET')
        self.assertNotIn('SECRET',pelias.full_url)
        self.assertEqual(pelias.get_header('Authorization'),'SECRET')
        self.assertIn('boundary.country=CIV',pelias.full_url)
        nominatim=request_for('nominatim','Abidjan','')
        self.assertIn('countrycodes=ci',nominatim.full_url)
        self.assertIn('agent-lab',nominatim.get_header('User-agent'))
        photon=request_for('photon','Abidjan','')
        self.assertIn('countrycode=CI',photon.full_url)

    def test_provider_parsers_preserve_order_for_top_one(self):
        pelias={'features':[{'properties':{'label':'Wrong','confidence':.2,'match_type':'fallback',
                                           'layer':'locality'},'geometry':{'coordinates':[-4.1,5.3]}},
                             {'properties':{'label':'Right','confidence':.9,'match_type':'exact',
                                           'layer':'venue'},'geometry':{'coordinates':[-4,5.3]}}]}
        self.assertEqual([x['label'] for x in parse_candidates('pelias',pelias)],['Wrong','Right'])
        self.assertEqual(parse_candidates('nominatim',[{'lat':'5.3','lon':'-4',
                     'display_name':'Place','type':'hotel'}])[0]['label'],'Place')
        photon={'features':[{'properties':{'housenumber':'10','street':'Avenue du Général de Gaulle',
                                          'city':'Abidjan'},'geometry':{'coordinates':[-4,5.3]}}]}
        self.assertIn('10 Avenue',parse_candidates('photon',photon)[0]['label'])

    def test_persists_private_candidates_and_resume_without_requery(self):
        cases,source_hash=load_cases('data/geocoding_reference_8.json')
        calls=[];sleeps=[];time_value=[0]
        def fake_lookup(provider,query,key):
            calls.append((provider,query))
            time_value[0]+=.01
            return {'status':'results','candidates':[{'label':query,'lat':cases[0]['reference_lat'],
                'lon':cases[0]['reference_lon'],'kind':'hotel','match_type':None,'confidence':None}]}
        def fake_sleep(seconds):
            sleeps.append(seconds);time_value[0]+=seconds
        with tempfile.TemporaryDirectory() as folder:
            report=run(cases[:1],source_hash,Path(folder)/'benchmark',('nominatim',),'',
                       lookup_fn=fake_lookup,clock=lambda:time_value[0],sleep=fake_sleep)
            self.assertEqual(report['completed'],2)
            self.assertGreaterEqual(sleeps[0],1.19)
            self.assertEqual(report['summary']['nominatim']['address']['within_100m'],1)
            private=json.loads((Path(folder)/'benchmark'/'review.private.json').read_text())
            self.assertIn('lat',private['rows'][0]['candidates'][0])
            public=json.loads((Path(folder)/'benchmark'/'report.json').read_text())
            self.assertNotIn('lat',json.dumps(public))
            self.assertNotIn('SECRET',json.dumps(public))
            run(cases[:1],source_hash,Path(folder)/'benchmark',('nominatim',),'',
                lookup_fn=fake_lookup,clock=lambda:time_value[0],sleep=fake_sleep)
            self.assertEqual(len(calls),2)

    def test_rate_limit_stops_campaign_before_more_requests(self):
        cases,source_hash=load_cases('data/geocoding_reference_8.json')
        calls=[]
        def throttled(provider,query,key):
            calls.append(provider)
            return {'status':'rate_limited','candidates':[]}
        with tempfile.TemporaryDirectory() as folder:
            report=run(cases,source_hash,Path(folder)/'benchmark',('nominatim',),'',
                       lookup_fn=throttled)
        self.assertEqual(calls,['nominatim'])
        self.assertFalse(report['campaign_complete'])
        self.assertEqual(report['stop_reason'],'nominatim: rate_limited')


if __name__=='__main__':unittest.main()
