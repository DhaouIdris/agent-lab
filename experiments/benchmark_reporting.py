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
            'route_status','provider_http_status','elapsed_seconds','response_origin','automatic_checks_pass','quality_checks','human_review_required','abstention_convention_match')
    safe={key:report[key] for key in ('kind','campaign_complete','stop_reason','summary','per_category','per_case','config') if key in report}
    safe['results']=[]
    for row in report['results']:
        item={key:row[key] for key in fields if key in row}
        metadata=row.get('diagnostic_metadata',{})
        counts=('content_length','unobserved_id_count','parent_id_confusion_count','unverified_numeric_mention_count')
        item['diagnostic_metadata']={key:metadata[key] for key in counts if type(metadata.get(key)) is int}
        if metadata.get('content_kind') in ('empty','string','non_string'):
            item['diagnostic_metadata']['content_kind']=metadata['content_kind']
        if metadata.get('provider_error_kind') in ('timeout','transport','response_json','response_schema'):
            item['diagnostic_metadata']['provider_error_kind']=metadata['provider_error_kind']
        item['abstain']=(row.get('output') or {}).get('abstain')
        item['provider_attempts']=len(row.get('provider_calls',[]))
        item['tools']=[t for t in row.get('observed_tools',[]) if t in ('search_catalogue','search_documents','calculate_route','rank_nearby','resolve_origin')]
        safe['results'].append(item)
    if private:
        write_json(out/'review.private.json',report)
    write_json(out/'report.json',safe)
