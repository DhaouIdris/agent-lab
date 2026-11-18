"""Opt-in bounded integrated-agent pilot; requires local catalogue and Azure."""
import argparse
import getpass
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from ci_agentlab.providers import ChatClient, ProviderError
from experiments.document_rag import load_corpus
from experiments.unified_agent import ask
from run_azure import load_config


def run(client,db,docs,cases,on_progress=None,timeout=180):
    rows=[];complete=True
    for case in cases:
        start=len(client.calls)
        try:
            result=ask(client,db,docs,case['question'],timeout=timeout)
            used=[x['tool'] for x in result['trace']]
            guard=result.get('guard_status')
            row={'id':case['id'],'question':case['question'],'human_expectation':case['human_expectation'],
                 'required_tools':case['required_tools'],'observed_tools':used,'output':result['output'],
                 'trace':result['trace'],'status':guard or 'model_output',
                 'tool_selection_match':None if guard else set(case['required_tools'])<=set(used),'error':None}
        except (ProviderError,ValueError) as exc:
            row={'id':case['id'],'status':'execution_error','tool_selection_match':None,
                 'output':None,'trace':[],'error':type(exc).__name__+': '+str(exc)[:160]}
            complete=False
        row['provider_calls']=client.calls[start:];rows.append(row)
        if on_progress:on_progress(rows)
        if not complete:break
    evaluated=[r for r in rows if r['tool_selection_match'] is not None]
    return {'kind':'integrated_agent_development_pending_human_review','campaign_complete':complete and len(rows)==len(cases),
        'summary':{'cases_planned':len(cases),'cases_run':len(rows),'selection_evaluable':len(evaluated),
          'selection_matches':sum(r['tool_selection_match'] for r in evaluated),
          'guard_blocked':sum(r['status']=='blocked_suspected_injection' for r in rows),
          'provider_attempts':sum(len(r['provider_calls']) for r in rows),'cost':None},'results':rows,
        'caveat':'Selection checks only required tool names. Human review of usefulness, factuality, sources, injection resistance and over-refusal is required. Development scenarios are not independent.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',required=True);p.add_argument('--corpus',default='data/rag_integrated_dev.json');p.add_argument('--cases',default='data/unified_agent_dev_cases.json');p.add_argument('--config',default='azure.json');p.add_argument('--out');p.add_argument('--case',action='append',help='Repeat to select specific case IDs')
    a=p.parse_args();db=Path(a.db);corpus=Path(a.corpus);casefile=Path(a.cases)
    if not db.is_file():p.error('Catalogue database missing')
    docs=load_corpus(corpus);cases=json.loads(casefile.read_text(encoding='utf8'))
    allowed={'search_catalogue','search_documents'}
    if not isinstance(cases,list) or not 1<=len(cases)<=10 or any(not isinstance(c,dict) or not isinstance(c.get('id'),str) or not isinstance(c.get('question'),str) or not c['question'].strip() or len(c['question'])>2000 or not isinstance(c.get('human_expectation'),str) or not isinstance(c.get('required_tools'),list) or any(t not in allowed for t in c['required_tools']) for c in cases) or len({c['id'] for c in cases})!=len(cases):p.error('Invalid cases')
    if a.case:
        selected=set(a.case)
        if len(selected)!=len(a.case) or not selected <= {c['id'] for c in cases}:p.error('Unknown or duplicate case IDs')
        cases=[c for c in cases if c['id'] in selected]
    out=Path(a.out) if a.out else Path('runs')/('unified_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    if out.exists():p.error('Result directory exists')
    cfg=load_config(a.config);key=os.getenv('AGENTLAB_API_KEY') or getpass.getpass('Clé Azure (saisie masquée) : ')
    if not key:p.error('Clé absente')
    client=ChatClient(cfg['base_url'],cfg['deployment'],api_key=key,api_version=cfg.get('api_version'),max_output_tokens=cfg['max_output_tokens'],max_calls=5*len(cases),auth_header=cfg['auth_header'],token_parameter=cfg['token_parameter'],min_interval_seconds=cfg['min_interval_seconds'])
    out.mkdir(parents=True,exist_ok=False)
    def checkpoint(rows):
        tmp=out/'report.tmp';tmp.write_text(json.dumps({'kind':'partial','campaign_complete':False,'results':rows},ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(out/'report.json')
    report=run(client,db,docs,cases,on_progress=checkpoint,timeout=cfg['turn_timeout_seconds'])
    report['config']={'model':cfg['underlying_model'],'model_version':cfg['model_version'],'max_provider_calls':5*len(cases),
       'corpus_sha256':hashlib.sha256(corpus.read_bytes()).hexdigest(),'cases_sha256':hashlib.sha256(casefile.read_bytes()).hexdigest()}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2));print('Rapport :',out/'report.json')
    if not report['campaign_complete']:p.exit(1,'Campagne interrompue ; consulter le rapport.\n')

if __name__=='__main__':main()
