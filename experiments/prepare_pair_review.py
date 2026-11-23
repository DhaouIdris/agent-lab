"""Make a bounded, varied manual review CSV from private development diagnostics."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from experiments.audit_place_quality import generic_name, name_words

HEADERS=['origin_case','first_id','first_name','first_category','second_id','second_name',
         'second_category','separation_m','manual_decision','notes']


def select_pairs(quality,comparison,limit=30):
    if not 1<=limit<=100:raise ValueError('limit must be 1..100')
    examples=quality.get('possible_same_place_examples',[])
    cases=comparison.get('results',[])
    if not isinstance(examples,list) or not isinstance(cases,list):raise ValueError('Invalid review inputs')
    indexed={frozenset((p['first_id'],p['second_id'])):p for p in examples}
    prioritized=[]
    for case in cases:
        ids={p['source_id'] for p in case.get('short_top3',[])}
        for pair in case.get('possible_duplicates',[]):
            key=frozenset((pair['first_id'],pair['second_id']))
            enriched=indexed.get(key,pair)
            generic=generic_name(pair['first_name']) and generic_name(pair['second_name'])
            prioritized.append((0 if key<=ids else 3 if generic else 1,case['id'],enriched))
    prioritized.extend((2,'',p) for p in examples)
    seen=set();signatures=Counter();out=[];generic_count=0
    for _,case_id,p in sorted(prioritized,key=lambda item:(item[0],item[1],item[2]['first_id'])):
        key=frozenset((p['first_id'],p['second_id']))
        signature=tuple(sorted((tuple(sorted(name_words(p['first_name']))),
                                tuple(sorted(name_words(p['second_name']))))))
        generic=generic_name(p['first_name']) and generic_name(p['second_name'])
        if key in seen or signatures[signature]>=2 or (generic and generic_count>=4):continue
        if generic:generic_count+=1
        seen.add(key);signatures[signature]+=1
        categories=p.get('categories',['',''])
        out.append(dict(zip(HEADERS,[case_id,p['first_id'],p['first_name'],categories[0],
                                     p['second_id'],p['second_name'],categories[1],
                                     p.get('separation_m',''),'',''])))
        if len(out)==limit:break
    return out


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quality-review',required=True)
    parser.add_argument('--comparison-review',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--limit',type=int,default=30)
    args=parser.parse_args(argv)
    out=Path(args.out)
    if out.exists():parser.error('Output file already exists; choose a new path')
    quality=json.loads(Path(args.quality_review).read_text(encoding='utf-8-sig'))
    comparison=json.loads(Path(args.comparison_review).read_text(encoding='utf-8-sig'))
    rows=select_pairs(quality,comparison,args.limit)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=HEADERS)
        writer.writeheader();writer.writerows(rows)
    print(json.dumps({'review_pairs':len(rows),'private_csv':str(out)}))


if __name__=='__main__':main()
