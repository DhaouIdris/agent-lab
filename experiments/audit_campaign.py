"""Sixty frozen scenarios. Default to a network-free check of the real entry point."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
import re
from pathlib import Path
import statistics

from ci_agentlab.providers import ChatClient
from experiments.benchmark_reporting import save_report, write_json
from experiments.document_rag import load_corpus
from experiments.unified_agent import fetch_route, fetch_matrix, _NEARBY_USER
from experiments.injection_guard import normalize
from experiments.route_service import valid_coordinates
from experiments.unified_agent_batch import run
from run_azure import load_config

CASES=Path('data/audit_campaign_60.json')
CORPUS=Path('data/rag_integrated_dev.json')
DOCS={'tai':'UNESCO_TAI__','comoe':'UNESCO_COMOE__','nimba':'UNESCO_NIMBA__',
      'bassam':'UNESCO_BASSAM__','mosque':'UNESCO_MOSQUEES__','gdp':'WB_CIV_GDP_',
      'mixed':'UNESCO_COMOE__','mixed_route':'UNESCO_TAI__'}
LOCAL={'coords':'unsupported_routing','invalid':'invalid_coordinates','block':'blocked_suspected_injection',
       'nearby_invalid':'invalid_coordinates','nearby_empty':'no_nearby_candidates'}
REVIEW=('useful_and_complete','facts_supported','citations_relevant','limits_accurate','no_unauthorized_promise')


def scenario(entry):
    goal=entry['goal']
    tools=[]
    checks={'status':LOCAL.get(goal,'model_output')}
    evidence={'no_live_offer':True}
    if goal=='unknown':
        evidence['no_payment_data_request']=True
    if goal in DOCS:
        tools.append('search_documents')
        evidence['document_prefix']=DOCS[goal]
    if goal in ('places','places2','places3','search','mixed'):
        tools.append('search_catalogue')
        if goal!='search':
            evidence['min_places']=3 if goal=='places3' else (2 if goal=='places2' else 1)
    if goal in LOCAL:
        checks.update(max_provider_calls=0,max_tool_calls=0,abstain=True)
    elif goal=='clarify' and entry.get('user_location') is None and _NEARBY_USER.search(normalize(entry['question'])) and re.search(r'\b(?:moi|ma position|near me)\b',normalize(entry['question'])):
        checks.update(status='location_required',max_provider_calls=0,max_tool_calls=0,abstain=True)
    elif goal in ('car','walk'):
        tools.append('calculate_route')
        checks.update(route_status='ok',route_mode=goal,abstain=False,max_provider_calls=0)
    elif goal=='mixed_route':
        tools.append('calculate_route')
        checks.update(route_status='ok',route_mode='walk',abstain=False)
    elif goal=='nearby':
        tools.append('rank_nearby')
        evidence['min_places']=1
        checks.update(status='nearby_result',route_status='ok',abstain=False,max_provider_calls=0)
    elif goal in ('unknown','clarify'):
        checks['abstain']=True
    elif goal!='search':
        checks['abstain']=False
    checks.update(entry.get('outcome_checks',{}))
    evidence.update(entry.get('evidence_checks',{}))
    return {**entry,'required_tools':tools,'outcome_checks':checks,'evidence_checks':evidence,
            'forbidden_tools':[] if goal in ('walk','car','mixed_route','nearby') else ['calculate_route','rank_nearby']}


class ExternalBoundary(Exception):
    """An offline or explicitly forbidden external operation was requested."""


class NoChat:
    def __init__(self):
        self.calls=[]

    def chat(self,*args,**kwargs):
        raise ExternalBoundary('chat')


def no_route(*args,**kwargs):
    raise ExternalBoundary('route')


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def evaluate_case(case,client,live,db,docs,timeout,capture_rejected=False):
    goal=case['goal']
    allow_chat=goal not in {*LOCAL,'walk','car','nearby'}
    allow_route=goal in ('walk','car','mixed_route','nearby')
    chat=client if live and allow_chat else NoChat()
    router=fetch_route if live and allow_route else no_route
    matrix_router=fetch_matrix if live and allow_route else no_route
    before=len(chat.calls)
    try:
        return run(chat,db,docs,[case],timeout=timeout,route_service=router,
                   matrix_service=matrix_router,capture_rejected=capture_rejected)['results'][0]
    except ExternalBoundary as exc:
        requested=exc.args[0]
        permitted=allow_chat if requested=='chat' else allow_route
        status='awaiting_'+requested if permitted and not live else 'unexpected_'+requested
        return {'id':case['id'],'category':case['category'],'status':status,'provider_calls':chat.calls[before:],
                'automatic_checks_pass':None if status.startswith('awaiting') else False}


def summarize(rows,planned):
    passed=sum(r.get('automatic_checks_pass') is True for r in rows)
    evaluated=sum(r.get('automatic_checks_pass') is not None for r in rows)
    timed=sorted(r['elapsed_seconds'] for r in rows if 'elapsed_seconds' in r)
    calls=[c for r in rows for c in r.get('provider_calls',[])]
    tokens=[c.get('usage',{}).get('total_tokens') for c in calls]
    return {'planned':planned,'visited':len(rows),'automatically_evaluable':evaluated,
            'automatic_passes':passed,'automatic_failures':evaluated-passed,
            'abstention_convention_mismatches':sum(r.get('abstention_convention_match') is False for r in rows),
            'statuses':dict(Counter(r['status'] for r in rows)),'provider_attempts':len(calls),
            'total_reported_tokens':sum(tokens) if all(isinstance(x,int) for x in tokens) else None,
            'route_statuses':dict(Counter(r['route_status'] for r in rows if r.get('route_status'))),
            'model_outputs':sum(r.get('response_origin')=='model' for r in rows),
            'route_calls':sum(r.get('observed_tools',[]).count('calculate_route') for r in rows),
            'matrix_calls':sum(r.get('observed_tools',[]).count('rank_nearby') for r in rows),
            'latency_p50_seconds':statistics.median(timed) if timed else None,
            'latency_p95_seconds':timed[(95*len(timed)+99)//100-1] if timed else None,
            'human_success_rate':None}


def consistency_by_case(rows,cases,repetitions):
    results=[]
    expected=set(range(1,repetitions+1))
    for case in cases:
        runs=[r for r in rows if r['id']==case['id']]
        recorded=[r['repetition'] for r in runs]
        evaluated=[r for r in runs if type(r.get('automatic_checks_pass')) is bool]
        complete=len(runs)==repetitions and set(recorded)==expected
        outputs=[r['output'] for r in runs if isinstance(r.get('output'),dict)]
        abstentions=[o['abstain'] for o in outputs if type(o.get('abstain')) is bool]
        citations={(tuple(sorted(o.get('document_ids',[]))),tuple(sorted(o.get('place_ids',[])))) for o in outputs}
        sequences={tuple(r['observed_tools']) for r in runs if isinstance(r.get('observed_tools'),list)}
        results.append({'id':case['id'],'category':case['category'],'repetitions_planned':repetitions,
                        'runs_recorded':len(runs),'repetitions_recorded':recorded,
                        'automatic_checks_evaluable':len(evaluated),
                        'automatic_passes':sum(r['automatic_checks_pass'] for r in evaluated),
                        'all_repetitions_passed':all(r['automatic_checks_pass'] for r in evaluated)
                            if complete and len(evaluated)==repetitions else None,
                        'statuses':dict(Counter(r['status'] for r in runs)),
                        'variable_status':len({r['status'] for r in runs})>1 if len(runs)>=2 else None,
                        'variable_abstention':len(set(abstentions))>1 if len(abstentions)>=2 else None,
                        'tool_sequence_variants':len(sequences),'citation_set_variants':len(citations)})
    return results


def add_consistency(report,cases,repetitions):
    per_case=consistency_by_case(report['results'],cases,repetitions)
    report['per_case']=per_case
    report['summary'].update(
        cases_passed_all_repetitions=sum(c['all_repetitions_passed'] is True for c in per_case),
        cases_failed_with_all_repetitions_evaluable=sum(c['all_repetitions_passed'] is False for c in per_case),
        cases_awaiting_complete_evaluation=sum(c['all_repetitions_passed'] is None for c in per_case),
        cases_with_variable_status=sum(c['variable_status'] is True for c in per_case),
        cases_with_variable_abstention=sum(c['variable_abstention'] is True for c in per_case))


def provider(config,budget):
    key=os.getenv('AGENTLAB_API_KEY') or getpass.getpass('Clé Azure : ')
    if not key:
        raise ValueError('Clé Azure absente')
    return ChatClient(config['base_url'],config['deployment'],api_key=key,api_version=config.get('api_version'),
                      max_calls=budget,max_output_tokens=config['max_output_tokens'],auth_header=config['auth_header'],
                      token_parameter=config['token_parameter'],min_interval_seconds=config['min_interval_seconds'])


def adjudicate(directory):
    report=json.loads((directory/'report.json').read_text(encoding='utf8'))
    grades=json.loads((directory/'grades.private.json').read_text(encoding='utf8'))
    if report['kind']!='live_development' or grades['run_id']!=report['config']['run_id']:
        raise ValueError('Grades must belong to this live campaign')
    expected={(r['id'],r['repetition']):r for r in report['results']}
    if len(grades['rows'])!=len(expected):
        raise ValueError('Incomplete grade sheet')
    by_case={}
    by_category={}
    dimension_failures=Counter()
    for grade in grades['rows']:
        key=(grade['id'],grade['repetition'])
        row=expected.pop(key)
        if any(type(grade.get(dim)) is not bool for dim in REVIEW):
            raise ValueError('Fill every review dimension with true or false')
        ok=row['automatic_checks_pass'] is True and all(grade[d] for d in REVIEW)
        by_case.setdefault(key[0],[]).append(ok)
        group=by_category.setdefault(row.get('category','unspecified'),{'reviewed':0,'joint_passes':0})
        group['reviewed']+=1
        group['joint_passes']+=int(ok)
        dimension_failures.update(d for d in REVIEW if not grade[d])
    n=report['summary']['planned']
    passed=sum(sum(v) for v in by_case.values())
    consistent=sum(len(v)==report['config']['repetitions'] and all(v) for v in by_case.values())
    write_json(directory/'adjudication.json',{'reviewed':len(grades['rows']),'planned':n,'joint_passes':passed,
               'success_per_planned_run':passed/n,'passed_every_planned_repetition':consistent,
               'per_category':by_category,'failed_review_dimensions':dict(dimension_failures),
               'cases_with_variable_success':sum(len(set(v))>1 for v in by_case.values()),
               'distinct_cases_planned':n//report['config']['repetitions'],'campaign_complete':report['campaign_complete']})


def load_cases(path,consistency):
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    goals=set(DOCS)|set(LOCAL)|{'places','places2','places3','search','general','unknown','clarify','car','walk','nearby'}
    if not isinstance(data,list) or not 1<=len(data)<=60:
        raise ValueError('Provide 1..60 scenarios')
    ids=set()
    for case in data:
        extra_outcome=case.get('outcome_checks',{}) if isinstance(case,dict) else None
        extra_evidence=case.get('evidence_checks',{}) if isinstance(case,dict) else None
        if (not isinstance(case,dict) or not all(isinstance(case.get(k),str) and case[k].strip()
                for k in ('id','category','goal','question','human_expectation'))
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',case['id']) or case['id'] in ids
                or type(case.get('abstain_is_diagnostic',False)) is not bool
                or case['goal'] not in goals or len(case['question'])>2000 or type(case.get('consistency')) is not bool
                or (case['goal'] in ('nearby','nearby_invalid','nearby_empty') and 'user_location' not in case)
                or ('user_location' in case and not valid_coordinates(case['user_location']) and case['goal']!='nearby_invalid')
                or not isinstance(extra_outcome,dict) or not set(extra_outcome)<={'max_tool_calls','max_provider_calls'}
                or any(type(value) is not int or not 0<=value<=10 for value in extra_outcome.values())
                or not isinstance(extra_evidence,dict) or not set(extra_evidence)<={'no_unavailable_lookup_offer','required_document_ids','required_place_ids','max_answer_chars','no_place_ids'}
                or any(type(value) is not bool for key,value in extra_evidence.items() if key=='no_unavailable_lookup_offer')
                or any(type(value) is not bool for key,value in extra_evidence.items() if key=='no_place_ids')
                or ('max_answer_chars' in extra_evidence and (type(extra_evidence['max_answer_chars']) is not int or not 1<=extra_evidence['max_answer_chars']<=1000))
                or any(not isinstance(extra_evidence.get(key),list) or not extra_evidence[key]
                       or any(not isinstance(item,str) or not item for item in extra_evidence[key])
                       for key in ('required_document_ids','required_place_ids') if key in extra_evidence)):
            raise ValueError('Invalid or duplicate scenario')
        ids.add(case['id'])
    selected=[scenario(case) for case in data if not consistency or case['consistency']]
    if not selected:
        raise ValueError('Empty consistency subset')
    return selected


def failed_cases(cases,report_path):
    report=json.loads(report_path.read_text(encoding='utf-8-sig'))
    raw=CASES.read_bytes().replace(b'\r\n',b'\n')
    legacy_hashes={hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw.replace(b'\n',b'\r\n')).hexdigest()}
    if report['config']['cases_sha256'] not in legacy_hashes:
        raise ValueError('Previous report must use the frozen default panel')
    failed={r['id'] for r in report['results'] if r.get('automatic_checks_pass') is False}
    if not failed or not failed <= {c['id'] for c in cases}:
        raise ValueError('No failed cases or unknown scenario IDs')
    return [c for c in cases if c['id'] in failed]


def diagnose(directory):
    """Extract failed-case evidence locally. No generation and no changes to scores."""
    report=json.loads((directory/'report.json').read_text(encoding='utf-8-sig'))
    review=json.loads((directory/'review.private.json').read_text(encoding='utf-8-sig'))
    if report['config']['run_id']!=review['config']['run_id']:
        raise ValueError('Review belongs to another run')
    failed={(r['id'],r['repetition']) for r in report['results'] if r.get('automatic_checks_pass') is False}
    rows=[]
    for row in review['results']:
        key=(row['id'],row['repetition'])
        if key not in failed:
            continue
        failed.remove(key)
        sources=[]
        for tool in row.get('trace',[]):
            evidence_available=isinstance(tool.get('result'),dict)
            result=tool.get('result') or {}
            passages=result.get('passages',[])
            items=result.get('items',[])
            sources.append({'tool':tool['tool'],'evidence_available':evidence_available,
                            'document_ids':[d['id'] for d in passages] if evidence_available else None,
                            'place_ids':[d['source_id'] for d in items] if evidence_available else None,
                            'result_count':len(passages)+len(items) if evidence_available else tool.get('result_count'),
                            'passages':[{k:d[k] for k in ('id','title','text','url','publisher') if k in d} for d in passages],
                            'places':[{k:d[k] for k in ('source_id','name','category','district') if k in d} for d in items]})
        rows.append({k:row.get(k) for k in ('id','repetition','question','human_expectation','output','diagnostic_code',
                                            'diagnostic_metadata','quality_checks','rejected_responses_private')})
        rows[-1]['observed_sources']=sources
    if failed:
        raise ValueError('Review missing failed executions')
    output=directory/'diagnosis.private.json'
    write_json(output,{'run_id':report['config']['run_id'],'rows':rows})
    print(str(output))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live',action='store_true')
    p.add_argument('--consistency',action='store_true',help='Repeat cases marked consistency=true three times')
    p.add_argument('--cases',type=Path,default=CASES,help='Frozen panel or a separately authored private panel')
    p.add_argument('--db',type=Path,default=Path('local_data/lieux.sqlite'))
    p.add_argument('--config',default='azure.json')
    p.add_argument('--private-review',action='store_true')
    p.add_argument('--out',type=Path)
    p.add_argument('--adjudicate',type=Path)
    p.add_argument('--diagnose',type=Path,help='Extract failed answers from a local private review without network calls')
    p.add_argument('--failed-from',type=Path,help='Run only failures from an earlier frozen-panel report')
    p.add_argument('--category',action='append',help='Select one or more categories from the supplied panel')
    p.add_argument('--case',action='append',help='Select individual case IDs from the supplied panel')
    a=p.parse_args()
    if a.diagnose:
        diagnose(a.diagnose)
        return
    if a.adjudicate:
        adjudicate(a.adjudicate)
        return
    cases=load_cases(a.cases,a.consistency)
    if a.category:
        if len(set(a.category))!=len(a.category) or not set(a.category)<={c['category'] for c in cases}:
            p.error('Unknown or duplicate category in selected panel')
        cases=[c for c in cases if c['category'] in set(a.category)]
    if a.case:
        if len(set(a.case))!=len(a.case) or not set(a.case)<={c['id'] for c in cases}:
            p.error('Unknown or duplicate case ID in selected panel')
        cases=[c for c in cases if c['id'] in set(a.case)]
    if a.failed_from:
        if a.consistency or a.cases!=CASES or a.category or a.case:
            p.error('--failed-from requires the full frozen default panel')
        cases=failed_cases(cases,a.failed_from)
    repeat=3 if a.consistency else 1
    planned=len(cases)*repeat
    config=load_config(a.config) if a.live else {}
    if a.live and not a.db.is_file():
        p.error('Catalogue SQLite introuvable')
    client=provider(config,planned*5) if a.live else NoChat()
    docs=load_corpus(CORPUS)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=a.out or Path('runs')/('audit_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    metadata={'run_id':stamp,'abstention_policy':{c['id']:'diagnostic' if c.get('abstain_is_diagnostic') else 'scored' for c in cases},'selected_case_ids':[c['id'] for c in cases],'repetitions':repeat,'cases_sha256':digest(a.cases),'corpus_sha256':digest(CORPUS),
              'catalogue_sha256_start':digest(a.db) if a.db.is_file() else None,
              'model':config.get('underlying_model'),'model_version':config.get('model_version'),
              'max_provider_calls':planned*5 if a.live else 0,
              'code_sha256':{p.name:digest(p) for p in [Path(__file__),Path('ci_agentlab/providers.py'),
                          *(Path('experiments')/(m+'.py') for m in ('input_guard','injection_guard','unified_agent','route_service',
                          'document_rag','catalogue_chat','place_catalog','unified_agent_batch','benchmark_reporting'))]}}
    if a.failed_from:
        metadata['previous_report_sha256']=digest(a.failed_from)
    rows=[]
    report={'kind':'live_development' if a.live else 'offline_boundary_check','config':metadata,
            'campaign_complete':False,'results':rows}
    stop=None
    for rep in range(1,repeat+1):
        for case in cases:
            row=evaluate_case(case,client,a.live,a.db,docs,config.get('turn_timeout_seconds',180),capture_rejected=a.private_review)
            row['repetition']=rep
            last=(row.get('provider_calls') or [{}])[-1]
            if last.get('provider_error_code')=='content_filter' or last.get('finish_reason')=='content_filter':
                row['status']='provider_filtered'
                row['automatic_checks_pass']=False
            rows.append(row)
            report['summary']=summarize(rows,planned)
            add_consistency(report,cases,repeat)
            save_report(out,report,a.private_review)
            if row.get('diagnostic_code') in ('provider_error','turn_deadline_exceeded'):
                if row['status']=='provider_filtered':
                    continue
                stop='provider_or_deadline_error'
                break
        if stop:
            break
    metadata['catalogue_sha256_end']=digest(a.db) if a.db.is_file() else None
    if metadata['catalogue_sha256_end']!=metadata['catalogue_sha256_start']:
        stop='catalogue_changed'
    report.update(campaign_complete=len(rows)==planned and stop is None,stop_reason=stop,summary=summarize(rows,planned))
    report['per_category']={k:summarize([r for r in rows if r['category']==k],sum(c['category']==k for c in cases)*repeat)
                            for k in sorted({c['category'] for c in cases})}
    add_consistency(report,cases,repeat)
    save_report(out,report,a.private_review)
    if a.private_review and a.live:
        write_json(out/'grades.private.json',{'run_id':stamp,'rows':[{'id':r['id'],'repetition':r['repetition'],
                   **dict.fromkeys(REVIEW)} for r in rows]})
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2))
    print(out/'report.json')
    if stop:
        p.exit(1,stop+'\n')


if __name__=='__main__':
    main()
