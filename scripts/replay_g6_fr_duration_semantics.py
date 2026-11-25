#!/usr/bin/env python3
"""G6.3c bis: conservative scenario-specific agreement, no new tariff certification."""
import collections,csv,gzip,json,os,pathlib,subprocess,sys
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import git_blob,j,dec,Q
from scripts.replay_g6_fr_duration import compile_duration,DIMS

VERSION="g6-fr-electroverse-2026-11-25-duration-semantics-v1"
def envelope(raw,f):
    """Over-approximate rates for all elapsed clocks between zero and total.
    Include base/plain alternatives, never assume a missing surcharge is zero.
    Prorated model only, not proof of invoiced amounts."""
    d=inspect_tariff(raw)
    rates={k:{dec(d["base_rates"][k])} for k in DIMS}
    for r in d["normalized_rules"]:
        if r["types"]:
            b=r["conditions"]["durationRestrictions"]
            if (b["minDurationSeconds"] or 0)>f["seconds"]:continue
        for k,v in r["rates"].items():rates[k].add(dec(v))
    qty={"energy":dec(f["energy"]),"time":dec(f["chargeSeconds"])/60,"parking":dec(f["parkSeconds"])/60,"flat":Decimal(1)}
    low={k:(min(v)*qty[k]).quantize(Q,rounding=ROUND_HALF_UP) for k,v in rates.items()}
    high={k:(max(v)*qty[k]).quantize(Q,rounding=ROUND_HALF_UP) for k,v in rates.items()}
    return low,high

