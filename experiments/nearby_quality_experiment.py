"""Evaluate a conservative quality-aware nearby top three without changing the agent."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from experiments.audit_place_quality import generic_name, name_words, similar_name
from experiments.benchmark_reporting import write_json
from experiments.compare_nearby_shortlists import load_cases, route_ranking
from experiments.nearby_places import MAX_CANDIDATES, MAX_COMPARISON_CANDIDATES, air_distance_km, candidates
from experiments.route_service import load_route_key, matrix

MAX_EXTRA_METERS=250
MAX_EXTRA_RATIO=.25


def repetitive(place, selected):
    for _,_,other in selected:
        if name_words(place['name'])==name_words(other['name']):
            return True
        if (similar_name(place['name'],other['name'])
                and air_distance_km((place['latitude'],place['longitude']),
                                    (other['latitude'],other['longitude']))<=.075):
            return True
    return False


def quality_top3(places, distances):
    """Always retain nearest. Replace only generic/repetitive later slots within budget."""
    ranked=route_ranking(places,distances,top=len(places))
    if not ranked:return []
    selected=[ranked[0]]
    while len(selected)<min(3,len(ranked)):
        available=[row for row in ranked if row[1] not in {r[1] for r in selected}]
        baseline=available[0]
        chosen=baseline
        if generic_name(baseline[2]['name']) or repetitive(baseline[2],selected):
            max_distance=baseline[0]+min(MAX_EXTRA_METERS,baseline[0]*MAX_EXTRA_RATIO)
            chosen=next((row for row in available
                         if row[0]<=max_distance and not generic_name(row[2]['name'])
                         and not repetitive(row[2],selected)),baseline)
        selected.append(chosen)
    return sorted(selected,key=lambda row:(row[0],row[1]))


def pair_count(rows):
    return sum(similar_name(a[2]['name'],b[2]['name']) and
               air_distance_km((a[2]['latitude'],a[2]['longitude']),
                               (b[2]['latitude'],b[2]['longitude']))<=.075
               for i,a in enumerate(rows) for b in rows[i+1:])


def metrics(baseline,selected):
    return {'displayed':len(selected),
            'generic_names':sum(generic_name(p['name']) for _,_,p in selected),
            'repetitive_close_pairs':pair_count(selected),
            'rank_distance_extra_m':[round(selected[i][0]-baseline[i][0],1)
                                     for i in range(min(len(baseline),len(selected)))],
            'nearest_preserved':not baseline or baseline[0][1]==selected[0][1]}


def evaluate_case(case,db,key,matrix_service=matrix):
    places,total=candidates(db,case['origin'],case['category'],limit=MAX_COMPARISON_CANDIDATES)
    row={'id':case['id'],'category':case['category'],'mode':case['mode'],
         'matching_in_radius':total,'candidate_count':len(places),'status':'no_candidates'}
    detail=dict(row)
    if not places:return row,detail
    result=matrix_service(case['origin'],[(p['latitude'],p['longitude']) for p in places],
                          case['mode'],key,timeout=20)
    row['status']=detail['status']=result['status']
    if result['status']!='ok':
        row['reason']=detail['reason']=result.get('reason','unknown')
        return row,detail
    distances=result.get('distances_m',[])
    if len(distances)!=len(places):
        row['status']=detail['status']='invalid_response'
        return row,detail
    for limit,label in ((MAX_CANDIDATES,'12'),(MAX_COMPARISON_CANDIDATES,'50')):
        current=places[:limit];values=distances[:limit]
        baseline=route_ranking(current,values)
        proposed=quality_top3(current,values)
        row[label]={'baseline':metrics(baseline,baseline),
                    'proposed':metrics(baseline,proposed)}
        detail[label+'_top3']={'baseline':[{'source_id':p['source_id'],'name':p['name'],'distance_m':d}
                                    for d,_,p in baseline],
                       'proposed':[{'source_id':p['source_id'],'name':p['name'],'distance_m':d}
                                    for d,_,p in proposed]}
    detail['metrics']={label:row[label] for label in ('12','50')}
    return row,detail


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',default='data/nearby_shortlist_comparison_8.json')
    parser.add_argument('--db',default='local_data/lieux.sqlite')
    parser.add_argument('--out',required=True)
    args=parser.parse_args(argv)
    cases=load_cases(args.cases)
    if not Path(args.db).is_file():parser.error('POI database does not exist')
    key=load_route_key()
    if not key:parser.error('ORS_API_KEY is missing from environment or .env')
    out=Path(args.out)
    if out.exists():parser.error('Output directory already exists; choose a new directory')
    out.mkdir(parents=True)
    public={'kind':'development_nearby_quality_comparison',
            'created_at':datetime.now(timezone.utc).isoformat(),'candidate_limits':[12,50],
            'policy':{'nearest_preserved':True,'maximum_extra_m':MAX_EXTRA_METERS,
                      'maximum_extra_ratio':MAX_EXTRA_RATIO},
            'caveat':'Development-only name heuristic. No establishments verified or deduplicated. Eight purposive locations, historical 2022 POIs; manual review required.',
            'results':[]}
    private={'kind':public['kind'],'results':[]}
    for case in cases:
        row,detail=evaluate_case(case,args.db,key)
        public['results'].append(row);private['results'].append(detail)
        write_json(out/'report.json',public)
        write_json(out/'review.private.json',private)
        if row['status']=='unavailable':break
    print(json.dumps({'completed':len(public['results']),'planned':len(cases),
                      'report':str(out/'report.json'),'private_review':str(out/'review.private.json')},ensure_ascii=False))


if __name__=='__main__':main()
