"""In-memory laboratory executor, NOT a production authorization service."""
import copy
import hashlib
import json
import math
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pydantic import ValidationError
from .contracts import TOOL_MODELS, FinalAnswer, ToolResponse, aware

ROOT = Path(__file__).resolve().parents[1]
WRITES = {"create_simulated_booking", "cancel_simulated_booking"}

def normalize(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.casefold()) if not unicodedata.combining(c))

def distance_m(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    d1, d2 = p2-p1, math.radians(b[1]-a[1])
    h=math.sin(d1/2)**2+math.cos(p1)*math.cos(p2)*math.sin(d2/2)**2
    return round(6371000*2*math.asin(min(1,math.sqrt(h))), 1)

def reply(status="ok", data=None, code=None, retryable=False, missing=None, conflicts=None):
    return ToolResponse(status=status,data=data,error_code=code,retryable=retryable,
            missing_fields=missing or [],conflicts=conflicts or []).model_dump()

class Engine:
    def __init__(self, world=None, actor="alice", now="2026-11-16T12:00:00+00:00", scopes=None,
                 max_calls=8, deadline_seconds=60):
        self.world=copy.deepcopy(world or json.loads((ROOT/"data/world.json").read_text(encoding="utf-8")))
        self.actor=actor
        self.now=aware(now)
        self.scopes=set(TOOL_MODELS) if scopes is None else set(scopes)
        self.max_calls=max_calls
        self.deadline_seconds=deadline_seconds
        self.trace=[]
        self.audit=[]
        self.quotes={}
        self.bookings=copy.deepcopy(self.world.get("bookings",{}))
        self.approvals={}
        self.quote_bookings={}
        self.exposed={}
        self.failures={}
        self.lock=threading.RLock()
        self.begin_turn()

    def begin_turn(self):
        self.turn_calls=0
        self.started=time.monotonic()
        self.transient_attempts={}

    def _key(self,name,args):
        return hashlib.sha256(json.dumps([self.actor,name,args],sort_keys=True).encode()).hexdigest()

    def approve(self,name,args,ttl_seconds=300):
        """Trusted HOST event only. Never registered as a model tool."""
        if name not in WRITES:
            raise ValueError("Only exact mutation approvals are supported")
        args=TOOL_MODELS[name].model_validate(args).model_dump()
        with self.lock:
            if name=="create_simulated_booking":
                target=self.quotes.get(args["quote_id"])
            else:
                target=self.bookings.get(args["booking_id"])
            if not target or target["owner"]!=self.actor:
                raise ValueError("Cannot approve inaccessible target")
            self.approvals[self._key(name,args)]=self.now+timedelta(seconds=ttl_seconds)

    def _consume_approval(self,name,args):
        key=self._key(name,args)
        expiry=self.approvals.get(key)
        if expiry is None or expiry<=self.now:
            return False
        del self.approvals[key]
        self.audit.append({"event":"approval_consumed","actor":self.actor,"tool":name,"args":args})
        return True

    def _expose(self,entity):
        self.exposed[entity["id"]]=copy.deepcopy(entity)
        return copy.deepcopy(entity)

    def call(self,name,args):
        start=time.monotonic()
        with self.lock:
            self.turn_calls+=1
            if self.turn_calls>self.max_calls:
                result=reply("forbidden",code="CALL_BUDGET_EXCEEDED")
            elif time.monotonic()-self.started>self.deadline_seconds:
                result=reply("unavailable",code="DEADLINE_EXCEEDED")
            elif name not in TOOL_MODELS or name not in self.scopes:
                result=reply("forbidden",code="TOOL_NOT_ALLOWED")
            else:
                try:
                    parsed=TOOL_MODELS[name].model_validate(args).model_dump()
                except (ValidationError,TypeError,ValueError):
                    # Do not echo arbitrary arguments or secrets in an error.
                    result=reply("invalid",code="INVALID_ARGUMENTS")
                else:
                    signature=self._key(name,parsed)
                    if self.transient_attempts.get(signature,0)>=3:
                        result=reply("unavailable",code="RETRY_LIMIT_EXCEEDED")
                    else:
                        faults=self.failures.get(name,[])
                        fault=faults.pop(0) if faults else None
                        if fault in ("TIMEOUT","RATE_LIMIT","MALFORMED_RESPONSE"):
                            result=reply("unavailable",code=fault,retryable=fault!="MALFORMED_RESPONSE")
                        else:
                            result=getattr(self,"_"+name)(parsed)
                            if fault=="TIMEOUT_AFTER_COMMIT" and result["status"]=="ok":
                                result=reply("unavailable",code="TIMEOUT",retryable=True)
                        if result["retryable"]:
                            self.transient_attempts[signature]=self.transient_attempts.get(signature,0)+1
            self.trace.append({"tool":name,"arguments":copy.deepcopy(args),"result":copy.deepcopy(result),
                               "latency_ms":round((time.monotonic()-start)*1000,3)})
            return result

    def _search_places(self,a):
        matches=[]
        for p in self.world["places"]:
            if a["category"] and p["category"]!=a["category"]:continue
            if a["district"] and normalize(p["district"])!=normalize(a["district"]):continue
            if a["query"] and normalize(a["query"]) not in normalize(p["name"]):continue
            if a["wifi_required"] and p.get("wifi") is not True:continue
            p=copy.deepcopy(p)
            if a["radius_m"] is not None:
                d=distance_m((a["latitude"],a["longitude"]),(p["latitude"],p["longitude"]))
                if d>a["radius_m"]:continue
                p["distance_m"]=d
            matches.append(p)
        matches.sort(key=lambda p:(p.get("distance_m",0),p["id"]))
        items=[self._expose(p) for p in matches[:a["limit"]]]
        return reply("ok" if items else "no_results",{"items":items,"total":len(matches),
            "coverage":"small_historical_fixture_not_exhaustive","current_activity_verified":False})

    def _search_events(self,a):
        start,end=aware(a["start"]),aware(a["end"])
        items=[self._expose(e) for e in self.world["events"] if aware(e["start"])<end and aware(e["end"])>start
               and (not a["theme"] or normalize(a["theme"]) in normalize(e["name"]+" "+e["theme"]))]
        return reply("ok" if items else "no_results",{"items":items[:a["limit"]],"total":len(items),
            "coverage":"selected_official_programme_only"})

    def _get_entity_details(self,a):
        e=next((e for e in self.world["places"]+self.world["events"] if e["id"]==a["entity_id"]),None)
        if not e:return reply("not_found",code="NOT_FOUND")
        missing=[k for k in ("wifi","opening_hours","price_xof") if e.get(k) is None] if e in self.world["places"] else []
        return reply("partial" if missing or e.get("conflicts") else "ok",self._expose(e),missing=missing,conflicts=e.get("conflicts",[]))

    def _search_knowledge(self,a):
        words=set(normalize(a["query"]).replace("?", "").split())-{"de","la","le","les","en","a","et","the","of","is"}
        scored=[]
        for d in self.world["documents"]:
            score=sum(w in normalize(d["text"]+" "+d["name"]) for w in words)
            if score:scored.append((score,d))
        scored.sort(key=lambda x:(-x[0],x[1]["id"]))
        items=[self._expose(d) for _,d in scored[:a["limit"]]]
        return reply("ok" if items else "no_results",{"items":items,"retrieval":"lexical_baseline"})

    def _plan_itinerary(self,a):
        places={p["id"]:p for p in self.world["places"]}
        if any(i not in places for i in a["place_ids"]):return reply("not_found",code="NOT_FOUND")
        start,end=aware(a["start"]),aware(a["end"])
        t=start; missing=[]; violations=[]; steps=[]; known_cost=0
        timing_known=True
        for idx,pid in enumerate(a["place_ids"]):
            p=places[pid]
            if idx:
                key=f'{a["mode"]}:{a["place_ids"][idx-1]}:{pid}'
                minutes=self.world["route_minutes"].get(key)
                if minutes is None:
                    missing.append("travel_time:"+key);timing_known=False
                elif timing_known:t+=timedelta(minutes=minutes)
            windows=p.get("opening_windows")
            if windows is None:missing.append("opening_hours:"+pid)
            elif timing_known:
                feasible_windows=[(aware(w[0]),aware(w[1])) for w in windows if aware(w[1])>=t+timedelta(minutes=a["visit_minutes"])]
                if not feasible_windows:violations.append("closed:"+pid)
                else:
                    op,cl=min(feasible_windows)
                    t=max(t,op)
                    if t+timedelta(minutes=a["visit_minutes"])>cl:violations.append("closed:"+pid)
            arrival=t if timing_known else None
            if timing_known:t+=timedelta(minutes=a["visit_minutes"])
            steps.append({"place_id":pid,"arrival":arrival.isoformat() if arrival else None,
                          "departure":t.isoformat() if timing_known else None})
            price=p.get("price_xof")
            if price is None:missing.append("price:"+pid)
            else:known_cost+=price
        transport=self.world.get("transport_cost_xof") if len(a["place_ids"])>1 else 0
        if transport is None:missing.append("transport_cost")
        else:known_cost+=transport
        if timing_known and t>end:violations.append("time_budget")
        if a["budget_xof"] is not None and known_cost>a["budget_xof"]:violations.append("money_budget")
        feasible=False if violations else None if missing else True
        return reply("partial" if missing else "ok",{"feasible":feasible,"steps":steps,
            "violations":violations,"known_cost_xof":known_cost,"total_cost_xof":None if any(x.startswith("price:") or x=="transport_cost" for x in missing) else known_cost,
            "simulation":True,"route_basis":"controlled_fixture_only","optimization":"input_order_feasibility_only"},missing=missing)

    def _get_booking_quote(self,a):
        p=next((p for p in self.world["places"] if p["id"]==a["place_id"]),None)
        if not p:return reply("not_found",code="NOT_FOUND")
        if aware(a["start"])<=self.now:return reply("invalid",code="DATE_IN_PAST")
        qid="Q"+str(len(self.quotes)+1)
        quote={"quote_id":qid,"owner":self.actor,**a,"amount_xof":10000*a["guests"],
               "currency":"XOF","simulation":True,"service":"sandbox_test_service_not_a_real_offer",
               "expires_at":(self.now+timedelta(minutes=5)).isoformat()}
        self.quotes[qid]=quote
        return reply(data={k:v for k,v in quote.items() if k!="owner"})

    def _create_simulated_booking(self,a):
        q=self.quotes.get(a["quote_id"])
        if not q or q["owner"]!=self.actor:return reply("not_found",code="NOT_FOUND")
        old=self.quote_bookings.get(q["quote_id"])
        if old:return self._get_simulated_booking({"booking_id":old})
        if aware(q["expires_at"])<=self.now:return reply("invalid",code="QUOTE_EXPIRED")
        if not self._consume_approval("create_simulated_booking",a):return reply("forbidden",code="APPROVAL_REQUIRED")
        bid="B"+str(len(self.bookings)+1)
        self.bookings[bid]={"booking_id":bid,"owner":self.actor,"quote_id":q["quote_id"],
            "place_id":q["place_id"],"status":"confirmed_simulated","simulation":True,"amount_xof":q["amount_xof"]}
        self.quote_bookings[q["quote_id"]]=bid
        self.audit.append({"event":"booking_created","booking_id":bid,"actor":self.actor})
        return self._get_simulated_booking({"booking_id":bid})

    def _get_simulated_booking(self,a):
        b=self.bookings.get(a["booking_id"])
        if not b or b["owner"]!=self.actor:return reply("not_found",code="NOT_FOUND")
        return reply(data={k:v for k,v in b.items() if k!="owner"})

    def _cancel_simulated_booking(self,a):
        b=self.bookings.get(a["booking_id"])
        if not b or b["owner"]!=self.actor:return reply("not_found",code="NOT_FOUND")
        if b["status"]=="cancelled_simulated":return self._get_simulated_booking(a)
        if not self._consume_approval("cancel_simulated_booking",a):return reply("forbidden",code="APPROVAL_REQUIRED")
        b["status"]="cancelled_simulated"
        self.audit.append({"event":"booking_cancelled","booking_id":b["booking_id"],"actor":self.actor})
        return self._get_simulated_booking(a)

    def validate_final(self,payload):
        """Check declared facts against actually exposed evidence, not arbitrary prose."""
        try: final=FinalAnswer.model_validate(payload)
        except (ValidationError,TypeError):return ["INVALID_FINAL_SCHEMA"]
        errors=[]
        # Simulation steps are evidence only for the IDs and timestamps actually
        # returned by the tool; they are not source documents about the places.
        steps=[]
        booking_evidence=[]
        for t in self.trace:
            result=t.get("result",{})
            if t.get("tool")=="plan_itinerary" and result.get("status") in ("ok","partial"):
                steps.extend((result.get("data") or {}).get("steps",[]))
            if t.get("tool") in ("get_booking_quote","create_simulated_booking","get_simulated_booking","cancel_simulated_booking") and result.get("status")=="ok":
                data=result.get("data") or {}
                if t["tool"]=="get_booking_quote":
                    owner_record=self.quotes.get(data.get("quote_id"))
                else:
                    owner_record=self.bookings.get(data.get("booking_id"))
                if owner_record and owner_record.get("owner")==self.actor and data.get("simulation") is True:
                    booking_evidence.append((t["tool"],data))
        simulated_ids={s.get("place_id") for s in steps}
        booking_ids={d[k] for _,d in booking_evidence for k in ("quote_id","booking_id","place_id") if isinstance(d.get(k),str)}
        for eid in final.entity_ids:
            if eid not in self.exposed and eid not in simulated_ids and not (final.simulation and eid in booking_ids):errors.append("UNSEEN_ENTITY:"+eid)
        for fact in final.facts:
            e=self.exposed.get(fact.entity_id)
            if fact.source_id in ("get_booking_quote","functions.get_booking_quote"):
                matches=[d for name,d in booking_evidence if name=="get_booking_quote" and fact.entity_id==d.get("quote_id")]
                if not final.simulation or not any(fact.field in d and type(d[fact.field]) is type(fact.value) and d[fact.field]==fact.value for d in matches):
                    errors.append("UNSUPPORTED_FACT")
                continue
            if fact.source_id in ("plan_itinerary","functions.plan_itinerary") and fact.field in ("start","end"):
                field={"start":"arrival","end":"departure"}[fact.field]
                if not final.simulation or not any(s.get("place_id")==fact.entity_id and type(s.get(field)) is type(fact.value) and s.get(field)==fact.value for s in steps):
                    errors.append("UNSUPPORTED_FACT")
                continue
            if not e or fact.field not in e or e[fact.field]!=fact.value or type(e[fact.field])!=type(fact.value):
                errors.append("UNSUPPORTED_FACT")
            elif e.get("field_sources",{}).get(fact.field,e.get("source_id"))!=fact.source_id:
                errors.append("INVALID_CITATION")
        if final.booking_id or final.booking_status:
            b=self.bookings.get(final.booking_id)
            if not b or b["owner"]!=self.actor or b["status"]!=final.booking_status or not final.simulation:
                errors.append("FALSE_BOOKING_CLAIM")
            elif not any(t["result"].get("data",{}).get("booking_id")==final.booking_id
                         for t in self.trace if isinstance(t["result"].get("data"),dict)):
                errors.append("UNOBSERVED_BOOKING")
        return errors


