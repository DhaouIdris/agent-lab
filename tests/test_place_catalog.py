import csv
import json
import tempfile
import unittest
from pathlib import Path
from experiments.place_catalog import import_csv,search,audit_csv,distance_m

class CatalogueTests(unittest.TestCase):
    def test_distance_is_geodesic(self):
        self.assertAlmostEqual(distance_m(0,0,0,1),111194.9,delta=1)
    def test_radius_applies_before_limit_and_sorts_by_distance(self):
        with self.csv.open('a',encoding='utf8',newline='') as f:
            w=csv.writer(f)
            w.writerow(['node/far','A far','Ice-Cream',json.dumps({'type':'Point','coordinates':[-4,5.34]}),''])
            w.writerow(['node/near','Z near','Ice-Cream',json.dumps({'type':'Point','coordinates':[-4,5.301]}),''])
        import_csv(self.csv,self.db)
        r=search(self.db,category='ice_cream',latitude=5.3,longitude=-4,radius_m=10000,limit=1)
        self.assertEqual(r['items'][0]['source_id'],'node/near')
        self.assertEqual(r['distance_method'],'haversine_straight_line')
        self.assertAlmostEqual(r['items'][0]['distance_m'],111.2,delta=1)
        self.assertEqual(search(self.db,category='ice_cream',latitude=5.3,longitude=-4,radius_m=50)['items'],[])
        for geo in ({'latitude':5.3},{'latitude':float('nan'),'longitude':-4,'radius_m':1},{'latitude':5.3,'longitude':-4,'radius_m':20001}):
            with self.subTest(geo=geo),self.assertRaises(ValueError):search(self.db,**geo)
    def setUp(self):
        self.d=tempfile.TemporaryDirectory();self.addCleanup(self.d.cleanup)
        self.csv=Path(self.d.name)/'source.csv';self.db=Path(self.d.name)/'catalog.sqlite'
        with self.csv.open('w',encoding='utf-8',newline='') as f:
            w=csv.writer(f);w.writerow(['id','nom_de_l_etablissement','categorie','geometry','ville_ou_commune'])
            w.writerow(['way/1','Café Étoile','Café',json.dumps({'type':'Point','coordinates':[-4,5.3]}),'Cocody'])
            w.writerow(['way/1','Duplicate','Café',json.dumps({'type':'Point','coordinates':[-4,5.3]}),'Cocody'])
            w.writerow(['way/2','No location','Hôtel','not-json',''])
            w.writerow(['way/3','Restaurant Test','Restaurant',json.dumps({'type':'Point','coordinates':[-4,5.3]}),'Plateau'])
    def test_import_and_unicode_search(self):
        m=import_csv(self.csv,self.db)
        self.assertEqual(m['counts'],{'rows':4,'inserted':2,'rejected':1,'duplicates':1})
        r=search(self.db,category='cafe',district='cocody',query='etoile')
        self.assertEqual([x['source_id'] for x in r['items']],['way/1'])
        self.assertFalse(r['current_status_verified'])
        self.assertIn('OpenStreetMap',r['attribution'])
    def test_rejects_overwrite_and_sql_wildcard(self):
        import_csv(self.csv,self.db)
        with self.assertRaises(ValueError):import_csv(self.csv,self.db)
        self.assertEqual(search(self.db,query='%')['items'],[])
        with self.assertRaises(ValueError):search(self.db,limit=0)
    def test_bad_headers_leave_no_database(self):
        self.csv.write_text('id,name\n1,test\n',encoding='utf-8')
        with self.assertRaises(ValueError):import_csv(self.csv,self.db)
        self.assertFalse(self.db.exists())

    def test_audit_counts_match_import_and_overlapping_reasons(self):
        with self.csv.open('a',encoding='utf8',newline='') as f:
            csv.writer(f).writerow(['way/4','','Unmapped','not-json',''])
        audit=audit_csv(self.csv)
        self.assertEqual(audit['counts']['rejected'],2)
        self.assertEqual(audit['rejection_reasons_overlapping'],{'invalid_geometry':2,'missing_name':1,'unsupported_category':1})
        self.assertEqual(audit['accepted_categories'],{'cafe':1,'restaurant':1})
        meta=import_csv(self.csv,self.db)
        for k in ('rows','inserted','duplicates','rejected'):
            self.assertEqual(audit['counts'][k],meta['counts'][k])
        self.assertEqual(audit['file_sha256'],meta['file_sha256'])

    def test_fast_food_and_ice_cream_keep_distinct_categories(self):
        with self.csv.open('a',encoding='utf8',newline='') as f:
            w=csv.writer(f);geometry=json.dumps({'type':'Point','coordinates':[-4,5.3]})
            w.writerow(['way/4','Le fast-food','Fast-Food',geometry,''])
            w.writerow(['way/5','Le glacier','Ice-Cream',geometry,''])
            w.writerow(['way/6','','Ice-Cream',geometry,''])
        audit=audit_csv(self.csv)
        self.assertEqual(audit['accepted_categories']['fast_food'],1)
        self.assertEqual(audit['accepted_categories']['ice_cream'],1)
        self.assertEqual(audit['rejection_reasons_overlapping']['missing_name'],1)
        import_csv(self.csv,self.db)
        self.assertEqual(search(self.db,category='fast_food')['items'][0]['source_id'],'way/4')
        self.assertEqual(search(self.db,category='ice_cream')['items'][0]['source_id'],'way/5')
        self.assertEqual(search(self.db,category='restaurant')['items'][0]['source_id'],'way/3')


if __name__=='__main__':unittest.main()



