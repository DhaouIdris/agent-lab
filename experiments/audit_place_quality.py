"""Read-only quality audit of the historical POI catalogue, with private evidence."""
import argparse
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from experiments.benchmark_reporting import write_json
from experiments.nearby_places import air_distance_km
from experiments.route_service import valid_coordinates

GENERIC_WORDS={'hotel','cafe','cafeteria','kiosque','restaurant','bar','buvette',
               'glacier','fast','food','snack','resto','point','de','du','la','le','les'}
NEARBY_METERS=75
PRIVATE_LIMIT=100


def name_words(name):
    normalized=unicodedata.normalize('NFKD',name.casefold())
    plain=''.join(c for c in normalized if not unicodedata.combining(c))
    return set(re.findall(r'[a-z0-9]+',plain))


def generic_name(name):
    words=name_words(name)
    return bool(words) and words<=GENERIC_WORDS


def similar_name(a,b):
    left,right=name_words(a),name_words(b)
    return bool(left and right and len(left&right)>=min(2,len(left),len(right))
                and len(left&right)/max(len(left),len(right))>=.75)


def close_pairs(places):
    """Cell lookup narrows candidates; final distance is computed using coordinates."""
    cells=defaultdict(list)
    for place in places:
        if not valid_coordinates((place['latitude'],place['longitude'])):continue
        lat,lon=place['latitude'],place['longitude']
        # 0.005 degrees safely exceeds 75 m along both axes inside Côte d'Ivoire.
        cell=(math.floor(lat/.005),math.floor(lon/.005))
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                for other in cells[(cell[0]+dy,cell[1]+dx)]:
                    distance=air_distance_km((lat,lon),(other['latitude'],other['longitude']))*1000
                    if distance<=NEARBY_METERS:
                        yield other,place,distance
        cells[cell].append(place)


def read_places(db):
    if not Path(db).is_file():raise ValueError('POI database does not exist')
    con=sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    try:
        return [dict(r) for r in con.execute(
            'SELECT source_id,name,category,district,latitude,longitude FROM places ORDER BY source_id')]
    finally:
        con.close()


def audit(places,review=None):
    public={'kind':'development_poi_quality_audit','created_at':datetime.now(timezone.utc).isoformat(),
            'scope':'all imported POIs; historical source, current activity unverified',
            'threshold_m':NEARBY_METERS,'total_places':len(places),'categories':{},
            'caveat':'Name similarity and physical proximity flag possible duplicates, not confirmed identical establishments. Generic labels are not necessarily erroneous. Do not merge without source review.'}
    private={'kind':public['kind'],'generic_examples':[],'possible_same_place_examples':[],
             'generic_nearby_pair_examples':[],'different_name_same_coordinate_examples':[],
             'review_cases':[]}
    categories=defaultdict(Counter)
    generic_ids=set()
    for p in places:
        counts=categories[p['category']]
        counts['total']+=1
        if not str(p.get('district') or '').strip():counts['missing_district']+=1
        if generic_name(p['name']):
            counts['generic_name']+=1;generic_ids.add(p['source_id'])
            if len(private['generic_examples'])<PRIVATE_LIMIT:
                private['generic_examples'].append({k:p[k] for k in ('source_id','name','category')})
        if not valid_coordinates((p['latitude'],p['longitude'])):
            counts['invalid_coordinate']+=1
    for category,counts in sorted(categories.items()):
        public['categories'][category]=dict(counts)
        for field in ('missing_district','generic_name','invalid_coordinate'):
            public['categories'][category].setdefault(field,0)

    matched_ids=set(); pair_counts=Counter(); same_place_pairs=set()
    for a,b,distance in close_pairs(places):
        same_coords=distance<.01
        similar=similar_name(a['name'],b['name'])
        pair={'first_id':a['source_id'],'first_name':a['name'],
              'second_id':b['source_id'],'second_name':b['name'],
              'categories':[a['category'],b['category']], 'separation_m':round(distance,1)}
        if similar:
            kind='generic_nearby_pair' if generic_name(a['name']) and generic_name(b['name']) else 'possible_same_place'
            pair_counts[kind]+=1
            matched_ids.update((a['source_id'],b['source_id']))
            if kind=='possible_same_place':
                same_place_pairs.add(frozenset((a['source_id'],b['source_id'])))
            field=kind+'_examples'
            if len(private[field])<PRIVATE_LIMIT:private[field].append(pair)
        elif same_coords:
            pair_counts['different_name_same_coordinate']+=1
            if len(private['different_name_same_coordinate_examples'])<PRIVATE_LIMIT:
                private['different_name_same_coordinate_examples'].append(pair)
    public['nearby_pair_counts']={key:pair_counts[key] for key in (
        'possible_same_place','generic_nearby_pair','different_name_same_coordinate')}
    public['places_in_similar_nearby_pairs']=len(matched_ids)

    if review is not None:
        if not isinstance(review,dict) or not isinstance(review.get('results'),list):
            raise ValueError('Expected comparison review with results')
        for case in review['results']:
            top=case.get('short_top3',[])
            if not isinstance(top,list):raise ValueError('Invalid top three')
            ids=[p['source_id'] for p in top]
            flagged=[{'source_id':p['source_id'],'name':p['name']} for p in top
                     if p['source_id'] in generic_ids]
            near_pairs=[sorted(pair) for pair in same_place_pairs if pair<=set(ids)]
            public.setdefault('review_impact',[]).append({
                'id':case['id'],'displayed_count':len(ids),'generic_displayed':len(flagged),
                'possible_same_place_pairs_in_top3':len(near_pairs)})
            private['review_cases'].append({'id':case['id'],'generic_displayed':flagged,
                                            'possible_same_place_pairs_in_top3':near_pairs})
    return public,private


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='local_data/lieux.sqlite')
    parser.add_argument('--review',help='Optional review.private.json from shortlist comparison')
    parser.add_argument('--out',required=True)
    args=parser.parse_args(argv)
    places=read_places(args.db)
    review=json.loads(Path(args.review).read_text(encoding='utf-8-sig')) if args.review else None
    public,private=audit(places,review)
    out=Path(args.out)
    if out.exists():parser.error('Output directory already exists; choose a new directory')
    out.mkdir(parents=True)
    write_json(out/'report.json',public)
    write_json(out/'review.private.json',private)
    print(json.dumps({'places_audited':len(places),'report':str(out/'report.json'),
                      'private_review':str(out/'review.private.json')},ensure_ascii=False))


if __name__=='__main__':
    main()
