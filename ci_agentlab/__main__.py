import argparse
import hashlib
import json
import os
import platform
import random
import sys
from datetime import datetime,timezone
from pathlib import Path
from . import __version__
from .contracts import TOOL_MODELS,FinalAnswer,ToolResponse,tool_specs
from .tools import ROOT
from .evaluation import run_case,aggregate
from .providers import ChatClient

def dump(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in ("data","ci_agentlab") for p in sorted((ROOT/directory).glob("*")) if p.suffix in (".json",".py")}

def main():
    p=argparse.ArgumentParser(description="AgentLab: tool, guardrail and agent evaluation sandbox")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("schemas",help="Export nine input contracts, final response schema and model tool definitions")
    sub.add_parser("validate",help="Validate fixture, scenario metadata and oracle replay consistency; no LLM")
    for name in ("replay","run"):
        c=sub.add_parser(name,help="No LLM: oracle replay" if name=="replay" else "OPT-IN: call the specified model endpoint")
        c.add_argument("--out",default="runs/"+name)
        c.add_argument("--repeat",type=int,default=1)
        c.add_argument("--seed",type=int,default=42)
        c.add_argument("--case",action="append",help="Case ID, repeat to select several")
        if name=="run":
            c.add_argument("--base-url",required=True,help="OpenAI-compatible base, e.g. http://localhost:8000/v1")
            c.add_argument("--model",required=True)
            c.add_argument("--api-version")
            c.add_argument("--api-key-env",default="AGENTLAB_API_KEY")
            c.add_argument("--auth-header",choices=["bearer","api-key"],default="bearer")
            c.add_argument("--token-parameter",choices=["max_tokens","max_completion_tokens"],default="max_tokens")
            c.add_argument("--min-interval-seconds",type=float,default=0)
            c.add_argument("--turn-timeout-seconds",type=int,default=60)
            c.add_argument("--stop-on-provider-error",action="store_true",help="Stop campaign after a transport/auth/quota/protocol error")
            c.add_argument("--max-output-tokens",type=int,default=2000)
            c.add_argument("--max-provider-calls",type=int,default=240)
            c.add_argument("--input-price",type=float,help="Currency units per million input tokens")
            c.add_argument("--output-price",type=float,help="Currency units per million output tokens")
            c.add_argument("--reasoning-effort",choices=["low","medium","high"])
    c=sub.add_parser("compare",help="Paired comparison of two model reports with matching corpus hashes")
    c.add_argument("left");c.add_argument("right");c.add_argument("--out",default="runs/comparison.json")
    args=p.parse_args()
    if args.command=="schemas":
        for name,model in TOOL_MODELS.items():dump(ROOT/"schemas"/(name+".json"),model.model_json_schema())
        dump(ROOT/"schemas/final_answer.json",FinalAnswer.model_json_schema())
        dump(ROOT/"schemas/tool_response.json",ToolResponse.model_json_schema())
        dump(ROOT/"schemas/tools.openai.json",tool_specs())
        print("Exported 9 tool input contracts + final response + tool catalog.");return
    cases=json.loads((ROOT/"data/scenarios.json").read_text(encoding="utf-8"))
    if args.command=="validate":
        from .validation import validate_corpus
        errors=validate_corpus(cases)
        if errors:
            print(json.dumps(errors,ensure_ascii=False,indent=2));sys.exit(1)
        print("40 development cases: metadata, oracle rules and reference replays validated. No model evaluated.");return
    if args.command=="compare":
        from .comparison import compare
        report=compare(json.loads(Path(args.left).read_text(encoding="utf-8")),json.loads(Path(args.right).read_text(encoding="utf-8")))
        dump(Path(args.out),report);print(json.dumps(report,indent=2));return
    if not 1<=args.repeat<=20:p.error("repeat must be 1..20")
    if args.case:
        unknown=set(args.case)-{c["id"] for c in cases}
        if unknown:p.error("Unknown cases: "+str(sorted(unknown)))
        cases=[c for c in cases if c["id"] in args.case]
    replay=json.loads((ROOT/"data/oracle_replays.json").read_text(encoding="utf-8")) if args.command=="replay" else None
    client=None
    if args.command=="run":
        if not 1<=args.max_provider_calls<=10000:p.error("max-provider-calls must be 1..10000")
        if not 100<=args.max_output_tokens<=8192:p.error("max-output-tokens must be 100..8192")
        if (args.input_price is None)!=(args.output_price is None):p.error("Supply both prices or neither")
        if args.input_price is not None and min(args.input_price,args.output_price)<0:p.error("Prices must be nonnegative")
        client=ChatClient(args.base_url,args.model,os.getenv(args.api_key_env),args.api_version,
                          args.max_output_tokens,args.input_price,args.output_price,args.reasoning_effort,
                          max_calls=args.max_provider_calls,auth_header=args.auth_header,
                          token_parameter=args.token_parameter,min_interval_seconds=args.min_interval_seconds)
    tasks=[(c,rep) for c in cases for rep in range(args.repeat)]
    random.Random(args.seed).shuffle(tasks)
    results=[]
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    config={k:v for k,v in vars(args).items() if k not in ("api_key_env",)}
    report={"kind":"oracle_replay_NOT_MODEL_PERFORMANCE" if replay else "model_automatic_evaluation_PENDING_HUMAN_REVIEW",
        "created_at":datetime.now(timezone.utc).isoformat(),"version":__version__,"python":platform.python_version(),
        "config":config,"hashes":hashes(),"run_seed":args.seed,"results":results}
    for c,rep in tasks:
        r=run_case(c,replay=replay[c["id"]] if replay else None,client=client,
                   turn_timeout_seconds=getattr(args,"turn_timeout_seconds",60),
                   stop_on_provider_error=getattr(args,"stop_on_provider_error",False))
        r["repetition"]=rep;results.append(r)
        print(f'{c["id"]} repeat={rep+1}: {"PASS" if r["auto_pass"] else "FAIL"} automatic checks',flush=True)
        report["summary"]=aggregate(results,args.seed)
        report["campaign_complete"]=not any("Global provider-call cap reached" in f.get("detail","") for x in results for f in x["failures"])
        dump(out/"report.json",report)
        if client and args.stop_on_provider_error and any(x.get("error") and not x.get("recovered_or_retried") for x in r["provider_calls"]):
            report["campaign_complete"]=False
            report["stop_reason"]="Provider error: inspect authentication, quota, endpoint and model compatibility before retrying."
            dump(out/"report.json",report)
            print(report["stop_reason"])
            break
    blind=[]
    for i,r in enumerate(results):
        c=next(c for c in cases if c["id"]==r["case_id"])
        blind.append({"review_id":f"R{i+1:04}","conversation":[t["user"] for t in c["turns"]],
                      "outputs":r["outputs"],"trace":r["trace"],"rubric":c["human_rubric"],
                      "human_pass":None,"comments":""})
    dump(out/"human_review.json",blind)
    dump(out/"review_mapping.json",[{"review_id":f"R{i+1:04}","case_id":r["case_id"],"repetition":r["repetition"]} for i,r in enumerate(results)])
    print(json.dumps(report["summary"],indent=2))
    if replay:print("These are reference replays, NOT AI performance results.")

if __name__=="__main__":main()

