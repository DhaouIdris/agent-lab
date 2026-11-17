"""Opt-in sequential RAG development batch. Requires Azure configuration and credits."""
import argparse
import hashlib
import getpass
import json
import os
from datetime import datetime,timezone
from pathlib import Path
from ci_agentlab.providers import ChatClient,ProviderError
from experiments.document_rag import ROOT,CORPUS,load_corpus,retrieve,generate
from run_azure import load_config

CASES=ROOT/'data/rag_batch_dev.json'

def run_batch(client,docs,cases,k=3,on_progress=None,turn_timeout=180):
    results=[];complete=True
    for case in cases:
        start=len(client.calls)
        hits=retrieve(case['question'],docs,k)
        row={'id':case['id'],'question':case['question'],'expected_behavior':case['expected_behavior'],
             'relevant_ids':case['relevant_ids'],'human_expectation':case['human_expectation'],
             'retrieved_ids':[x['id'] for x in hits], 'human_review_required':True}
        try:
            output=generate(client,case['question'],hits,timeout=turn_timeout)
            row['output']=output
            row['evaluation_status'] = output.get('guard_status', 'model_output' if hits else 'no_retrieval')
            row['behavior_match'] = None if output.get('guard_status') else output['abstain']==(case['expected_behavior']=='abstain')
            row['retrieval_hit_at_k']=bool(set(case['relevant_ids']) & {x['id'] for x in hits}) if case['relevant_ids'] else None
            row['retrieval_recall_at_k']=len(set(case['relevant_ids']) & {x['id'] for x in hits})/len(set(case['relevant_ids'])) if case['relevant_ids'] else None
            row['error']=None
        except (ProviderError,ValueError) as exc:
            row.update(output=None,behavior_match=None,retrieval_hit_at_k=None,retrieval_recall_at_k=None,error=type(exc).__name__+': '+str(exc)[:180])
            complete=False
        row['provider_calls']=client.calls[start:]
        results.append(row)
        if on_progress:on_progress(results)
        if not complete:break
    judged=[r for r in results if r['behavior_match'] is not None]
    retrieved=[r for r in results if r['retrieval_hit_at_k'] is not None]
    usage=[c.get('usage',{}) for r in results for c in r['provider_calls']]
    summary={'cases_planned':len(cases),'cases_run':len(results),'cases_with_output':sum(r['output'] is not None for r in results),
             'guard_blocked_runs':sum(r.get('evaluation_status') == 'blocked_suspected_injection' for r in results),
             'behavior_evaluable_runs':len(judged),
             'behavior_matches':sum(r['behavior_match'] for r in judged),
             'behavior_match_rate':sum(r['behavior_match'] for r in judged)/len(judged) if judged else None,
             'retrieval_hit_count':sum(r['retrieval_hit_at_k'] for r in retrieved),
             'mean_retrieval_recall_at_k':sum(r['retrieval_recall_at_k'] for r in retrieved)/len(retrieved) if retrieved else None,
             'retrieval_cases_with_labels':len(retrieved),
             'provider_attempts':len(usage),'prompt_tokens_reported':sum(u.get('prompt_tokens',0) for u in usage),
             'completion_tokens_reported':sum(u.get('completion_tokens',0) for u in usage),
             'usage_complete':all('prompt_tokens' in u and 'completion_tokens' in u for u in usage) if usage else True,
             'cost':None,'human_success_rate':None}
    return {'kind':'development_rag_batch_pending_human_review','campaign_complete':complete and len(results)==len(cases),
            'summary':summary,'results':results,
            'caveat':'Automatic checks test only abstention flag and labelled retrieval; citation IDs are checked but answer correctness, completeness and over-refusal require human review. Provisional development set, not independent.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='azure.json');p.add_argument('--out')
    p.add_argument('--k',type=int,default=3);p.add_argument('--corpus',default=str(CORPUS));p.add_argument('--cases',default=str(CASES));a=p.parse_args()
    corpus_path=Path(a.corpus);cases_path=Path(a.cases)
    docs=load_corpus(corpus_path);cases=json.loads(cases_path.read_text(encoding='utf-8'))
    if not isinstance(cases,list) or not 1<=len(cases)<=20:p.error('Cases must contain 1..20 examples')
    required=('id','question','expected_behavior','human_expectation','relevant_ids')
    if any(not isinstance(c,dict) or any(k not in c for k in required) or c['expected_behavior'] not in ('answer','abstain') or not isinstance(c['relevant_ids'],list) for c in cases):
        p.error('Invalid case metadata')
    if type(a.k)!=int or not 1<=a.k<=10:p.error('k must be 1..10')
    out=Path(a.out) if a.out else ROOT/'runs'/('rag_batch_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    if out.exists():p.error('Result directory exists; choose a new path')
    cfg=load_config(a.config)
    key=os.getenv('AGENTLAB_API_KEY') or getpass.getpass('Clé Azure (saisie masquée) : ')
    if not key:p.error('Clé absente')
    client=ChatClient(cfg['base_url'],cfg['deployment'],api_key=key,api_version=cfg.get('api_version'),
        max_output_tokens=cfg['max_output_tokens'],max_calls=3*len(cases),auth_header=cfg['auth_header'],
        token_parameter=cfg['token_parameter'],min_interval_seconds=cfg['min_interval_seconds'])
    out.mkdir(parents=True,exist_ok=False)
    def checkpoint(results):
        partial={'kind':'development_rag_batch_partial','campaign_complete':False,'results':results}
        temp=out/'report.tmp'
        temp.write_text(json.dumps(partial,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temp.replace(out/'report.json')
    report=run_batch(client,docs,cases,k=a.k,on_progress=checkpoint,turn_timeout=cfg['turn_timeout_seconds'])
    report['config']={'model':cfg['underlying_model'],'deployment':cfg['deployment'],'model_version':cfg['model_version'],'k':a.k,'max_provider_calls':3*len(cases),
        'corpus_sha256':hashlib.sha256(corpus_path.read_bytes()).hexdigest(),'cases_sha256':hashlib.sha256(cases_path.read_bytes()).hexdigest()}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2));print('Rapport :',out/'report.json')
    if not report['campaign_complete']:p.exit(1,'Campagne interrompue ; consulter le rapport partiel.\n')

if __name__=='__main__':main()

