"""One-off, cached comparison of three public geocoders against published hotel positions."""
import argparse
import hashlib
import json
import math
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from experiments.benchmark_reporting import write_json
from experiments.place_origin import _NoRedirect
from experiments.route_service import load_route_key, valid_coordinates

PROVIDERS=('pelias','nominatim','photon')
USER_AGENT='agent-lab-geocoder-comparison/0.1 (+https://github.com/DhaouIdris/agent-lab)'
ENDPOINTS={'pelias':'https://api.heigit.org/pelias/v1/search',
           'nominatim':'https://nominatim.openstreetmap.org/search',
           'photon':'https://photon.komoot.io/api/'}


def load_cases(path):
    raw=Path(path).read_bytes()
    cases=json.loads(raw.decode('utf-8-sig'))
    if not isinstance(cases,list) or not 1<=len(cases)<=12:
        raise ValueError('Expected 1..12 reference places')
    ids=set()
    for case in cases:
        if (not isinstance(case,dict) or set(case)!={'id','name','address','reference_lat','reference_lon','reference_url'}
                or not isinstance(case['id'],str) or not case['id'].isalnum() or case['id'] in ids
                or any(not isinstance(case[key],str) or not 5<=len(case[key])<=200 for key in ('name','address'))
                or not case['reference_url'].startswith('https://')
                or not valid_coordinates((case['reference_lat'],case['reference_lon']))):
            raise ValueError('Invalid reference place')
        ids.add(case['id'])
    return cases,hashlib.sha256(raw).hexdigest()


def haversine_m(origin,point):
    a,b=map(math.radians,origin);c,d=map(math.radians,point)
    h=math.sin((c-a)/2)**2+math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 12742000*math.asin(min(1,math.sqrt(h)))


def request_for(provider,query,key):
    if provider=='pelias':
        params={'text':query,'boundary.country':'CIV','size':3}
        headers={'Authorization':key,'Accept':'application/json','User-Agent':USER_AGENT}
    elif provider=='nominatim':
        params={'q':query,'format':'jsonv2','countrycodes':'ci','limit':3,'addressdetails':1}
        headers={'Accept':'application/json','User-Agent':USER_AGENT}
    elif provider=='photon':
        params={'q':query,'countrycode':'CI','limit':3,'lang':'fr'}
        headers={'Accept':'application/json','User-Agent':USER_AGENT}
    else:
        raise ValueError('Unknown provider')
    return urllib.request.Request(ENDPOINTS[provider]+'?'+urllib.parse.urlencode(params),headers=headers)


def parse_candidates(provider,data):
    records=data if provider=='nominatim' else data['features']
    if not isinstance(records,list):raise ValueError('Invalid geocoder response')
    candidates=[]
    for item in records[:3]:
        try:
            if provider=='nominatim':
                lat,lon=float(item['lat']),float(item['lon'])
                label=item['display_name'];kind=item.get('addresstype') or item.get('type')
                match_type=None;confidence=None
            else:
                prop=item['properties'];lon,lat=item['geometry']['coordinates'][:2]
                if provider=='pelias':
                    label=prop.get('label')
                else:
                    label=prop.get('name') or ' '.join(str(prop.get(k,'')) for k in
                        ('housenumber','street','city')).strip()
                kind=prop.get('layer') if provider=='pelias' else prop.get('osm_value')
                match_type=prop.get('match_type') if provider=='pelias' else None
                confidence=prop.get('confidence') if provider=='pelias' else None
            if (not valid_coordinates((lat,lon)) or not isinstance(label,str)
                    or not 1<=len(label)<=300):continue
            candidates.append({'label':label,'lat':lat,'lon':lon,
                               'kind':kind if isinstance(kind,str) else None,
                               'match_type':match_type if isinstance(match_type,str) else None,
                               'confidence':confidence if type(confidence) in (int,float)
                               and math.isfinite(confidence) else None})
        except (KeyError,IndexError,TypeError,ValueError):
            continue
    return candidates


def lookup(provider,query,key,opener=None):
    if provider=='pelias' and not key:return {'status':'missing_key','candidates':[]}
    req=request_for(provider,query,key)
    try:
        with (opener or urllib.request.build_opener(_NoRedirect())).open(req,timeout=8) as response:
            raw=response.read(1000001)
        if len(raw)>1000000:return {'status':'oversized_response','candidates':[]}
        candidates=parse_candidates(provider,json.loads(raw))
        return {'status':'results' if candidates else 'empty','candidates':candidates}
    except urllib.error.HTTPError as exc:
        return {'status':'rate_limited' if exc.code==429 else 'http_error','http_status':exc.code,'candidates':[]}
    except (urllib.error.URLError,TimeoutError,OSError):
        return {'status':'transport_error','candidates':[]}
    except (ValueError,KeyError,TypeError):
        return {'status':'invalid_response','candidates':[]}


