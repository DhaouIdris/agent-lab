import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from experiments.nearby_quality_experiment import evaluate_case, metrics, quality_top3
from experiments.compare_nearby_shortlists import route_ranking
from experiments.prepare_pair_review import select_pairs


class QualityExperimentTests(unittest.TestCase):
    def test_nearest_preserved_and_short_detour_for_distinctive_name(self):
        names=['Kiosque','Café','Cafétéria','Café Aboki']
        places=[{'source_id':f'n{i}','name':name,'latitude':5.320+i*.0001,'longitude':-4}
                for i,name in enumerate(names)]
        baseline=route_ranking(places,[100,200,220,230])
        selected=quality_top3(places,[100,200,220,230])
        self.assertEqual([r[1] for r in selected],['n0','n1','n3'])
        self.assertEqual(metrics(baseline,selected)['generic_names'],2)
        self.assertTrue(metrics(baseline,selected)['nearest_preserved'])
        self.assertEqual(metrics(baseline,selected)['rank_distance_extra_m'],[0,0,10])

    def test_close_similar_hotel_names_replaced_without_merging(self):
        names=['Seen hôtel Abidjan','Seen Hotel Abidjan Plateau','Hôtel Novotel Abidjan','Hotel Ivoire']
        places=[{'source_id':f'n{i}','name':name,'latitude':5.32+i*.0001,'longitude':-4}
                for i,name in enumerate(names)]
        selected=quality_top3(places,[1400,1480,1540,1550])
        self.assertEqual([row[1] for row in selected],['n0','n2','n3'])
        self.assertEqual(selected[0][0],1400)

    def test_avoids_extra_travel_beyond_budget_and_never_hides_only_generic(self):
        places=[{'source_id':str(i),'name':name,'latitude':5.32+i*.0001,'longitude':-4}
                for i,name in enumerate(['Café','Kiosque','Café Aboki'])]
        self.assertEqual([r[1] for r in quality_top3(places,[100,200,400])],['0','1','2'])
        self.assertEqual([r[1] for r in quality_top3(places[:2],[100,200])],['0','1'])

    def test_case_one_matrix_call_and_public_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'places.sqlite';con=sqlite3.connect(db)
            try:
                con.execute('CREATE TABLE places (source_id TEXT,name TEXT,category TEXT,district TEXT,latitude REAL,longitude REAL)')
                con.executemany('INSERT INTO places VALUES (?,?,?,?,?,?)',[
                    ('n0','Café','cafe','',5.3201,-4),
                    ('n1','Kiosque','cafe','',5.3202,-4),
                    ('n2','Café Aboki','cafe','',5.3203,-4),
                ]);con.commit()
            finally:con.close()
            service=Mock(return_value={'status':'ok','distances_m':[100,200,220]})
            row,detail=evaluate_case({'id':'NC1','origin':[5.32,-4],
                                      'category':'cafe','mode':'walk'},db,'SECRET',service)
            self.assertEqual(service.call_count,1)
            self.assertTrue(row['12']['proposed']['nearest_preserved'])
            self.assertNotIn('Café',json.dumps(row,ensure_ascii=False))
            self.assertNotIn('5.32',json.dumps(row))
            self.assertNotIn('SECRET',json.dumps(row))
            self.assertEqual(detail['12_top3']['baseline'][0]['name'],'Café')

    def test_manual_review_sheet_keeps_first_displayed_pair_and_blank_decision(self):
        pair={'first_id':'n1','first_name':'Seen hôtel Abidjan',
              'second_id':'w2','second_name':'Seen Hotel Abidjan Plateau',
              'categories':['hotel','hotel'],'separation_m':12}
        quality={'possible_same_place_examples':[pair]}
        comparison={'results':[{'id':'NC04','short_top3':[{'source_id':'n1'},{'source_id':'w2'}],
                                'possible_duplicates':[pair]}]}
        rows=select_pairs(quality,comparison)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['origin_case'],'NC04')
        self.assertEqual(rows[0]['manual_decision'],'')
        self.assertEqual(rows[0]['separation_m'],12)


if __name__=='__main__':unittest.main()
