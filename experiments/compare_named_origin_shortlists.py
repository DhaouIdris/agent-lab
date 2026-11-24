"""Compare 12 versus 50 route candidates from natural named-place questions."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from experiments.benchmark_reporting import write_json
from experiments.compare_nearby_shortlists import compare_case
from experiments.injection_guard import inspect_passages, normalize
from experiments.input_guard import inspect_user_input
from experiments.place_origin import named_origin_request, local_origin, geocode_origin
from experiments.route_service import load_route_key
from experiments.unified_agent import _NEARBY_CATEGORIES


def load_named_cases(path):
    cases=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if (not isinstance(cases,list) or not 1<=len(cases)<=20
            or any(not isinstance(c,dict) or set(c)!={'id','question','human_expectation'}
                   or not isinstance(c['id'],str) or not c['id'].isalnum()
                   or not isinstance(c['question'],str) or not 5<=len(c['question'])<=500
                   or re.search(r'-?\d+\.\d+\s*,\s*-?\d+\.\d+',c['question'])
                   or not isinstance(c['human_expectation'],str) or not c['human_expectation']
                   for c in cases)
            or len({c['id'] for c in cases})!=len(cases)):
        raise ValueError('Expected 1..20 distinct annotated natural questions')
    return cases


def compare_named_case(case,db,key,matrix_service=None,geocoder=geocode_origin):
    question=case['question']
    origin_name=named_origin_request(question)
    q=normalize(question)
    destination_clause=q.replace(normalize(origin_name),'',1) if origin_name else q
    category=next((category for pattern,category in _NEARBY_CATEGORIES if pattern.search(destination_clause)),None)
    mode='car' if 'en voiture' in q else 'walk'
    row={'id':case['id'],'status':'invalid_question'}
    if not origin_name or not category or inspect_user_input(question):return row,dict(row)
    resolved=local_origin(db,origin_name)
    if resolved['status']=='not_found':resolved=geocoder(origin_name,key,timeout=8)
    if resolved['status']!='ok':
        row['status']=resolved['status']
        return row,dict(row)
    if inspect_passages([{'id':'origin','text':resolved['name']} ]):
        row['status']='blocked_suspected_injection'
        return row,dict(row)
    route_case={'id':case['id'],'category':category,'mode':mode,'origin':resolved['location']}
    kwargs={'matrix_service':matrix_service} if matrix_service is not None else {}
    public,private=compare_case(route_case,db,key,**kwargs)
    public['origin_source']=resolved['source']
    private['origin_source']=resolved['source']
    private['origin_name']=resolved['name']
    private['question']=question
    private['human_expectation']=case['human_expectation']
    return public,private


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases',default='data/named_origin_shortlist_4.json')
    p.add_argument('--db',default='local_data/lieux.sqlite')
    p.add_argument('--out',required=True)
    a=p.parse_args(argv)
    cases=load_named_cases(a.cases)
    if not Path(a.db).is_file():p.error('Catalogue SQLite introuvable')
    key=load_route_key()
    if not key:p.error('ORS_API_KEY absente du fichier .env ou de l’environnement')
    out=Path(a.out)
    if out.exists():p.error('Dossier de sortie déjà présent')
    out.mkdir(parents=True)
    public={'kind':'development_named_origin_shortlist_comparison','created_at':datetime.now(timezone.utc).isoformat(),
            'candidate_limits':[12,50],'results':[],
            'caveat':'A 50-place shortlist is not an exhaustive nearest-place oracle. These authored cases need manual review.'}
    private={'kind':public['kind'],'results':[]}
    for case in cases:
        row,detail=compare_named_case(case,a.db,key)
        public['results'].append(row);private['results'].append(detail)
        write_json(out/'report.json',public)
        write_json(out/'review.private.json',private)
        if row['status']=='unavailable':break
    print(json.dumps({'completed':len(public['results']),'planned':len(cases),
                      'report':str(out/'report.json'),'private_review':str(out/'review.private.json')},ensure_ascii=False))


if __name__=='__main__':main()
