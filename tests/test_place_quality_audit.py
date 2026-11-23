import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from experiments.audit_place_quality import audit, generic_name, main


class PlaceQualityAuditTests(unittest.TestCase):
    def test_generic_distinct_and_same_place_signals(self):
        self.assertTrue(generic_name('Hôtel'))
        self.assertTrue(generic_name('Kiosque café'))
        self.assertFalse(generic_name('Café Aboki'))
        places=[
            {'source_id':'node/1','name':'Seen hôtel Abidjan','category':'hotel','district':'','latitude':5.3200,'longitude':-4},
            {'source_id':'way/2','name':'Seen Hotel Abidjan Plateau','category':'hotel','district':'','latitude':5.3202,'longitude':-4},
            {'source_id':'node/3','name':'Kiosque','category':'cafe','district':'','latitude':5.3300,'longitude':-4},
            {'source_id':'node/4','name':'Kiosque','category':'cafe','district':'','latitude':5.3301,'longitude':-4},
            {'source_id':'node/5','name':'Cafe Aboki','category':'cafe','district':'Plateau','latitude':5.3300,'longitude':-4},
            {'source_id':'node/6','name':'Cafe Aboki','category':'cafe','district':'','latitude':5.40,'longitude':-4},
        ]
        review={'results':[{'id':'NC1','short_top3':[
            {'source_id':p['source_id'],'name':p['name']} for p in places[:3]]}]}
        public,private=audit(places,review)
        self.assertEqual(public['nearby_pair_counts']['possible_same_place'],1)
        self.assertEqual(public['nearby_pair_counts']['generic_nearby_pair'],1)
        self.assertEqual(public['review_impact'][0]['generic_displayed'],1)
        self.assertEqual(public['review_impact'][0]['possible_same_place_pairs_in_top3'],1)
        self.assertEqual(public['categories']['hotel']['missing_district'],2)
        self.assertNotIn('Seen',json.dumps(public))
        self.assertNotIn('5.3200',json.dumps(public))
        self.assertEqual(private['possible_same_place_examples'][0]['first_id'],'node/1')

    def test_command_reads_sqlite_without_changes_and_writes_bounded_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'places.sqlite';out=Path(tmp)/'results'
            con=sqlite3.connect(db)
            try:
                con.execute('CREATE TABLE places (source_id TEXT,name TEXT,category TEXT,district TEXT,latitude REAL,longitude REAL)')
                con.execute('INSERT INTO places VALUES (?,?,?,?,?,?)',('node/1','Hotel','hotel','',5.32,-4))
                con.commit()
            finally:con.close()
            main(['--db',str(db),'--out',str(out)])
            public=json.loads((out/'report.json').read_text(encoding='utf-8'))
            private=json.loads((out/'review.private.json').read_text(encoding='utf-8'))
            self.assertEqual(public['categories']['hotel']['generic_name'],1)
            self.assertNotIn('node/1',json.dumps(public))
            self.assertEqual(private['generic_examples'][0]['source_id'],'node/1')
            con=sqlite3.connect(db)
            try:self.assertEqual(con.execute('SELECT count(*) FROM places').fetchone()[0],1)
            finally:con.close()


if __name__=='__main__':unittest.main()
