import json
import tempfile
import unittest
from pathlib import Path

from experiments.price_offers import load_prices,find_offers


class PriceOfferTests(unittest.TestCase):
    def test_budget_filters_dishes_without_implying_whole_day_cost(self):
        data=load_prices()
        result=find_offers(data,2000)
        self.assertTrue(result['offers'])
        self.assertTrue(all(x['amount_xof']<=2000 for x in result['offers']))
        self.assertTrue(all(x['catalogue_source_id'] is None for x in result['offers']))
        self.assertNotIn('SGCI_ART_CHILD',{x['id'] for x in result['offers']})
        self.assertIn('Delivery',result['caveat'])

    def test_indexed_museum_price_requires_explicit_inclusion(self):
        data=load_prices()
        normal=find_offers(data,5000,kind='museum')
        flagged=find_offers(data,5000,kind='museum',include_unconfirmed=True)
        self.assertEqual(normal['offers'],[])
        self.assertTrue(flagged['offers'])
        self.assertTrue(all(x['status']=='indexed_price_recheck_required' for x in flagged['offers']))

    def test_dated_free_event_only_on_its_announced_day(self):
        data=load_prices()
        event=find_offers(data,0,'dated_cultural_event',on_date='2026-11-28')
        self.assertEqual([x['id'] for x in event['offers']],['GOETHE_PLUME_ENTRY'])
        self.assertEqual(find_offers(data,0,'dated_cultural_event',on_date='2026-11-29')['offers'],[])

    def test_rejects_invented_catalogue_link_and_invalid_prices(self):
        data=load_prices()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'prices.json'
            data['sources'][0]['catalogue_source_id']='node/123'
            path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):load_prices(path)
            data['sources'][0]['catalogue_source_id']=None
            data['offers'][0]['amount_xof']=-1
            path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):load_prices(path)
