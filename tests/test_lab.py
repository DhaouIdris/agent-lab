import copy
import json
import threading
import unittest
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from pydantic import ValidationError
from ci_agentlab.contracts import TOOL_MODELS,FinalAnswer
from ci_agentlab.tools import Engine,ROOT,distance_m
from ci_agentlab.evaluation import run_case,aggregate
from ci_agentlab.validation import validate_corpus
from ci_agentlab.providers import ToolAgent,ProviderError,ChatClient
from ci_agentlab.comparison import compare

QUOTE={"place_id":"P1","start":"2026-11-20T12:00:00+00:00","guests":2}

def quote(e,args=None):return e.call("get_booking_quote",args or QUOTE)["data"]["quote_id"]
def approve_create(e,q):e.approve("create_simulated_booking",{"quote_id":q})
def create(e,q):return e.call("create_simulated_booking",{"quote_id":q})

class Contracts(unittest.TestCase):
    def test_all_nine_have_closed_schemas(self):
        self.assertEqual(len(TOOL_MODELS),9)
        for model in TOOL_MODELS.values():self.assertFalse(model.model_json_schema()["additionalProperties"])
    def test_boolean_is_not_integer_guests(self):
        self.assertEqual(Engine().call("get_booking_quote",{**QUOTE,"guests":True})["error_code"],"INVALID_ARGUMENTS")
    def test_numeric_string_is_rejected(self):
        self.assertEqual(Engine().call("search_places",{"limit":"5"})["error_code"],"INVALID_ARGUMENTS")
    def test_forged_confirmation_argument(self):
        e=Engine();q=quote(e)
        r=e.call("create_simulated_booking",{"quote_id":q,"user_confirmed":True})
        self.assertEqual(r["error_code"],"INVALID_ARGUMENTS");self.assertEqual(e.bookings,{})
    def test_radius_requires_coordinates(self):
        self.assertEqual(Engine().call("search_places",{"radius_m":500})["error_code"],"INVALID_ARGUMENTS")
    def test_reversed_dates(self):
        self.assertEqual(Engine().call("search_events",{"start":"2026-11-20T00:00:00Z","end":"2026-11-19T00:00:00Z"})["error_code"],"INVALID_ARGUMENTS")
    def test_naive_dates(self):
        self.assertEqual(Engine().call("search_events",{"start":"2026-11-20","end":"2026-11-21"})["error_code"],"INVALID_ARGUMENTS")
    def test_nan_coords(self):
        self.assertEqual(Engine().call("search_places",{"latitude":float("nan"),"longitude":0.,"radius_m":1})["error_code"],"INVALID_ARGUMENTS")
    def test_duplicate_itinerary_stops(self):
        a={"place_ids":["P1","P1"],"start":"2026-11-20T09:00:00Z","end":"2026-11-20T12:00:00Z"}
        self.assertEqual(Engine().call("plan_itinerary",a)["error_code"],"INVALID_ARGUMENTS")

