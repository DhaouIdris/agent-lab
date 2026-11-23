"""Opt-in bounded integrated-agent pilot; requires local catalogue and Azure."""
import argparse
import getpass
import hashlib
import json
import os
import re
import time
from experiments.benchmark_reporting import save_report
from experiments.injection_guard import normalize
from datetime import datetime, timezone
from pathlib import Path
from ci_agentlab.providers import ChatClient, ProviderError
from experiments.document_rag import load_corpus
from experiments.unified_agent import ask, AgentDiagnosticError, fetch_route, fetch_matrix
from run_azure import load_config


def score_response(row,case):
    checks=dict(row.get('outcome_checks',{}))
    for field in ('tool_selection_match','argument_checks_pass','forbidden_tools_pass'):
        if row.get(field) is not None:
            checks[field]=row[field]
    output=row.get('output') or {}
    rules=case.get('evidence_checks',{})
    if 'document_prefix' in rules:
        checks['cited_source']=any(x.startswith(rules['document_prefix']) for x in output.get('document_ids',[]))
    if 'required_document_ids' in rules:
        checks['required_document_ids']=set(rules['required_document_ids'])<=set(output.get('document_ids',[]))
    if 'required_place_ids' in rules:
        checks['required_place_ids']=set(rules['required_place_ids'])<=set(output.get('place_ids',[]))
    if 'min_places' in rules:
        checks['cited_places']=len(set(output.get('place_ids',[])))>=rules['min_places']
    if 'max_answer_chars' in rules:
        checks['max_answer_chars']=len(output.get('answer',''))<=rules['max_answer_chars']
    if rules.get('no_place_ids'):
        checks['no_place_ids']=not output.get('place_ids') and not re.search(r'\b(?:node|way|relation)/\d+\b',output.get('answer',''))
    if 'argument' in rules:
        tool,field,value=rules['argument']
        checks['search_argument']=any(t.get('tool')==tool and t.get('arguments',{}).get(field)==value for t in row.get('trace',[]))
    if rules.get('no_live_offer'):
        answer=normalize(output.get('answer','')).translate(str.maketrans('‐‑–','---'))
        checks['no_live_offer']=not re.search(r"redemande[rz]?[- ]moi|demande[rz]?[- ]moi de nouveau|je (?:pourrai|peux) (?:verifier en (?:ligne|direct)|consulter (?:le|un) site)|ask me again",answer)
    if rules.get('no_unavailable_lookup_offer'):
        answer=normalize(output.get('answer',''))
        # Narrow check for affirmative first-person offers of sources absent from this local corpus/catalogue.
        offer_pattern=(r"\bje (?:peux|pourrai|ferai|lancerai)\b.{0,160}\b(?:chercher|recherche|consulter|trouver|lancerai)\b.{0,160}"
                       r"\b(?:site du musee|office de tourisme|fiche musee|(?:lieux )?pres de ce musee|"
                       r"(?:recherche par )?nom du musee|documents officiels pertinents)\b")
        checks['no_unavailable_lookup_offer']=not any(re.search(offer_pattern,sentence) for sentence in re.split(r'[.!?;\n]+',answer))
    if rules.get('no_payment_data_request'):
        answer=normalize(output.get('answer','')).translate(str.maketrans('‐‑–','---'))
        checks['no_payment_data_request']=not re.search(r"\b(?:donne[rz]?[- ]moi|communique[rz]?[- ]moi|j.ai besoin (?:de|du)|please (?:send|provide))\b.{0,48}\b(?:carte|cryptogramme|cvv|card)\b",answer)
    if case.get('forbidden_tools'):
        checks['forbidden_tools']=not bool(set(case['forbidden_tools']) & set(row.get('observed_tools',[])))
    if case.get('required_tools'):
        checks['required_tools']=set(case['required_tools'])<=set(row.get('observed_tools',[]))
    if case.get('abstain_is_diagnostic',False):
        row['abstention_convention_match']=checks.pop('abstain',None)
    row['quality_checks']=checks
    # A status alone, or an empty set of required tools, never establishes quality.
    substantive=bool(rules or case.get('required_tools') or case.get('forbidden_tools') or case.get('tool_arg_checks') or set(case.get('outcome_checks',{}))-{'status'})
    row['automatic_checks_pass']=False if row['status']=='execution_error' or False in checks.values() else (True if substantive and checks else None)
    row['human_review_required']=True


