import json
from collections import Counter
from .tools import ROOT
from .evaluation import run_case

OPS={"decision","warnings","entities","fact","call","no_call","max_calls","result","booking_count","booking_status","no_effects","text_absent","simulation","refuse_or_not_found"}
EXPECTED={"search":8,"planning":6,"conversation":6,"uncertainty":4,"faults":4,"booking":4,"injection":4,"authorization":4}

def validate_corpus(cases):
    errors=[]
    if len(cases)!=40:errors.append("Expected 40 development scenarios")
    if len({c["id"] for c in cases})!=len(cases):errors.append("Duplicate case IDs")
    if dict(Counter(c["category"] for c in cases))!=EXPECTED:errors.append("Category counts differ from specification")
    replays=json.loads((ROOT/"data/oracle_replays.json").read_text(encoding="utf-8"))
    sources=json.loads((ROOT/"data/world.json").read_text(encoding="utf-8"))["sources"]
    for case in cases:
        for key in ("ground_truth","source_ids","allowed_actions","human_rubric","annotation_status","reference_clock"):
            if not case.get(key):errors.append(f'{case["id"]}: missing {key}')
        if not set(case["source_ids"])<=set(sources):errors.append(case["id"]+": unknown source")
        for turn in case["turns"]:
            if not turn["checks"]:errors.append(case["id"]+": empty oracle")
            for rule in turn["checks"]:
                if rule["op"] not in OPS:errors.append(case["id"]+": unknown operator")
        try:
            result=run_case(case,replay=replays[case["id"]])
            if not result["auto_pass"]:errors.append({"id":case["id"],"failures":result["failures"],"guard":result["output_guard_errors"]})
        except Exception as exc:errors.append(case["id"]+": "+str(exc))
    return errors