class Authorization(unittest.TestCase):
    def test_unknown_tool_fails_closed(self):
        self.assertEqual(Engine().call("execute_shell",{"command":"anything"})["error_code"],"TOOL_NOT_ALLOWED")
    def test_scopes(self):
        self.assertEqual(Engine(scopes=[]).call("search_places",{})["error_code"],"TOOL_NOT_ALLOWED")
    def test_missing_approval_has_no_effect(self):
        e=Engine();r=create(e,quote(e))
        self.assertEqual(r["error_code"],"APPROVAL_REQUIRED");self.assertFalse(e.bookings)
    def test_approval_binds_exact_quote(self):
        e=Engine();q1=quote(e);q2=quote(e,{**QUOTE,"guests":4});approve_create(e,q1)
        self.assertEqual(create(e,q2)["error_code"],"APPROVAL_REQUIRED")
        self.assertEqual(create(e,q1)["status"],"ok")
    def test_approval_binds_actor(self):
        e=Engine();q=quote(e);approve_create(e,q);e.actor="bob"
        self.assertEqual(create(e,q)["error_code"],"NOT_FOUND")
    def test_expired_approval(self):
        e=Engine();q=quote(e);e.approve("create_simulated_booking",{"quote_id":q},ttl_seconds=10)
        e.now+=timedelta(seconds=11)
        self.assertEqual(create(e,q)["error_code"],"APPROVAL_REQUIRED")
    def test_expired_quote_even_with_valid_approval(self):
        e=Engine();q=quote(e);e.approve("create_simulated_booking",{"quote_id":q},ttl_seconds=600)
        e.now+=timedelta(seconds=301)
        self.assertEqual(create(e,q)["error_code"],"QUOTE_EXPIRED")
    def test_approval_is_consumed(self):
        e=Engine();q=quote(e);approve_create(e,q);create(e,q)
        self.assertFalse(e.approvals)
    def test_create_idempotent(self):
        e=Engine();q=quote(e);approve_create(e,q)
        a=create(e,q);b=create(e,q)
        self.assertEqual(a,b);self.assertEqual(len(e.bookings),1)
    def test_concurrent_create_has_one_effect(self):
        e=Engine(max_calls=100);q=quote(e);approve_create(e,q)
        with ThreadPoolExecutor(max_workers=8) as pool:rs=list(pool.map(lambda _:create(e,q),range(20)))
        self.assertEqual(len({r["data"]["booking_id"] for r in rs}),1)
        self.assertEqual(sum(a["event"]=="booking_created" for a in e.audit),1)
    def test_lost_response_after_commit(self):
        e=Engine();q=quote(e);approve_create(e,q);e.failures={"create_simulated_booking":["TIMEOUT_AFTER_COMMIT"]}
        self.assertEqual(create(e,q)["error_code"],"TIMEOUT")
        self.assertEqual(create(e,q)["status"],"ok");self.assertEqual(len(e.bookings),1)
    def test_other_user_and_unknown_indistinguishable(self):
        e=Engine();q=quote(e);approve_create(e,q);bid=create(e,q)["data"]["booking_id"];e.actor="bob"
        for name in ("get_simulated_booking","cancel_simulated_booking"):
            self.assertEqual(e.call(name,{"booking_id":bid}),e.call(name,{"booking_id":"does_not_exist"}))
    def test_cancel_requires_separate_approval(self):
        e=Engine();q=quote(e);approve_create(e,q);bid=create(e,q)["data"]["booking_id"]
        self.assertEqual(e.call("cancel_simulated_booking",{"booking_id":bid})["error_code"],"APPROVAL_REQUIRED")
    def test_cancel_idempotent_after_exact_approval(self):
        e=Engine();q=quote(e);approve_create(e,q);bid=create(e,q)["data"]["booking_id"]
        a={"booking_id":bid};e.approve("cancel_simulated_booking",a)
        self.assertEqual(e.call("cancel_simulated_booking",a),e.call("cancel_simulated_booking",a))
        self.assertEqual(e.bookings[bid]["status"],"cancelled_simulated")

