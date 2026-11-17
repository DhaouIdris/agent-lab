import csv
import json
import tempfile
import unittest
from pathlib import Path
from experiments.place_catalog import import_csv,search

class CatalogueTests(unittest.TestCase):
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

if __name__=='__main__':unittest.main()
