"""Persist shareable benchmark metrics, with a separately requested review copy."""
import json
from pathlib import Path


def write_json(path, data):
    path=Path(path)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    tmp.replace(path)


def save_report(out, report, private=False):
    # Project from an allowlist. Free text can recur in outputs, traces, arguments,
    # error strings and even provider metadata. Only case IDs from test manifests are public.
    fields=('id','category','status','repetition','diagnostic_code','tool_selection_match',
            'outcome_checks_pass','argument_checks_pass','forbidden_tools_pass','outcome_checks',
            'route_status','provider_http_status','elapsed_seconds','response_origin','automatic_checks_pass','quality_checks','human_review_required')
    safe={key:report[key] for key in ('kind','campaign_complete','stop_reason','summary','per_category','per_case','config') if key in report}
    safe['results']=[]
    for row in report['results']:
        item={key:row[key] for key in fields if key in row}
        item['abstain']=(row.get('output') or {}).get('abstain')
        item['provider_attempts']=len(row.get('provider_calls',[]))
        item['tools']=[t for t in row.get('observed_tools',[]) if t in ('search_catalogue','search_documents','calculate_route')]
        safe['results'].append(item)
    if private:
        write_json(out/'review.private.json',report)
    write_json(out/'report.json',safe)
