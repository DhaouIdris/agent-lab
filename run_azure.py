"""Lightweight launcher: tools run on CPU locally, LLM runs remotely on Azure."""
import argparse
import getpass
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

from ci_agentlab.preflight import check_endpoint
from ci_agentlab.providers import ChatClient, ProviderError

load_dotenv()
ROOT=Path(__file__).parent

def load_config(path):
    c=json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(c,dict):raise ValueError("Configuration must be a JSON object")
    allowed=set(json.loads((ROOT/"azure.example.json").read_text(encoding="utf-8")))
    if set(c)-allowed:raise ValueError("Unknown config fields; credentials must not be stored here")
    if allowed-set(c):raise ValueError("Missing fields: start from azure.example.json")
    if c["auth_header"] not in ("api-key","bearer"):raise ValueError("Invalid auth_header")
    if c["token_parameter"] not in ("max_tokens","max_completion_tokens"):raise ValueError("Invalid token_parameter")
    for k in ("base_url","deployment"):
        if not isinstance(c.get(k),str) or not c[k].strip():raise ValueError("Missing "+k)
    u=urlsplit(c["base_url"])
    if u.scheme!="https" or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ValueError("Azure requires a plain HTTPS base URL, no credentials/query/fragment")
    if "YOUR-RESOURCE" in c["base_url"]:raise ValueError("Replace the example base_url with the deployment inference URL")
    if not u.path.rstrip("/").endswith("/openai/v1"):
        raise ValueError("This starter targets the /openai/v1 base URL, not the Foundry project URL or /chat/completions")
    if c.get("deployment_type") not in ("GlobalStandard","DataZoneStandard","Standard"):
        raise ValueError("Starter expects a pay-per-token Standard deployment; no provisioned or dedicated GPU profile")
    if type(c.get("max_output_tokens")) is not int or not 100<=c["max_output_tokens"]<=4096:raise ValueError("Output cap must be 100..4096")
    if not isinstance(c.get("min_interval_seconds"),(int,float)) or not 0<=c["min_interval_seconds"]<=60:raise ValueError("Request spacing must be 0..60 seconds")
    if type(c.get("turn_timeout_seconds")) is not int or not 30<=c["turn_timeout_seconds"]<=600:raise ValueError("Turn timeout must be 30..600 seconds")
    a,b=c.get("input_price_per_million"),c.get("output_price_per_million")
    if (a is None)!=(b is None):raise ValueError("Provide both token prices or neither")
    if a is not None and any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in (a,b)):raise ValueError("Invalid prices")
    return c

def fingerprint(c):return hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()

def public_config(c):return {k:v for k,v in c.items() if k!="base_url"}

def build_command(c,stage,out):
    cmd=[sys.executable,"-m","ci_agentlab","run","--base-url",c["base_url"],"--model",c["deployment"],
         "--auth-header",c["auth_header"],"--token-parameter",c["token_parameter"],
         "--max-output-tokens",str(c["max_output_tokens"]),"--min-interval-seconds",str(c["min_interval_seconds"]),
         "--turn-timeout-seconds",str(c["turn_timeout_seconds"]),"--stop-on-provider-error","--out",str(out)]
    caps={"smoke":24,"pilot":400,"benchmark":1200}
    cmd += ["--max-provider-calls",str(caps[stage]),"--repeat","3" if stage=="benchmark" else "1"]
    
    if stage=="smoke":cmd += ["--case","S01","--case","U01"]
    
    if c.get("api_version"):cmd += ["--api-version",c["api_version"]]
    
    if c.get("input_price_per_million") is not None:
        cmd += ["--input-price",str(c["input_price_per_million"]),"--output-price",str(c["output_price_per_million"])]
    return cmd

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=["check","preflight","smoke","pilot","benchmark"])
    p.add_argument("--config",default="azure.json")
    p.add_argument("--dry-run",action="store_true",help="No network request or key requested")
    p.add_argument("--out",help="Fresh run directory; defaults to timestamped path")
    p.add_argument("--case",action="append",help="Select development scenario(s), pilot stage only")
    args=p.parse_args()
    if args.case and args.stage!="pilot":p.error("--case is supported with pilot only")
    
    try:c=load_config(args.config)
    except (OSError,ValueError,TypeError) as e:p.exit(2,"Configuration: "+str(e)+"\n")
    
    if args.stage=="check":
        print("Configuration locale valide. Quota, crédit et disponibilité du déploiement non vérifiés.")
        print("Inférence Azure ; outils et benchmark locaux ; aucun poids téléchargé.")
        return
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out=Path(args.out).resolve() if args.out else ROOT/"runs"/f"azure_{args.stage}_{stamp}"
    if args.stage not in ("check","preflight") and not args.dry_run and out.exists():
        p.exit(2,"Choisis un dossier de résultats neuf avec --out.\n")
    marker=ROOT/"runs/azure_preflight.json"
    
    if args.dry_run:
        command=build_command(c,args.stage,out) if args.stage!="preflight" else "Two-call protocol check"
        if args.case:
            for case in args.case:command += ["--case",case]
        if isinstance(command,list):
            for flag in ("--base-url","--out"):
                if flag in command:command[command.index(flag)+1]="[REDACTED]"
        print(json.dumps({"stage":args.stage,"network_calls":0,"preflight_max_requests":2,
            "command":command,
            "cost":"Unknown until deployment tariffs and usage are known"},ensure_ascii=False,indent=2));return
    
    if args.stage!="preflight":
        try:prior=json.loads(marker.read_text(encoding="utf-8"))
        except (OSError,ValueError):p.exit(2,"Exécute d'abord : python run_azure.py preflight\n")
        if not prior.get("passed") or prior.get("config_fingerprint")!=fingerprint(c):
            p.exit(2,"Configuration modifiée ou preflight invalide : relance le preflight.\n")
    key=os.getenv("AGENTLAB_API_KEY") or getpass.getpass("Clé Azure (saisie masquée, non enregistrée) : ")
    
    if not key:
        p.exit(2,"Clé absente. Aucun appel effectué.\n")
    
    if args.stage=="preflight":
        client=ChatClient(c["base_url"],c["deployment"],api_key=key,api_version=c.get("api_version"),
            max_output_tokens=c["max_output_tokens"],input_price=c.get("input_price_per_million"),output_price=c.get("output_price_per_million"),
            max_calls=2,auth_header=c["auth_header"],token_parameter=c["token_parameter"],min_interval_seconds=c["min_interval_seconds"])
        try:report=check_endpoint(client)
        except (ProviderError,ValueError) as exc:report={"passed":False,"error":str(exc),"provider_calls":client.calls}
        report.update(config_fingerprint=fingerprint(c),checked_at=datetime.now(timezone.utc).isoformat())
        marker.parent.mkdir(parents=True,exist_ok=True);marker.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2));sys.exit(0 if report["passed"] else 1)
    env=os.environ.copy();env["AGENTLAB_API_KEY"]=key
    command=build_command(c,args.stage,out)
    if args.case:
        for case in args.case:command += ["--case",case]
    proc=subprocess.run(command,cwd=ROOT,env=env)

    if proc.returncode:sys.exit(proc.returncode)
    (out/"azure_run_metadata.json").write_text(json.dumps({"config":public_config(c),"currency":c["currency"],"quota_verified":False},indent=2),encoding="utf-8")
    report=json.loads((out/"report.json").read_text(encoding="utf-8"))

    if not report.get("campaign_complete",False):
        sys.exit(1)

if __name__=="__main__":main()


