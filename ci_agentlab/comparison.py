import random
import statistics
from collections import defaultdict

def compare(left,right,seed=42):
    if not left.get("campaign_complete",True) or not right.get("campaign_complete",True):
        raise ValueError("Incomplete campaign: global call cap reached; rerun with a sufficient fixed budget")
    if not left["kind"].startswith("model_") or not right["kind"].startswith("model_"):
        raise ValueError("Reference replays cannot be used as model comparison")
    if left["hashes"]!=right["hashes"]:
        raise ValueError("Different corpus or implementation hashes; re-run controlled experiments")
    def by_case(report):
        d=defaultdict(dict)
        for r in report["results"]:
            if r["repetition"] in d[r["case_id"]]:raise ValueError("Duplicate case repetition")
            d[r["case_id"]][r["repetition"]]=r["auto_pass"]
        return d
    a,b=by_case(left),by_case(right)
    if set(a)!=set(b) or any(set(a[k])!=set(b[k]) for k in a):raise ValueError("Cases/repetitions must match")
    differences=[statistics.mean(b[k].values())-statistics.mean(a[k].values()) for k in sorted(a)]
    if not differences:raise ValueError("Empty comparison")
    rng=random.Random(seed)
    samples=sorted(statistics.mean(rng.choices(differences,k=len(differences))) for _ in range(5000))
    return {"right_minus_left_automatic_pass":statistics.mean(differences),"paired_scenario_bootstrap_95":[samples[124],samples[4874]],
            "distinct_scenarios":len(differences),"human_success_comparison":None,
            "interpretation":"Exploratory paired result on development scenarios; not a production superiority claim. Check safety separately and adjudicate human reviews."}