class EvidenceAndFaults(unittest.TestCase):
    def test_haversine_independent_known_distance(self):
        self.assertAlmostEqual(distance_m((0,0),(0,1)),111194.9,delta=1)
    def test_wifi_unknown_is_not_true(self):
        r=Engine().call("search_places",{"wifi_required":True})
        self.assertEqual(r["status"],"no_results")
    def test_empty_does_not_mean_outage(self):
        e=Engine();empty=e.call("search_places",{"category":"cafe"});e.failures={"search_places":["TIMEOUT"]}
        outage=e.call("search_places",{"category":"cafe"})
        self.assertEqual(empty["status"],"no_results");self.assertEqual(outage["status"],"unavailable")
    def test_event_end_is_exclusive(self):
        r=Engine().call("search_events",{"start":"2026-11-23T00:00:00Z","end":"2026-11-24T00:00:00Z"})
        self.assertEqual(r["status"],"no_results")
    def test_retry_cap(self):
        e=Engine();e.failures={"search_places":["TIMEOUT"]*5}
        for _ in range(3):self.assertTrue(e.call("search_places",{})["retryable"])
        self.assertEqual(e.call("search_places",{})["error_code"],"RETRY_LIMIT_EXCEEDED")
    def test_call_cap(self):
        e=Engine(max_calls=1);e.call("search_places",{})
        self.assertEqual(e.call("search_places",{})["error_code"],"CALL_BUDGET_EXCEEDED")
    def test_expired_turn_deadline(self):
        e=Engine();e.started-=61
        self.assertEqual(e.call("search_places",{})["error_code"],"DEADLINE_EXCEEDED")
    def test_unseen_entity_rejected(self):
        self.assertIn("UNSEEN_ENTITY:P1",Engine().validate_final({"decision":"answer","answer":"x","entity_ids":["P1"]}))
    def test_citation_must_match_exposed_fact(self):
        e=Engine();e.call("get_entity_details",{"entity_id":"P1"})
        f={"decision":"answer","answer":"x","facts":[{"entity_id":"P1","field":"wifi","value":True,"source_id":"S_OSM"}]}
        self.assertIn("UNSUPPORTED_FACT",e.validate_final(f))
    def test_wrong_source_rejected(self):
        e=Engine();e.call("get_entity_details",{"entity_id":"P1"})
        f={"decision":"answer","answer":"x","facts":[{"entity_id":"P1","field":"name","value":"Nuit de Saïgon","source_id":"S_UNESCO"}]}
        self.assertIn("INVALID_CITATION",e.validate_final(f))
    def test_false_booking_status_rejected(self):
        e=Engine()
        f={"decision":"answer","answer":"x","booking_id":"B999","booking_status":"confirmed_simulated","simulation":True}
        self.assertIn("FALSE_BOOKING_CLAIM",e.validate_final(f))
    def test_free_text_is_explicitly_not_semantically_verified(self):
        # Documents a limit, not a security guarantee: human adjudication required.
        f={"decision":"answer","answer":"This unsupported sentence is outside structured fact verification."}
        self.assertEqual(Engine().validate_final(f),[])

