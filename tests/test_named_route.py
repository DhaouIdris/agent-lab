import unittest
from unittest.mock import Mock, patch

from experiments.place_origin import named_route_request
from experiments.unified_agent import ask


QUESTION="Je suis à l'hotel lorenzo, comment se rendre au restaurant abbata ?"


class NamedRouteTests(unittest.TestCase):
    def test_extracts_only_explicit_pair(self):
        self.assertEqual(named_route_request(QUESTION),('hotel lorenzo','restaurant abbata'))
        self.assertIsNone(named_route_request('Comment aller au restaurant Abbata ?'))

    def test_resolves_both_and_uses_route_without_model(self):
        client=Mock()
        origin={'status':'ok','name':'Lorenzo lounge','location':(5.33,-4.02),
                'source':'catalogue','source_id':'node/6990037695'}
        destination={'status':'ok','name':'Abbata restaurant','location':(5.34,-4.01),
                     'source':'catalogue','source_id':'node/5319106421'}
        router=Mock(return_value={'status':'ok','distance_m':1750,'duration_s':1320,'source':'ORS'})
        with patch('experiments.unified_agent.local_origin',side_effect=[origin,destination]):
            result=ask(client,'unused',[],QUESTION,route_service=router)
        self.assertEqual(result['output']['place_ids'],['node/6990037695','node/5319106421'])
        self.assertIn('1.75 km',result['output']['answer'])
        self.assertIn('22 min',result['output']['answer'])
        self.assertIn('étapes de navigation',result['output']['answer'])
        self.assertEqual([x['tool'] for x in result['trace']],['resolve_origin','resolve_destination','calculate_route'])
        router.assert_called_once_with(origin['location'],destination['location'],'walk',12)
        client.chat.assert_not_called()

    def test_ambiguous_destination_never_calls_route(self):
        client=Mock();router=Mock()
        origin={'status':'ok','name':'Lorenzo lounge','location':(5.33,-4.02),'source':'catalogue'}
        destination={'status':'ambiguous','choices':[{'name':'Abbata A','district':'Cocody'},
                                                    {'name':'Abbata B','district':'Abidjan'}]}
        with patch('experiments.unified_agent.local_origin',side_effect=[origin,destination]):
            result=ask(client,'unused',[],QUESTION,route_service=router)
        self.assertEqual(result['guard_status'],'ambiguous_origin')
        router.assert_not_called();client.chat.assert_not_called()

    def test_missing_route_key_does_not_claim_distance(self):
        client=Mock();router=Mock(return_value={'status':'unavailable','reason':'missing_key'})
        origin={'status':'ok','name':'Lorenzo lounge','location':(5.33,-4.02),'source':'catalogue'}
        destination={'status':'ok','name':'Abbata restaurant','location':(5.34,-4.01),'source':'catalogue'}
        with patch('experiments.unified_agent.local_origin',side_effect=[origin,destination]):
            result=ask(client,'unused',[],QUESTION,route_service=router)
        self.assertTrue(result['output']['abstain'])
        self.assertNotIn('km',result['output']['answer'])
