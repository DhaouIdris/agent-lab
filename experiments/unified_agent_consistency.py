"""Repeat independent agent questions to diagnose variable execution (not answer quality)."""
import argparse
import getpass
import hashlib
import json
import os
import platform
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ci_agentlab.providers import ChatClient
from experiments.document_rag import load_corpus
from experiments.unified_agent_batch import run
from experiments.benchmark_reporting import save_report
from experiments.model_config import load_model_config
from experiments.model_credentials import model_key


def campaign(client, db, docs, cases, repeat=2, timeout=180, on_progress=None):
    rows=[]
    stop_reason=None
    # Interleave cases across repetitions so results are not grouped by time.
    for repetition in range(1, repeat+1):
        for case in cases:
            result=run(client, db, docs, [case], timeout=timeout)['results'][0]
            result['repetition']=repetition
            rows.append(result)
            if on_progress:
                on_progress(rows)
            if result['status']=='execution_error' and result.get('diagnostic_code') in (None,'provider_error','turn_deadline_exceeded'):
                stop_reason='provider_or_deadline_error'
                break
        if stop_reason:
            break
    by_case=[]
    for case in cases:
        matches=[x for x in rows if x['id']==case['id']]
        by_case.append({'id':case['id'],'runs':len(matches),
            'statuses':dict(Counter(x['status'] for x in matches)),
            'diagnostic_codes':dict(Counter(x['diagnostic_code'] for x in matches if x.get('diagnostic_code'))),
            'model_outputs':sum(x['status']=='model_output' and x.get('response_origin')!='route_service' for x in matches),
            'abstentions':sum(x.get('output',{}).get('abstain') is True for x in matches if isinstance(x.get('output'),dict)),
            'tool_sequences':[x.get('observed_tools') for x in matches]})
    categories={}
    for row in rows:
        category=row.get('category') or 'unspecified'
        item=categories.setdefault(category,{'runs':0,'outcome_checks_evaluable':0,'outcome_checks_passes':0,'execution_errors':0})
        item['runs']+=1
        item['outcome_checks_evaluable']+=int('outcome_checks_pass' in row)
        item['outcome_checks_passes']+=int(row.get('outcome_checks_pass') is True)
        item['execution_errors']+=int(row['status']=='execution_error')
    return {'kind':'agent_consistency_development_pending_human_review',
        'campaign_complete':stop_reason is None and len(rows)==len(cases)*repeat,
        'stop_reason':stop_reason,
        'summary':{'distinct_scenarios':len(cases),'repetitions_planned':repeat,
            'runs_planned':len(cases)*repeat,'runs_completed':len(rows),
            'model_outputs':sum(x['status']=='model_output' and x.get('response_origin')!='route_service' for x in rows),
            'execution_errors':sum(x['status']=='execution_error' for x in rows),
            'guard_blocks':sum(x['status']=='blocked_suspected_injection' for x in rows),
            'invalid_coordinates':sum(x['status']=='invalid_coordinates' for x in rows),
            'automatic_checks_passes':sum(x.get('automatic_checks_pass') is True for x in rows),
            'human_success_rate':None,'outcome_checks_evaluable':sum('outcome_checks_pass' in x for x in rows),
            'outcome_checks_passes':sum(x.get('outcome_checks_pass') is True for x in rows),
            'provider_attempts':sum(len(x.get('provider_calls',[])) for x in rows),
            'cost':None},'per_category':categories,'per_case':by_case,'results':rows,
        'caveat':'Repeated development cases are not independent or representative. A model output or matching tool selection is not proof of a correct, useful, safe, or consistent answer; review responses and sources manually.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-review',action='store_true');p.add_argument('--db',required=True);p.add_argument('--cases',required=True)
    p.add_argument('--corpus',default='data/rag_integrated_dev.json');p.add_argument('--config',default='model.json')
    p.add_argument('--repeat',type=int,default=2);p.add_argument('--case',action='append');p.add_argument('--out')
    a=p.parse_args()
    if not 1<=a.repeat<=5:p.error('repeat must be between 1 and 5')
    db=Path(a.db);corpus=Path(a.corpus);casefile=Path(a.cases)
    if not db.is_file():p.error('Catalogue database missing')
    docs=load_corpus(corpus);cases=json.loads(casefile.read_text(encoding='utf-8-sig'))
    allowed={'search_catalogue','search_documents','calculate_route'}
    if not isinstance(cases,list) or not 1<=len(cases)<=10 or any(not isinstance(c,dict) or not isinstance(c.get('id'),str) or not c['id'] or not isinstance(c.get('question'),str) or not c['question'].strip() or len(c['question'])>2000 or not isinstance(c.get('human_expectation'),str) or not isinstance(c.get('required_tools'),list) or any(t not in allowed for t in c['required_tools']) for c in cases) or len({c['id'] for c in cases})!=len(cases):p.error('Invalid cases')
    if a.case:
        selected=set(a.case)
        if len(selected)!=len(a.case) or not selected <= {c['id'] for c in cases}:p.error('Unknown or duplicate case IDs')
        cases=[c for c in cases if c['id'] in selected]
    out=Path(a.out) if a.out else Path('runs')/('consistency_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    if out.exists():p.error('Result directory exists')
    cfg=load_model_config(a.config)
    try:key=model_key(cfg)
    except ValueError as exc:p.error(str(exc))
    max_calls=5*len(cases)*a.repeat
    client=ChatClient(cfg['base_url'],cfg['deployment'],api_key=key,api_version=cfg.get('api_version'),max_output_tokens=cfg['max_output_tokens'],max_calls=max_calls,auth_header=cfg['auth_header'],token_parameter=cfg['token_parameter'],min_interval_seconds=cfg['min_interval_seconds'])
    out.mkdir(parents=True,exist_ok=False)
    def checkpoint(rows):
        save_report(out,{'kind':'partial','campaign_complete':False,'results':rows},a.private_review)
        row=rows[-1];print(f"{row['id']} repeat={row['repetition']}: {row['status']}",flush=True)
    report=campaign(client,db,docs,cases,repeat=a.repeat,timeout=cfg['turn_timeout_seconds'],on_progress=checkpoint)
    report['config']={'model':cfg.get('underlying_model',cfg['deployment']),'model_version':cfg.get('model_version'),'max_provider_calls':max_calls,
        'max_output_tokens':cfg['max_output_tokens'], 'python_version':platform.python_version(),
        'corpus_sha256':hashlib.sha256(corpus.read_bytes()).hexdigest(),'cases_sha256':hashlib.sha256(casefile.read_bytes()).hexdigest(),
        'catalogue_sha256_at_end':hashlib.sha256(db.read_bytes()).hexdigest(),
        'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path('experiments/unified_agent.py'),Path('experiments/unified_agent_batch.py'),Path('experiments/route_service.py'),Path('experiments/injection_guard.py'),Path('experiments/input_guard.py'),Path('ci_agentlab/providers.py'))}}
    save_report(out,report,a.private_review)
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2));print('Rapport :',out/'report.json')
    if not report['campaign_complete']:p.exit(1,'Campagne interrompue ; consulter le rapport.\n')

if __name__=='__main__':main()
