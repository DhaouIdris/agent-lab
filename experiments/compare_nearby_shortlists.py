"""Development diagnostic: compare two route rankings from one ORS matrix response."""
import argparse
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from experiments.benchmark_reporting import write_json
from experiments.nearby_places import CATEGORIES, MAX_CANDIDATES, MAX_COMPARISON_CANDIDATES, RADIUS_KM, air_distance_km, candidates
from experiments.route_service import load_route_key, matrix, valid_coordinates


def load_cases(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data,list) or not 1<=len(data)<=20:
        raise ValueError('Expected 1 to 20 development cases')
    ids=set()
    for case in data:
        if (not isinstance(case,dict) or not isinstance(case.get('id'),str)
                or not re.fullmatch(r'[A-Z0-9_-]{1,24}',case['id']) or case['id'] in ids
                or case.get('category') not in CATEGORIES or case.get('mode') not in ('walk','car')
                or not valid_coordinates(case.get('origin'))):
            raise ValueError('Invalid comparison case')
        ids.add(case['id'])
    return data


def route_ranking(places, distances, top=3):
    rows=[(distance,place['source_id'],place) for place,distance in zip(places,distances)
          if type(distance) in (int,float) and math.isfinite(distance) and distance>=0]
    return sorted(rows,key=lambda r:(r[0],r[1]))[:top]


def duplicate_candidates(places):
    """Conservative same/similar name and position signal; never merge POIs."""
    def words(name):
        normalized=unicodedata.normalize('NFKD',name.casefold())
        return set(re.findall(r'[a-z0-9]+',''.join(c for c in normalized if not unicodedata.combining(c))))
    pairs=[]
    for i,a in enumerate(places):
        for b in places[i+1:]:
            first,second=words(a['name']),words(b['name'])
            if (first and second and len(first&second)>=min(2,len(first),len(second))
                    and len(first&second)/max(len(first),len(second))>=.75
                    and air_distance_km((a['latitude'],a['longitude']),
                                        (b['latitude'],b['longitude']))<=.075):
                pairs.append({'first_id':a['source_id'],'first_name':a['name'],
                              'second_id':b['source_id'],'second_name':b['name']})
    return pairs


def compare_case(case,db,api_key,matrix_service=matrix):
    places,total=candidates(db,case['origin'],case['category'],limit=MAX_COMPARISON_CANDIDATES)
    public={'id':case['id'],'category':case['category'],'mode':case['mode'],
            'matching_in_radius':total,'candidate_count':len(places),
            'status':'no_candidates' if not places else 'pending'}
    private=dict(public)
    if not places:
        return public,private
    result=matrix_service(case['origin'],[(p['latitude'],p['longitude']) for p in places],
                          case['mode'],api_key,timeout=20)
    public['status']=private['status']=result['status']
    if result['status']!='ok':
        public['reason']=private['reason']=result.get('reason','unknown')
        return public,private
    if (len(result['distances_m'])!=len(places) or len(result['durations_s'])!=len(places)):
        public['status']=private['status']='invalid_response'
        return public,private
    short=route_ranking(places[:MAX_CANDIDATES],result['distances_m'][:MAX_CANDIDATES])
    wide=route_ranking(places,result['distances_m'])
    reachable=sum(type(d) in (int,float) and math.isfinite(d) and d>=0
                  for d in result['distances_m'])
    # Every untested candidate is at least as far in a straight line as the
    # last candidate. This is a lower bound, never a displayed route distance.
    boundary_m=(air_distance_km(case['origin'],
                                (places[-1]['latitude'],places[-1]['longitude']))*1000
                if total>len(places) else None)
    def certified(rank):
        return (len(wide)>=rank and reachable==len(places)
                and wide[rank-1][0]<RADIUS_KM*1000
                and (boundary_m is None or boundary_m>wide[rank-1][0]))
    short_ids={r[1] for r in short};wide_ids={r[1] for r in wide}
    duplicates=duplicate_candidates(places)
    public.update({'reachable_candidates':reachable,
                   'top3_overlap':len(short_ids&wide_ids),
                   'wide_top3_missing_from_short':len(wide_ids-short_ids),
                   'nearest_regret_m':round(short[0][0]-wide[0][0],1) if short and wide else None,
                   'nearest_bounded_in_catalogue':certified(1),
                   'top3_bounded_in_catalogue':certified(3),
                   'untested_air_distance_lower_bound_m':round(boundary_m,1) if boundary_m is not None else None,
                   'possible_duplicate_pairs':len(duplicates)})
    private.update(public)
    private['short_top3']=[{'source_id':p['source_id'],'name':p['name'],'distance_m':d}
                           for d,_,p in short]
    private['wide_top3']=[{'source_id':p['source_id'],'name':p['name'],'distance_m':d}
                          for d,_,p in wide]
    private['possible_duplicates']=duplicates
    return public,private


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',default='data/nearby_shortlist_comparison_8.json')
    parser.add_argument('--db',default='local_data/lieux.sqlite')
    parser.add_argument('--out',required=True)
    args=parser.parse_args(argv)
    cases=load_cases(args.cases)
    db=Path(args.db)
    if not db.is_file():parser.error('POI database does not exist')
    key=load_route_key()
    if not key:parser.error('ORS_API_KEY is missing from environment or .env')
    out=Path(args.out)
    if out.exists():parser.error('Output directory already exists; choose a new directory')
    out.mkdir(parents=True)
    public={'kind':'development_nearby_shortlist_comparison','created_at':datetime.now(timezone.utc).isoformat(),
            'candidate_limits':[12,50],'radius_km':10,
            'caveat':'The 50-candidate result is not a global nearest-neighbor oracle. Synthetic locations, incomplete historical 2022 POIs, development-only cases; flagged duplicates need manual review.',
            'results':[]}
    private={'kind':public['kind'],'results':[]}
    for case in cases:
        row,detail=compare_case(case,db,key)
        public['results'].append(row);private['results'].append(detail)
        # Preserve completed cases if ORS becomes unavailable during the campaign.
        write_json(out/'report.json',public)
        write_json(out/'review.private.json',private)
        if row['status']=='unavailable':break
    print(json.dumps({'completed':len(public['results']),'planned':len(cases),
                      'report':str(out/'report.json'),'private_review':str(out/'review.private.json')},ensure_ascii=False))


if __name__=='__main__':
    main()