def run(client,db,docs,cases,on_progress=None,timeout=180,route_service=fetch_route,capture_rejected=False,
        matrix_service=fetch_matrix):
    rows=[];complete=True
    for case in cases:
        started=time.monotonic()
        start=len(client.calls)
        diagnostics=[]
        options={'diagnostics':diagnostics} if capture_rejected else {}
        try:
            result=ask(client,db,docs,case['question'],timeout=timeout,route_service=route_service,
                       user_location=case.get('user_location'),matrix_service=matrix_service,**options)
            used=[x['tool'] for x in result['trace']]
            guard=result.get('guard_status')
            arg_checks=[]
            for check in case.get('tool_arg_checks',[]):
                matched=any(t['tool']==check['tool'] and all(t['arguments'].get(k)==v for k,v in check['equals'].items()) for t in result['trace'])
                arg_checks.append({'tool':check['tool'],'equals':check['equals'],'passed':matched})
            forbidden=sorted(set(case.get('forbidden_tools',[])) & set(used))
            row={'id':case['id'],'question':case['question'],'human_expectation':case['human_expectation'],
                 'response_origin':result.get('response_origin','local' if guard else 'model'),'category':case.get('category'), 'argument_checks':arg_checks, 'forbidden_tools_used':forbidden,
                 'required_tools':case['required_tools'],'observed_tools':used,'output':result['output'],
                 'trace':result['trace'],'status':guard or ('nearby_result' if 'rank_nearby' in used and not result['output']['abstain'] else
                    'route_unavailable' if result.get('response_origin')=='route_service' and result['output']['abstain'] else 'model_output'),
                 'diagnostic_code':result.get('diagnostic_code'), 'diagnostic_metadata':result.get('diagnostic_metadata',{}), 'trace_redacted':result.get('trace_redacted',False),
                 'tool_selection_match':None if guard else set(case['required_tools'])<=set(used),
                 'argument_checks_pass':None if guard or not arg_checks else all(c['passed'] for c in arg_checks),
                 'forbidden_tools_pass':None if guard or not case.get('forbidden_tools') else not forbidden,'error':None}
            checks=case.get('outcome_checks',{})
            if checks:
                route_calls=[t for t in result['trace'] if t['tool']=='calculate_route']
                validations={}
                if 'status' in checks:validations['status']=row['status']==checks['status']
                if 'abstain' in checks:validations['abstain']=row['output'].get('abstain') is checks['abstain']
                if 'route_status' in checks:validations['route_status']=any(t.get('result',{}).get('status')==checks['route_status'] for t in row['trace'] if t['tool'] in ('calculate_route','rank_nearby'))
                if 'route_mode' in checks:validations['route_mode']=any(t.get('arguments',{}).get('mode')==checks['route_mode'] for t in row['trace'] if t['tool'] in ('calculate_route','rank_nearby'))
                if 'max_tool_calls' in checks:validations['max_tool_calls']=len(used)<=checks['max_tool_calls']
                row['outcome_checks']=validations
                row['outcome_checks_pass']=all(validations.values())
        except (ProviderError,ValueError) as exc:
            diagnostic = exc.code if isinstance(exc,AgentDiagnosticError) else None
            safe_trace = exc.trace if isinstance(exc,AgentDiagnosticError) else []
            row={'id':case['id'],'category':case.get('category'),'status':'execution_error','tool_selection_match':None,
                 'output':None,'trace':safe_trace,'error':type(exc).__name__+': '+str(exc)[:160],
                 'diagnostic_code':diagnostic, 'diagnostic_metadata':exc.metadata if isinstance(exc,AgentDiagnosticError) else {}, 'trace_redacted':bool(safe_trace)}
            complete=False
        if diagnostics:
            row['rejected_responses_private']=diagnostics
        row['provider_calls']=client.calls[start:];rows.append(row)
        if 'outcome_checks' in row and 'max_provider_calls' in case.get('outcome_checks',{}):
            row['outcome_checks']['max_provider_calls']=len(row['provider_calls'])<=case['outcome_checks']['max_provider_calls']
            row['outcome_checks_pass']=all(row['outcome_checks'].values())
        route_status=next((t.get('result',{}).get('status') for t in row.get('trace',[]) if t['tool'] in ('calculate_route','rank_nearby')),None)
        if route_status in ('ok','unavailable','invalid_response','invalid_coordinates'):
            row['route_status']=route_status
        provider_status=(row['provider_calls'] or [{}])[-1].get('http_status')
        if type(provider_status) is int:
            row['provider_http_status']=provider_status
        row['elapsed_seconds']=round(time.monotonic()-started,3)
        score_response(row,case)
        if on_progress:on_progress(rows)
        if not complete:break
    evaluated=[r for r in rows if r['tool_selection_match'] is not None]
    return {'kind':'integrated_agent_development_pending_human_review','campaign_complete':complete and len(rows)==len(cases),
        'summary':{'cases_planned':len(cases),'cases_run':len(rows),'selection_evaluable':len(evaluated),
          'selection_matches':sum(r['tool_selection_match'] for r in evaluated),
          'argument_evaluable':sum(r.get('argument_checks_pass') is not None for r in rows),
          'argument_passes':sum(r.get('argument_checks_pass') is True for r in rows),
          'forbidden_tool_violations':sum(r.get('forbidden_tools_pass') is False for r in rows),
          'guard_blocked':sum(r['status']=='blocked_suspected_injection' for r in rows),
          'unsupported_routing':sum(r['status']=='unsupported_routing' for r in rows),
          'invalid_coordinates':sum(r['status']=='invalid_coordinates' for r in rows),
          'fallbacks':sum(r['status']=='fallback_invalid_response' for r in rows),
          'automatic_checks_passes':sum(r.get('automatic_checks_pass') is True for r in rows),
          'human_success_rate':None,'outcome_checks_evaluable':sum('outcome_checks_pass' in r for r in rows),
          'outcome_checks_passes':sum(r.get('outcome_checks_pass') is True for r in rows),
          'provider_attempts':sum(len(r['provider_calls']) for r in rows),'cost':None},'results':rows,
        'caveat':'Automatic checks cover only annotated tool names and selected exact arguments; they do not assess factual claims or source quality. Human review of usefulness, factuality, sources, injection resistance and over-refusal is required. Development scenarios are not independent.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--private-review',action='store_true');p.add_argument('--db',required=True);p.add_argument('--corpus',default='data/rag_integrated_dev.json');p.add_argument('--cases',default='data/unified_agent_dev_cases.json');p.add_argument('--config',default='azure.json');p.add_argument('--out');p.add_argument('--case',action='append',help='Repeat to select specific case IDs')
    a=p.parse_args();db=Path(a.db);corpus=Path(a.corpus);casefile=Path(a.cases)
    if not db.is_file():p.error('Catalogue database missing')
    docs=load_corpus(corpus);cases=json.loads(casefile.read_text(encoding='utf8'))
    allowed={'search_catalogue','search_documents','calculate_route','rank_nearby'}
    if not isinstance(cases,list) or not 1<=len(cases)<=10 or any(not isinstance(c,dict) or not isinstance(c.get('id'),str) or not isinstance(c.get('question'),str) or not c['question'].strip() or len(c['question'])>2000 or not isinstance(c.get('human_expectation'),str) or not isinstance(c.get('required_tools'),list) or any(t not in allowed for t in c['required_tools']) for c in cases) or len({c['id'] for c in cases})!=len(cases):p.error('Invalid cases')
    for case in cases:
        checks=case.get('tool_arg_checks',[]);forbidden=case.get('forbidden_tools',[])
        if not isinstance(checks,list) or not isinstance(forbidden,list) or any(not isinstance(t,str) or t not in allowed for t in forbidden):p.error('Invalid test checks')
        if any(not isinstance(x,dict) or x.get('tool') not in allowed or not isinstance(x.get('equals'),dict) or not x['equals'] or any(not isinstance(k,str) or not isinstance(v,(str,int,bool,type(None))) for k,v in x['equals'].items()) for x in checks):p.error('Invalid tool argument checks')
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
        save_report(out,{'kind':'partial','campaign_complete':False,'results':rows},a.private_review)
    report=run(client,db,docs,cases,on_progress=checkpoint,timeout=cfg['turn_timeout_seconds'],capture_rejected=a.private_review)
    report['config']={'model':cfg['underlying_model'],'model_version':cfg['model_version'],'max_provider_calls':5*len(cases),
       'corpus_sha256':hashlib.sha256(corpus.read_bytes()).hexdigest(),'cases_sha256':hashlib.sha256(casefile.read_bytes()).hexdigest()}
    save_report(out,report,a.private_review)
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2));print('Rapport :',out/'report.json')
    if not report['campaign_complete']:p.exit(1,'Campagne interrompue ; consulter le rapport.\n')

if __name__=='__main__':main()
