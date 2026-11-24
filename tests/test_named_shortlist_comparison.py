import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from experiments.compare_named_origin_shortlists import compare_named_case, load_named_cases


class NamedShortlistTests(unittest.TestCase):
    def test_natural_panel_has_no_user_coordinates(self):
        cases=load_named_cases('data/named_origin_shortlist_4.json')
        self.assertEqual(len(cases),4)
        self.assertTrue(all('latitude' not in c and 'longitude' not in c for c in cases))

    def test_one_matrix_compares_identical_12_prefix_to_50(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        db=Path(temp.name)/'places.sqlite'
        con=sqlite3.connect(db)
        con.execute('CREATE TABLE places (source_id TEXT,name TEXT,category TEXT,district TEXT,latitude REAL,longitude REAL,name_norm TEXT,district_norm TEXT)')
        con.execute('INSERT INTO places VALUES (?,?,?,?,?,?,?,?)',
                    ('node/1','Sofitel Abidjan Hôtel Ivoire','hotel','',5.33,-4,'sofitel abidjan hotel ivoire',''))
        con.execute('INSERT INTO places VALUES (?,?,?,?,?,?,?,?)',
                    ('node/20','Abidjan Café','cafe','',5.33,-4,'abidjan cafe',''))
        for i in range(16):
            con.execute('INSERT INTO places VALUES (?,?,?,?,?,?,?,?)',
                        (f'node/{i+2}',f'Restaurant {i}','restaurant','',5.331+i*.0001,-4,
                         f'restaurant {i}',''))
        con.commit();con.close()
        matrix=Mock(return_value={'status':'ok','distances_m':[100+i*10 for i in range(12)]+[50,260,270,280],
                                  'durations_s':[100]*16})
        case={'id':'NS01','question':"Je suis à l'hôtel Sofitel, quel restaurant est le plus proche ?",
              'human_expectation':'Comparer les itinéraires.'}
        public,private=compare_named_case(case,db,'SECRET',matrix_service=matrix)
        self.assertEqual(public['status'],'ok')
        self.assertEqual(public['nearest_regret_m'],50)
        self.assertEqual(public['wide_top3_missing_from_short'],1)
        self.assertEqual(len(private['short_top3']),3)
        self.assertEqual(private['wide_top3'][0]['distance_m'],50)
        self.assertNotIn('origin',public)
        self.assertNotIn('SECRET',json.dumps(public))
        matrix.assert_called_once()
        with patch('experiments.compare_named_origin_shortlists.compare_case',return_value=({'status':'ok'},{'status':'ok'})) as compare:
            compare_named_case({'id':'NS03','question':'Depuis Abidjan Café, quel bar est le plus proche à pied ?',
                                'human_expectation':'Bar depuis café.'},db,'SECRET')
        self.assertEqual(compare.call_args.args[0]['category'],'bar')


if __name__=='__main__':unittest.main()
