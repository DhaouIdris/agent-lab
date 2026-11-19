"""Compare the deployed input lexical guard against its previous baseline offline."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from experiments.injection_guard import inspect_passages
from experiments.input_guard import inspect_user_input


def evaluate(path):
    raw=Path(path).read_bytes(); cases=json.loads(raw.decode('utf-8-sig'))
    if not isinstance(cases,list) or not cases:raise ValueError('Invalid cases')
    rows=[];seen=set()
    for c in cases:
        if not isinstance(c,dict) or not isinstance(c.get('id'),str) or c['id'] in seen or c.get('label') not in ('malicious','benign') or not isinstance(c.get('text'),str) or not c['text'].strip():raise ValueError('Invalid case')
        seen.add(c['id']);text=c['text']
        rows.append({'id':c['id'],'label':c['label'],'baseline_blocked':bool(inspect_passages([{'id':'x','text':text}])), 'candidate_blocked':inspect_user_input(text)})
    def stats(k):
        tp=sum(x['label']=='malicious' and x[k] for x in rows);fn=sum(x['label']=='malicious' and not x[k] for x in rows)
        fp=sum(x['label']=='benign' and x[k] for x in rows);tn=sum(x['label']=='benign' and not x[k] for x in rows)
        return {'tp':tp,'fn':fn,'fp':fp,'tn':tn,'detection_rate':tp/(tp+fn) if tp+fn else None,'benign_block_rate':fp/(fp+tn) if fp+tn else None}
    return {'file':Path(path).name,'sha256':hashlib.sha256(raw).hexdigest(),'baseline':stats('baseline_blocked'),'candidate':stats('candidate_blocked'),'results':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cases',action='append');p.add_argument('--out');a=p.parse_args()
    paths=a.cases or ['data/injection_guard_dev.json','data/injection_guard_challenge.json','data/input_guard_scenarios.json']
    report={'kind':'offline_input_guard_comparison','sets':[evaluate(p) for p in paths],
       'caveat':'Project-authored examples and rules adapted from known cases; not independently annotated, not an unbiased or security guarantee. No provider or tool calls.'}
    out=Path(a.out) if a.out else Path('runs')/('input_guard_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    if out.exists():p.error('Output already exists')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps([{'file':s['file'],'baseline':s['baseline'],'candidate':s['candidate']} for s in report['sets']],ensure_ascii=False,indent=2));print('Rapport :',out)

if __name__=='__main__':main()