class Harness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=json.loads((ROOT/"data/scenarios.json").read_text())
        cls.replays=json.loads((ROOT/"data/oracle_replays.json").read_text())
    def test_all_40_gold_replays(self):
        self.assertEqual(validate_corpus(self.cases),[])
    def test_wrong_year_is_detected(self):
        c=next(c for c in self.cases if c["id"]=="S07");r=copy.deepcopy(self.replays["S07"])
        r["turns"][0]["final"]["facts"][0]["value"]=2013
        self.assertFalse(run_case(c,replay=r)["auto_pass"])
    def test_missing_search_is_detected(self):
        c=next(c for c in self.cases if c["id"]=="S01");r=copy.deepcopy(self.replays["S01"])
        r["turns"][0]["calls"]=[]
        self.assertFalse(run_case(c,replay=r)["auto_pass"])
    def test_injection_extra_mutation_is_detected_even_if_blocked(self):
        c=next(c for c in self.cases if c["id"]=="I02");r=copy.deepcopy(self.replays["I02"])
        r["turns"][0]["calls"].append({"tool":"create_simulated_booking","args":{"quote_id":"Q1"}})
        out=run_case(c,replay=r)
        self.assertFalse(out["auto_pass"]);self.assertEqual(out["unauthorized_effects"],0)
    def test_repeat_count_does_not_inflate_scenario_count(self):
        rs=[]
        for c in self.cases[:2]:
            for _ in range(3):rs.append(run_case(c,replay=self.replays[c["id"]]))
        a=aggregate(rs)
        self.assertEqual(a["distinct_scenarios"],2);self.assertEqual(a["runs"],6)
        self.assertIsNone(a["total_cost"]);self.assertIsNone(a["human_adjudicated_task_success_rate"])
    def test_comparison_rejects_oracle_as_model(self):
        with self.assertRaises(ValueError):compare({"kind":"oracle"},{"kind":"oracle"})
    def test_agent_adapter_executes_tools_without_gold(self):
        class Mock:
            def __init__(self):self.n=0
            def chat(self,messages,timeout):
                self.n+=1
                self_check=json.dumps(messages)
                if 'human_rubric' in self_check or 'ground_truth' in self_check:raise AssertionError("Gold leaked")
                if self.n==1:return {"tool_calls":[{"id":"t1","type":"function","function":{"name":"search_places","arguments":"{\"category\":\"restaurant\"}"}}]}
                return {"content":json.dumps({"decision":"answer","answer":"Historique uniquement.","entity_ids":["P1"],"warnings":["stale_data"]})}
        e=Engine();a=ToolAgent(Mock(),e)
        f=a.turn("Trouve un restaurant.")
        self.assertEqual(e.validate_final(f),[]);self.assertEqual(len(e.trace),1)
    def test_agent_round_cap(self):
        class Loop:
            def chat(self,*a,**k):return {"tool_calls":[{"id":"t","type":"function","function":{"name":"search_places","arguments":"{}"}}]}
        with self.assertRaises(ProviderError):ToolAgent(Loop(),Engine(),max_rounds=2).turn("loop")
    def test_endpoint_rejects_insecure_remote(self):
        with self.assertRaises(ValueError):ChatClient("http://example.com/v1","model")
    def test_multiturn_agent_host_confirmation_and_cancel(self):
        case=next(c for c in self.cases if c["id"]=="B04")
        def tc(name,args,i):return {"tool_calls":[{"id":str(i),"type":"function","function":{"name":name,"arguments":json.dumps(args)}}]}
        def f(**kw):return {"content":json.dumps({"decision":"answer","answer":"Simulation uniquement.","simulation":True,**kw})}
        class Mock:
            input_price=None;output_price=None
            def __init__(self):
                self.calls=[]
                self.replies=iter([tc("get_booking_quote",QUOTE,1),f(),tc("create_simulated_booking",{"quote_id":"Q1"},2),
                                  f(booking_id="B1",booking_status="confirmed_simulated"),tc("cancel_simulated_booking",{"booking_id":"B1"},3),
                                  f(booking_id="B1",booking_status="cancelled_simulated")])
            def chat(self,*a,**kw):return next(self.replies)
        result=run_case(case,client=Mock())
        self.assertTrue(result["auto_pass"],result["failures"])
    def test_paired_comparison_uses_same_cases(self):
        a={"kind":"model_test","hashes":{"data":"same"},"results":[{"case_id":"a","repetition":0,"auto_pass":False},{"case_id":"b","repetition":0,"auto_pass":True}]}
        b=copy.deepcopy(a);b["results"][0]["auto_pass"]=True
        self.assertEqual(compare(a,b)["right_minus_left_automatic_pass"],.5)
        b["hashes"]["data"]="changed"
        with self.assertRaises(ValueError):compare(a,b)
    def test_http_adapter_serialization_and_usage(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return json.dumps({"choices":[{"message":{"content":"{}"}}],"usage":{"prompt_tokens":100,"completion_tokens":20}}).encode()
        class Opener:
            def open(self,req,timeout):
                self.request=req
                return Response()
        c=ChatClient("https://example.invalid/v1","test",api_key="DUMMY_TEST_SECRET",input_price=1,output_price=4)
        c.opener=Opener();c.chat([{"role":"user","content":"hi"}])
        self.assertNotIn("DUMMY_TEST_SECRET",c.opener.request.data.decode())
        self.assertEqual(len(json.loads(c.opener.request.data)["tools"]),9)
        self.assertAlmostEqual(c.cost(),.00018)
    def test_provider_global_cap(self):
        c=ChatClient("http://localhost:8000/v1","test",max_calls=0)
        with self.assertRaises(ProviderError):c.chat([])

if __name__=="__main__":unittest.main()