def summarize(rows):
    summary={}
    for provider in PROVIDERS:
        summary[provider]={}
        for variant in ('address','name_and_address'):
            subset=[r for r in rows if r['provider']==provider and r['variant']==variant]
            distances=[r['top1_error_m'] for r in subset if r['top1_error_m'] is not None]
            summary[provider][variant]={
                'completed':len(subset),'with_result':len(distances),
                'within_100m':sum(x<=100 for x in distances),
                'within_250m':sum(x<=250 for x in distances),
                'over_1km':sum(x>1000 for x in distances),
                'median_error_m':round(statistics.median(distances)) if distances else None,
                'provider_errors':sum(r['status'] not in ('results','empty') for r in subset)}
    return summary


def run(cases,source_hash,out,providers,key,lookup_fn=lookup,clock=time.monotonic,sleep=time.sleep):
    out=Path(out);review_path=out/'review.private.json';report_path=out/'report.json'
    if out.exists():
        if not review_path.is_file():raise ValueError('Existing output has no private review; choose another folder')
        review=json.loads(review_path.read_text(encoding='utf-8-sig'))
        if review.get('cases_sha256')!=source_hash or review.get('providers')!=list(providers):
            raise ValueError('Case set or providers changed; choose another folder')
    else:
        out.mkdir(parents=True)
        review={'kind':'development_geocoder_comparison_pending_human_review',
                'cases_sha256':source_hash,'created_at':datetime.now(timezone.utc).isoformat(),
                'providers':list(providers),'rows':[]}
    review['stop_reason']=None
    done={(r['id'],r['variant'],r['provider']) for r in review['rows']}
    last_nominatim=None
    for case in cases:
        for variant,query in (('address',case['address']),('name_and_address',case['name']+', '+case['address'])):
            for provider in providers:
                if (case['id'],variant,provider) in done:continue
                if provider=='nominatim' and last_nominatim is not None:
                    sleep(max(0,1.2-(clock()-last_nominatim)))
                if provider=='nominatim':last_nominatim=clock()
                result=lookup_fn(provider,query,key)
                reference=(case['reference_lat'],case['reference_lon'])
                candidates=[]
                for candidate in result['candidates']:
                    candidate=dict(candidate)
                    candidate['error_m']=round(haversine_m(reference,(candidate['lat'],candidate['lon'])))
                    candidates.append(candidate)
                review['rows'].append({'id':case['id'],'provider':provider,'variant':variant,
                    'query':query,'reference':{'lat':reference[0],'lon':reference[1],
                    'source':case['reference_url']},'status':result['status'],
                    'http_status':result.get('http_status'),'candidates':candidates,
                    'human_verdict':None})
                done.add((case['id'],variant,provider))
                if result['status'] not in ('results','empty'):
                    review['stop_reason']=provider+': '+result['status']
                write_json(review_path,review)
                write_report(report_path,review,cases,providers)
                if review['stop_reason']:
                    return write_report(report_path,review,cases,providers)
    return write_report(report_path,review,cases,providers)


def write_report(path,review,cases,providers):
    rows=[{'id':r['id'],'provider':r['provider'],'variant':r['variant'],'status':r['status'],
           'candidate_count':len(r['candidates']),
           'top1_error_m':r['candidates'][0]['error_m'] if r['candidates'] else None}
          for r in review['rows']]
    report={'kind':review['kind'],'cases_sha256':review['cases_sha256'],
            'planned':len(cases)*2*len(providers),'completed':len(rows),
            'campaign_complete':len(rows)==len(cases)*2*len(providers),
            'stop_reason':review.get('stop_reason'),
            'summary':summarize(rows),'results':rows,
            'attribution':'© OpenStreetMap contributors, ODbL 1.0; https://www.openstreetmap.org/copyright',
            'human_adjudication':'pending',
            'caveat':'One provider group supplies all reference positions. Distance to a hotel coordinate is not proof of identity or routable entrance. Top-1 metrics include missing results in the denominator; human review is required. No claims about nationwide coverage.'}
    write_json(path,report)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',default='data/geocoding_reference_8.json')
    p.add_argument('--out',required=True)
    p.add_argument('--provider',choices=PROVIDERS,action='append',help='Repeat to select providers; default: all three')
    p.add_argument('--live',action='store_true',help='Actually query hosted geocoders; without this only validate cases')
    args=p.parse_args(argv)
    cases,source_hash=load_cases(args.cases)
    providers=list(dict.fromkeys(args.provider or PROVIDERS))
    if not args.live:
        print(json.dumps({'cases':len(cases),'variants':2,'providers':providers,
                          'planned_requests':len(cases)*2*len(providers),'live':False}))
        return
    key=load_route_key() if 'pelias' in providers else ''
    if 'pelias' in providers and not key:p.error('ORS_API_KEY missing from .env')
    try:report=run(cases,source_hash,args.out,providers,key)
    except ValueError as exc:p.error(str(exc))
    print(json.dumps({'completed':report['completed'],'planned':report['planned'],
                      'report':str(Path(args.out)/'report.json'),
                      'private_review':str(Path(args.out)/'review.private.json')},ensure_ascii=False))


if __name__=='__main__':main()
