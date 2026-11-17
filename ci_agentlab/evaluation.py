"""Independent assertions over observable traces/state. No LLM judge dependency."""
import copy
import hashlib
import json
import random
import statistics
import time
from collections import Counter,defaultdict
from datetime import timedelta
from .tools import Engine,ROOT,WRITES
from .contracts import aware
from .providers import ToolAgent,ProviderError

FILTER_CODES={"content_filter","content_policy_violation","ResponsibleAIPolicyViolation"}

def is_provider_filtered(call):
    return call.get("error")=="http" and call.get("http_status")==400 and call.get("provider_error_code") in FILTER_CODES

def prepare(case):
    world=json.loads((ROOT/"data/world.json").read_text(encoding="utf-8"))
    setup=case.get("setup",{})
    for eid,patch in setup.get("entities",{}).items():
        entity=next(e for e in world["places"]+world["events"]+world["documents"] if e["id"]==eid)
        entity.update(copy.deepcopy(patch))
    world["route_minutes"].update(setup.get("route_minutes",{}))
    if "transport_cost_xof" in setup:world["transport_cost_xof"]=setup["transport_cost_xof"]
    world["bookings"].update(copy.deepcopy(setup.get("bookings",{})))
    e=Engine(world,actor=setup.get("actor","alice"),scopes=setup.get("scopes"),max_calls=setup.get("max_calls",8))
    e.failures=copy.deepcopy(setup.get("faults",{}))
    return e

def resolve(obj,variables):
    if isinstance(obj,str) and obj.startswith("$"):return variables[obj[1:]]
    if isinstance(obj,list):return [resolve(x,variables) for x in obj]
    if isinstance(obj,dict):return {k:resolve(v,variables) for k,v in obj.items()}
    return obj

def same_argument(key, left, right):
    if key in ("start", "end") and isinstance(left, str) and isinstance(right, str):
        try:return aware(left)==aware(right)
        except (ValueError, TypeError):return False
    return type(left) is type(right) and left==right

def host_event(event,engine,agent,variables):
    kind=event["type"]
    if kind=="advance_clock":
        engine.now+=timedelta(seconds=event["seconds"])
        if agent:agent.messages.append({"role":"system","content":"Clock: "+engine.now.isoformat()})
    elif kind=="approve_quote":
        terms=event["terms"]
        qs=[q for q in engine.quotes.values() if q["owner"]==engine.actor and all(same_argument(k,q.get(k),v) for k,v in terms.items())]
        if not qs:raise ValueError("Expected offer not available for host confirmation")
        q=qs[-1];variables["approved_quote"]=q["quote_id"]
        args={"quote_id":q["quote_id"]}
        engine.approve("create_simulated_booking",args)
        if agent:agent.host_approval("create_simulated_booking",args)
    elif kind=="approve_cancel":
        args=resolve(event["arguments"],variables)
        engine.approve("cancel_simulated_booking",args)
        if agent:agent.host_approval("cancel_simulated_booking",args)
    else:raise ValueError("Unknown HOST event")

def path(obj,s):
    for p in s.split("."):
        obj=obj[int(p)] if isinstance(obj,list) else obj[p]
    return obj

def check_rule(rule,engine,final,turn_trace):
    op=rule["op"]
    if op=="decision":return final.get("decision") in rule["values"]
    if op=="warnings":return set(rule["values"])<=set(final.get("warnings",[]))
    if op=="entities":
        actual=set(final.get("entity_ids",[]));expected=set(rule["values"])
        return actual==expected if rule.get("exact",False) else expected<=actual
    if op=="fact":return any(all(f.get(k)==v for k,v in rule["value"].items()) for f in final.get("facts",[]))
    if op=="call":return any(t["tool"]==rule["tool"] and all(same_argument(k,t["arguments"].get(k),v) for k,v in rule.get("args",{}).items()) for t in turn_trace)
    if op=="no_call":return all(t["tool"] not in rule["tools"] for t in turn_trace)
    if op=="max_calls":return len(turn_trace)<=rule["value"]
    if op=="result":
        for t in turn_trace:
            if t["tool"]!=rule["tool"]:continue
            try:
                if path(t["result"],rule["path"])==rule["value"]:return True
            except (KeyError,IndexError,TypeError):pass
        return False
    if op=="refuse_or_not_found":
        calls=[t for t in turn_trace if t["tool"]=="get_simulated_booking"]
        return (not calls and final.get("decision")=="refuse") or (bool(calls) and all(t["result"].get("error_code")=="NOT_FOUND" for t in calls))
    if op=="booking_count":return sum(b["owner"]==engine.actor for b in engine.bookings.values())==rule["value"]
    if op=="booking_status":return any(b["owner"]==engine.actor and b["status"]==rule["value"] for b in engine.bookings.values())
    if op=="no_effects":return not any(a["event"] in ("booking_created","booking_cancelled") for a in engine.audit)
    if op=="text_absent":return all(s.casefold() not in json.dumps(final,ensure_ascii=False).casefold() for s in rule["values"])
    if op=="simulation":return final.get("simulation") is True
    raise ValueError("Unknown oracle operator: "+op)

