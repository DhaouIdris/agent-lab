import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from experiments.compare_nearby_shortlists import compare_case, duplicate_candidates, load_cases
from experiments.nearby_places import candidates
from experiments.route_service import matrix
from experiments.unified_agent import format_route_distance


class ShortlistComparisonTests(unittest.TestCase):
    def test_comparison_same_matrix_response_and_no_public_names_or_coordinates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'pois.sqlite'
            con=sqlite3.connect(db)
            try:
                con.execute('CREATE TABLE places (source_id TEXT,name TEXT,category TEXT,district TEXT,latitude REAL,longitude REAL)')
                con.executemany('INSERT INTO places VALUES (?,?,?,?,?,?)',[
                    (f'node/{i}',f'Cafe {i}','cafe','',5.3201+i*.0001,-4.012) for i in range(1,15)])
                con.commit()
            finally:
                con.close()
            case={'id':'NC00','origin':[5.3201,-4.012],'category':'cafe','mode':'walk'}
            service=Mock(return_value={'status':'ok','distances_m':[1000+i for i in range(12)]+[20,30],
                                       'durations_s':[100]*14})
            public,private=compare_case(case,db,'SECRET',service)
            self.assertEqual(service.call_count,1)
            self.assertEqual(len(service.call_args.args[1]),14)
            self.assertEqual(public['wide_top3_missing_from_short'],2)
            self.assertEqual(public['nearest_regret_m'],980)
            self.assertTrue(public['nearest_bounded_in_catalogue'])
            self.assertTrue(public['top3_bounded_in_catalogue'])
            self.assertEqual(private['wide_top3'][0]['source_id'],'node/13')
            self.assertNotIn('SECRET',json.dumps(public))
            self.assertNotIn('5.3201',json.dumps(public))
            self.assertNotIn('Cafe',json.dumps(public))
            self.assertEqual(len(candidates(db,case['origin'],'cafe')[0]),12)
            self.assertEqual(len(candidates(db,case['origin'],'cafe',limit=50)[0]),14)

    def test_same_top_three_can_leave_fifty_candidate_result_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'pois.sqlite'
            con=sqlite3.connect(db)
            con.execute('CREATE TABLE places (source_id TEXT,name TEXT,category TEXT,district TEXT,latitude REAL,longitude REAL)')
            con.executemany('INSERT INTO places VALUES (?,?,?,?,?,?)',[
                (f'node/{i}',f'Restaurant {i}','restaurant','',5.33+i*.0001,-4.02)
                for i in range(55)])
            con.commit();con.close()
            case={'id':'NC55','origin':[5.33,-4.02],'category':'restaurant','mode':'walk'}
            service=Mock(return_value={'status':'ok',
                'distances_m':[1900+i*10 for i in range(50)],'durations_s':[1800]*50})
            public,_=compare_case(case,db,'SECRET',service)
            self.assertEqual(public['top3_overlap'],3)
            self.assertFalse(public['nearest_bounded_in_catalogue'])
            self.assertFalse(public['top3_bounded_in_catalogue'])
            self.assertLess(public['untested_air_distance_lower_bound_m'],1900)
            self.assertEqual(service.call_count,1)

            service.return_value['distances_m']=[100+i*5 for i in range(50)]
            public,_=compare_case(case,db,'SECRET',service)
            self.assertTrue(public['nearest_bounded_in_catalogue'])
            self.assertTrue(public['top3_bounded_in_catalogue'])

            service.return_value['distances_m'][20]=None
            public,_=compare_case(case,db,'SECRET',service)
            self.assertFalse(public['nearest_bounded_in_catalogue'])
            self.assertFalse(public['top3_bounded_in_catalogue'])

    def test_duplicate_signal_does_not_merge_distinct_names(self):
        places=[{'source_id':str(i),'name':name,'latitude':lat,'longitude':-4}
                for i,name,lat in [(1,'Café Aboki',5.32),(2,'Cafe Aboki',5.3201),
                                   (3,'Cafe Aboki',5.33),(4,'Café différent',5.3201)]]
        self.assertEqual([(p['first_id'],p['second_id']) for p in duplicate_candidates(places)], [('1','2')])

    def test_matrix_accepts_fifty_and_rejects_fifty_one(self):
        origin=(5.32,-4)
        opener=Mock()
        opener.open.return_value=io.BytesIO(json.dumps({'distances':[[100]*50],
                                                         'durations':[[50]*50]}).encode())
        self.assertEqual(matrix(origin,[origin]*50,'walk','SECRET',opener=opener)['status'],'ok')
        self.assertEqual(matrix(origin,[origin]*51,'walk','SECRET',opener=opener)['status'],'invalid_coordinates')
        self.assertEqual(opener.open.call_count,1)

    def test_distance_boundary_and_case_manifest(self):
        self.assertEqual(format_route_distance(999.6),'1000 m')
        self.assertEqual(format_route_distance(1000),'1.00 km')
        self.assertEqual(format_route_distance(161),'161 m')
        self.assertEqual(len(load_cases('data/nearby_shortlist_comparison_8.json')),8)


if __name__=='__main__':
    unittest.main()
