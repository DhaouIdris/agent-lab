"""Compare lexical detector with optional Azure Prompt Shields on synthetic documents."""
import argparse
import getpass
import hashlib
import json
import os
import time
from pathlib import Path
from experiments.injection_guard import inspect_passages
from experiments.prompt_shield import AzurePromptShield, ShieldUnavailable


def stratify(cases, limit):
    groups=[[c for c in cases if c['label']==label] for label in ('malicious','benign')]
    rows=[]
    while len(rows)<limit and any(groups):
        for group in groups:
            if group and len(rows)<limit:rows.append(group.pop(0))
    return rows


def summarize(rows, field):
    valid=[r for r in rows if r.get(field) is not None]
    counts={key:0 for key in ('tp','fn','fp','tn')}
    for r in valid:
        counts[('tp' if r[field] else 'fn') if r['label']=='malicious' else ('fp' if r[field] else 'tn')]+=1
    return {**counts,'evaluable':len(valid),'unevaluable':len(rows)-len(valid),
            'detection_rate':counts['tp']/(counts['tp']+counts['fn']) if counts['tp']+counts['fn'] else None,
            'benign_block_rate':counts['fp']/(counts['fp']+counts['tn']) if counts['fp']+counts['tn'] else None}


def run(shield,cases,max_requests=2,on_progress=None):
    available_cases=len(cases)
    cases=stratify(cases,max_requests*5);rows=[];attempts=0;complete=True
    for i in range(0,len(cases),5):
        batch=cases[i:i+5];attempts+=1;start=time.monotonic()
        try:
            result=shield.inspect('Quelle est la localisation du lieu ?', [{'id':c['id'],'text':c['text']} for c in batch]);
            flagged=set(result['flagged_source_ids']); error=None
        except ShieldUnavailable:
            flagged=set();error='guard_unavailable';complete=False
        elapsed=round(time.monotonic()-start,3)
        for c in batch:
            rows.append({'id':c['id'],'label':c['label'],
                'baseline_blocked':bool(inspect_passages([{'id':c['id'],'text':c['text']}])),
                'shield_document_attack':None if error else c['id'] in flagged,
                'shield_prompt_attack':None if error else result['user_attack'],
                'provider_status':error or 'ok','batch_latency_seconds':elapsed})
        if on_progress:on_progress(rows,attempts)
        if error:break
    return {'results':rows,'summary':{'available_cases':available_cases,'selected_cases':len(cases),'cases_recorded':len(rows),
      'provider_attempts':attempts,'campaign_complete':complete and len(rows)==len(cases),
      'baseline':summarize(rows,'baseline_blocked'),'shield':summarize(rows,'shield_document_attack')}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cases',default='data/injection_guard_challenge.json')
    p.add_argument('--endpoint',required=True);p.add_argument('--out',required=True);p.add_argument('--max-requests',type=int,default=2)
    a=p.parse_args();out=Path(a.out)
    if out.exists():p.error('Output exists; choose a new path')
    if not 1<=a.max_requests<=20:p.error('max requests must be 1..20')
    raw=Path(a.cases).read_bytes();cases=json.loads(raw.decode('utf8'))
    if not isinstance(cases,list) or not cases or any(not isinstance(c,dict) or not isinstance(c.get('id'),str) or not c['id'] or c.get('label') not in ('malicious','benign') or not isinstance(c.get('text'),str) or not c['text'].strip() for c in cases) or len({c['id'] for c in cases})!=len(cases):p.error('Invalid cases')
    key=os.getenv('AGENTLAB_SHIELD_KEY') or getpass.getpass('Clé Content Safety (saisie masquée) : ')
    shield=AzurePromptShield(a.endpoint,key)
    def checkpoint(rows,attempts):
        report={'kind':'development_prompt_shield_partial','results':rows,'provider_attempts':attempts}
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    report=run(shield,cases,max_requests=a.max_requests,on_progress=checkpoint)
    report.update(kind='development_prompt_shield_comparison',cases_sha256=hashlib.sha256(raw).hexdigest(),
        max_requests=a.max_requests,cost=None,caveat='Synthetic labels not independent. Each request sends up to five documents and one fixed question. Error results are unevaluable, not negatives; provider usage and cost unavailable. Batch latency applies to entire request.')
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'output':out.name,'summary':report['summary']},ensure_ascii=False))


if __name__=='__main__':main()