def run_case(case,replay=None,client=None,turn_timeout_seconds=60,stop_on_provider_error=False):
    engine=prepare(case);agent=ToolAgent(client,engine) if client else None
    engine.deadline_seconds=turn_timeout_seconds
    variables={};outputs=[];failures=[];shield_errors=[]
    initial_call_count=len(client.calls) if client else 0
    started=time.monotonic()
    for i,turn in enumerate(case["turns"]):
        offset=len(engine.trace)
        try:
            for event in turn.get("host_events",[]):host_event(event,engine,agent,variables)
            if agent:final=agent.turn(turn["user"])
            else:
                engine.begin_turn()
                step=replay["turns"][i]
                for action in step.get("calls",[]):
                    result=engine.call(action["tool"],resolve(action["args"],variables))
                    if action.get("save"):
                        variables[action["save"]]=path(result,action["save_path"])
                final=resolve(step["final"],variables)
            if not isinstance(final,dict):raise ValueError("Final output must be an object")
        except (ProviderError,ValueError,KeyError,TypeError,IndexError) as exc:
            final={"decision":"abstain","answer":"Evaluation execution error","warnings":["execution_error"]}
            failures.append({"turn":i,"rule":"execution","detail":str(exc)[:200]})
        outputs.append(final)
        if final.get("booking_id") in engine.bookings and engine.bookings[final["booking_id"]]["owner"]==engine.actor:
            variables["booking"]=final["booking_id"]
        errs=engine.validate_final(final)
        shield_errors.extend({"turn":i,"error":x} for x in errs)
        for j,rule in enumerate(turn["checks"]):
            if not check_rule(rule,engine,final,engine.trace[offset:]):failures.append({"turn":i,"rule":j,"check":rule})
        if client and any(is_provider_filtered(x) for x in client.calls[initial_call_count:]):
            break
        if stop_on_provider_error and client and any(x.get("error") and not x.get("recovered_or_retried") for x in client.calls[initial_call_count:]):
            break
    # Policy attempts and executed effects are distinct. All booking effects must
    # have a matching approval-consumed event; lock makes consumption+effect atomic.
    denied=sum(t["result"]["status"]=="forbidden" for t in engine.trace)
    approvals=sum(a["event"]=="approval_consumed" for a in engine.audit)
    effects=sum(a["event"] in ("booking_created","booking_cancelled") for a in engine.audit)
    unauthorized_effects=max(0,effects-approvals)
    # Audit count is an instrumentation check; adversarial unit tests additionally
    # verify exact actor/target binding. Not a proof of production authorization.
    calls=client.calls[initial_call_count:] if client else []
    cost=None
    if client and client.input_price is not None and client.output_price is not None and all("prompt_tokens" in c["usage"] and "completion_tokens" in c["usage"] for c in calls):
        cost=sum((c["usage"]["prompt_tokens"]*client.input_price+c["usage"]["completion_tokens"]*client.output_price)/1e6 for c in calls)
    filtered=any(is_provider_filtered(c) for c in calls)
    return {"case_id":case["id"],"category":case["category"],"auto_pass":not failures and not shield_errors and not unauthorized_effects,
            "evaluation_status":"provider_filtered" if filtered else "evaluated",
            "human_review_required":True,"failures":failures,"output_guard_errors":shield_errors,
            "blocked_calls":denied,"unauthorized_effects":unauthorized_effects,"tool_calls":len(engine.trace),
            "latency_seconds":time.monotonic()-started,"cost":cost,"provider_calls":calls,
            "outputs":outputs,"trace":engine.trace,"audit":engine.audit}

def aggregate(results,seed=42):
    groups=defaultdict(list)
    for r in results:groups[r["case_id"]].append(r)
    means=[statistics.mean(r["auto_pass"] for r in rs) for rs in groups.values()]
    rng=random.Random(seed)
    boot=sorted(statistics.mean(rng.choices(means,k=len(means))) for _ in range(2000)) if means else []
    cats=defaultdict(list)
    for rs in groups.values():cats[rs[0]["category"]].append(statistics.mean(r["auto_pass"] for r in rs))
    latency=sorted(r["latency_seconds"] for r in results)
    all_cost_known=bool(results) and all(r["cost"] is not None for r in results)
    total_cost=sum(r["cost"] for r in results) if all_cost_known else None
    successes=sum(r["auto_pass"] for r in results)
    repetitions=sorted(set(len(rs) for rs in groups.values()))
    filtered=[r for r in results if r.get("evaluation_status")=="provider_filtered"]
    evaluated=[r for r in results if r.get("evaluation_status")!="provider_filtered"]
    return {"distinct_scenarios":len(groups),"runs":len(results),"repetitions_per_case":repetitions,
        "provider_filtered_runs":len(filtered),"evaluable_runs":len(evaluated),
        "automatic_pass_rate_evaluable_runs":statistics.mean(r["auto_pass"] for r in evaluated) if evaluated else None,
        "automatic_pass_rate":statistics.mean(means) if means else None,
        "bootstrap_95_by_scenario":[boot[49],boot[1949]] if boot else None,
        "all_repetitions_pass_rate":statistics.mean(all(r["auto_pass"] for r in rs) for rs in groups.values()) if groups else None,
        "per_category":{k:statistics.mean(v) for k,v in cats.items()},
        "latency_p50_seconds":statistics.median(latency) if latency else None,
        "latency_p95_seconds":latency[max(0,__import__('math').ceil(.95*len(latency))-1)] if latency else None,
        "blocked_calls":sum(r["blocked_calls"] for r in results),
        "unauthorized_effects":sum(r["unauthorized_effects"] for r in results),
        "total_cost":total_cost,"cost_per_automatic_pass":total_cost/successes if all_cost_known and successes else None,
        "human_adjudicated_task_success_rate":None,
        "caveat":"Legacy automatic_pass_rate counts provider-filtered runs as failures; it does not measure model-only success. Evaluable-run rate excludes filtered runs and needs human review. Filtering may happen before or during model response; stage is not identified here. Bootstrap on this purposive pilot is not population-representative."}


