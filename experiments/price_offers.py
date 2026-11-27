"""Read curated public price observations without merging uncertain OSM identities."""
import argparse
import json
from datetime import date
from pathlib import Path

DEFAULT=Path(__file__).resolve().parents[1]/'data'/'abidjan_price_offers_dev.json'
STATUSES={'published_price_unconfirmed_at_checkout','indexed_price_recheck_required','official_event_free_entry'}


def load_prices(path=DEFAULT):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    sources=data['sources'];offers=data['offers']
    if not isinstance(sources,list) or not isinstance(offers,list):raise ValueError('Invalid price collection')
    ids=set();offer_ids=set()
    for source in sources:
        if (not isinstance(source,dict) or not isinstance(source.get('id'),str) or source['id'] in ids or
                not isinstance(source.get('name'),str) or not source.get('url','').startswith('https://') or
                source.get('catalogue_source_id') is not None):
            raise ValueError('Invalid or unverified source identity')
        ids.add(source['id'])
    for offer in offers:
        if (not isinstance(offer,dict) or not isinstance(offer.get('id'),str) or offer['id'] in offer_ids or
                offer.get('source_id') not in ids or type(offer.get('amount_xof')) is not int or
                offer['amount_xof']<0 or offer['amount_xof']>1000000 or
                not isinstance(offer.get('label'),str) or not offer['label'].strip() or
                offer.get('status') not in STATUSES):
            raise ValueError('Invalid offer')
        if 'valid_on' in offer:
            try:date.fromisoformat(offer['valid_on'])
            except (ValueError,TypeError):raise ValueError('Invalid event date') from None
        offer_ids.add(offer['id'])
    return data


def find_offers(data,budget_fcfa=None,kind=None,include_unconfirmed=False,on_date=None):
    if budget_fcfa is not None and (type(budget_fcfa) is not int or budget_fcfa<0):raise ValueError('Invalid budget')
    sources={s['id']:s for s in data['sources']}
    if kind is not None and kind not in {'restaurant_delivery','museum','dated_cultural_event'}:raise ValueError('Invalid kind')
    today=date.fromisoformat(on_date) if on_date else date.today()
    results=[]
    for offer in data['offers']:
        source=sources[offer['source_id']]
        if kind and source['kind']!=kind:continue
        if 'valid_on' in offer and date.fromisoformat(offer['valid_on'])!=today:continue
        if budget_fcfa is not None and offer['amount_xof']>budget_fcfa:continue
        if not include_unconfirmed and source['access']=='indexed_page_only_recheck_required':continue
        results.append({**offer,'venue':source['name'],'locality':source['locality'],'source_url':source['url'],
                        'observed_at':data['checked_at'],'catalogue_source_id':None})
    return {'offers':results,'currency':'XOF','checked_at':data['checked_at'],
            'caveat':'Published prices are observations, not final bills. Delivery, service, transport and availability are unknown; no OSM identity match.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',default=str(DEFAULT));p.add_argument('--budget-fcfa',type=int)
    p.add_argument('--kind',choices=['restaurant_delivery','museum','dated_cultural_event'])
    p.add_argument('--on-date',help='ISO date, defaults to today')
    p.add_argument('--include-unconfirmed',action='store_true')
    a=p.parse_args()
    print(json.dumps(find_offers(load_prices(a.data),a.budget_fcfa,a.kind,a.include_unconfirmed,a.on_date),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