def delayed_oracle(component,threshold,rate,f):
    c,p=f["chargeSeconds"],f["parkSeconds"]
    start,end={"TIME":(0,c),"PARKING_TIME":(c,c+p),"CONNECTED_TIME":(0,c+p)}[component]
    return (dec(max(0,end-max(start,threshold)))*dec(rate)/60).quantize(Q,rounding=ROUND_HALF_UP)

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_duration_semantics" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    for p,sha in pin["evidence"].items():
        if git_blob(pathlib.Path(p))!=sha:raise ValueError("Historical evidence changed")
    a=download(root/"prior",pin["prior"],{"decisions.csv.gz":("g6-duration-offer-decisions.csv.gz",),"cases.csv.gz":("g6-duration-engine-cases.csv.gz",),"report.json":("g6-duration-replay-report.json",)})
    verify(a["decisions.csv.gz"],pin["decisionsSha256"]);verify(a["cases.csv.gz"],pin["casesSha256"])
    ar=json.loads(a["report.json"].read_text())
    if ar["sourcePin"]!=pin["priorSourcePin"] or ar["codeSha"]!=pin["prior"]["codeSha"] or ar["engineSha256"]!=pin["engineSha256"] or ar["identityPairs"]!=24115 or ar["passedCases"]!=822 or ar["cumulativeEstimatedOffers"]!=14517:raise ValueError("Prior lineage")
    with gzip.open(a["decisions.csv.gz"],"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    with gzip.open(a["cases.csv.gz"],"rt",encoding="utf-8",newline="") as f:prior=list(csv.DictReader(f))
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115 or len(prior)!=822 or any(r["engine_pass"].lower()!="true" for r in prior):raise ValueError("Prior coverage")
    groups=collections.defaultdict(list)
    for r in rows:
        if r["g6_duration_replay"]=="DURATION_HISTORICAL_REPLAY_PASS_SEMANTICS_REVIEW":groups[r["tariff_signature"]].append(r)
    if len(groups)!=38 or sum(map(len,groups.values()))!=2054:raise ValueError("Cohort")
    raw={}
    for sig,rr in groups.items():
        if len({r["raw_price_payload"] for r in rr})!=1 or any(r["raw_verified"].lower()!="true" or r["g6_calculability"]!="NOT_YET_CERTIFIED" for r in rr):raise ValueError("Raw scope")
        raw[sig]=json.loads(rr[0]["raw_price_payload"])
        if signature(raw[sig])!=sig:raise ValueError("Raw signature")
        compile_duration(raw[sig])
    cases=[];requests=[];by=collections.defaultdict(collections.Counter)
    for x in prior:
        sig=x["signature"]
        if sig not in groups:continue
        f=json.loads(x["session"]);lo,hi=envelope(raw[sig],f);original=json.loads(x["engine_result"])
        certain=lo==hi
        if certain and (dec(original["total"])!=sum(lo.values()) or any(dec(original[k])!=v for k,v in lo.items())):raise ValueError("Historical engine contradicts envelope")
        state="CONDITIONAL_ESTIMATE_AGREEMENT" if certain else "INCALCULABLE_SEMANTICS"
        by[sig][state]+=1
        cases.append(dict(signature=sig,scenario=x["scenario"],session=x["session"],decision=state,estimate_eur=str(sum(lo.values())) if certain else "",lower_model_eur=str(sum(lo.values())),upper_model_eur=str(sum(hi.values())),historical_engine=x["engine_result"]))
        # Reuse Production delayed mechanism as alternative hypothesis only.
        rates,bands,conflict,variable=compile_duration(raw[sig])
        for k,b,hi_bound,v in bands:
            if k not in ("time","parking") or b<=0 or hi_bound is not None or v<=0 or rates[k]!=0:continue
            component=DIMS[k]
            requests.append(dict(signature=sig,scenario=x["scenario"],component=component,threshold=b,rate=str(v),fixture=f,expected=str(delayed_oracle(component,b,v,f))))
    spec=pin["priorSourcePin"]["priorSourcePin"]["priorSourcePin"]["priorSourcePin"]["engine"]
    engine=pathlib.Path(spec["auditPath"])
    if git_blob(engine)!=spec["gitBlob"]:raise ValueError("Engine blob")
    verify(engine,pin["engineSha256"])
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_duration_semantics_engine.cjs")
    results=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(results["results"])!=len(requests) or not results["missingComponentGuard"]:raise ValueError("Delayed mechanism guard")
    delayed=[]
    for q,r in zip(requests,results["results"]):
        good=r["complete"] and r["total"] is not None and dec(r["total"])==dec(q["expected"])
        delayed.append(dict(signature=q["signature"],scenario=q["scenario"],component=q["component"],threshold_seconds=q["threshold"],rate=q["rate"],expected=q["expected"],engine_result=j(r),engine_pass=good))
    if not delayed or set(by)!=set(groups):raise ValueError("Missing replay")
    out=[]
    for r in rows:
        sig=r["tariff_signature"];counts=by.get(sig)
        out.append({**r,"g6_duration_semantics":"SCENARIO_DEPENDENT_REVIEW" if counts else "NOT_IN_SEMANTICS_PHASE","g6_duration_agreement_scenarios":counts["CONDITIONAL_ESTIMATE_AGREEMENT"] if counts else "", "g6_duration_ambiguous_scenarios":counts["INCALCULABLE_SEMANTICS"] if counts else ""})
    if sum(r["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for r in out)!=14517:raise ValueError("Prior estimates altered")
    dest=root/"results";dest.mkdir()
    for name,items in [("g6-duration-semantics-cases.csv.gz",cases),("g6-duration-delayed-alternatives.csv.gz",delayed),("g6-duration-semantics-offer-decisions.csv.gz",out)]:write_csv(dest/name,items,list(items[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),reviewOffers=2054,reviewSignatures=38,scenarioDecisions=dict(collections.Counter(x["decision"] for x in cases)),bySignature={sig:dict(c) for sig,c in by.items()},delayedCases=len(delayed),delayedPassed=sum(x["engine_pass"] for x in delayed),missingComponentGuard=results["missingComponentGuard"],cumulativeEstimatedOffers=14517,engineSha256=digest(engine),supplierCalls=0,identityChanges=0,pricesPromoted=0,automaticPublication=False,limitations=["Archived evidence proves delayed fee mechanism for distinct CPO/contract offers, not Electroverse billing semantics; no cross-channel transfer","Agreement limited to conservative prorated rate envelope and specified scenarios; bounds are diagnostic, not invoice bounds or amounts for ranking","No new unconditional offer certification; per-session rule remains to be integrated and verified in Production"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-duration-semantics-report.json").write_text(j(report))
    print("G6_FR_DURATION_SEMANTICS "+j({k:v for k,v in report.items() if k not in ("sourcePin","bySignature")}))
if __name__=="__main__":main()
