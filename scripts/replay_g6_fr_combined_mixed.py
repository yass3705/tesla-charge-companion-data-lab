#!/usr/bin/env python3
"""G6.3e bis: narrowly prove redundant duration-only rules before replay."""
import copy,collections,csv,gzip,json,os,pathlib,subprocess,sys
from decimal import Decimal
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import git_blob,j,dec
from scripts.replay_g6_fr_combined_windows import DIMS,compile_combined,rules_for,fixtures,segments,oracle,envelope

VERSION="g6-fr-electroverse-2026-11-25-combined-mixed-v1"
TARGET="5831d10403740c9e5e715fa151991d63588f28cd7e71fe0678e43c82e5936464"
def simplify(raw):
    """Only remove a duration-only rule if it is below a complementary,
    full-day pair of combined windows and its rates repeat the effective
    baseline, with all omitted baseline components explicitly zero."""
    d=inspect_tariff(raw)
    base={k:dec(d["base_rates"][k]) for k in DIMS}
    rules=d["normalized_rules"]
    plain=[r for r in rules if not r["types"] and not r["conditions"]]
    independent=[r for r in rules if r["types"]==["DURATION_BASED"]]
    combined=[r for r in rules if set(r["types"])=={"DURATION_BASED","TIME_BASED"}]
    if len(plain)!=1 or len(independent)!=1 or len(combined)!=2 or len(rules)!=4:raise ValueError("Unexpected mixed structure")
    p,ind=plain[0],independent[0]
    hist={**base,**{k:dec(v) for k,v in p["rates"].items()}}
    if set(ind["conditions"])!={"durationRestrictions"} or not ind["rates"] or set(ind["rates"])-set(DIMS):raise ValueError("Unknown independent rule")
    b=ind["conditions"]["durationRestrictions"]
    if set(b)!={"minDurationSeconds","maxDurationSeconds"} or b["minDurationSeconds"] not in (None,0) or type(b["maxDurationSeconds"]) is not int or b["maxDurationSeconds"]<=0:raise ValueError("Not an initial band")
    threshold=b["maxDurationSeconds"]
    for k,v in hist.items():
        if k in ind["rates"]:
            if dec(ind["rates"][k])!=v or base[k]!=v:raise ValueError("Non-redundant duration rule")
        elif v!=0 or base[k]!=0:raise ValueError("Omitted positive component")
    for r in combined:
        if r["conditions"]["durationRestrictions"]!={"minDurationSeconds":threshold,"maxDurationSeconds":None}:raise ValueError("Non-complementary duration bounds")
    cleaned=copy.deepcopy(raw)
    del cleaned["complexPricingDetail"]["restrictions"][ind["index"]]
    a,p,w=compile_combined(cleaned)
    from scripts.replay_g6_fr_time_windows import contains
    if len(w)!=2 or any(sum(contains(window,m) for window in w)!=1 for m in range(1440)):raise ValueError("Non-complementary windows")
    return a,p,w,dict(removedIndex=ind["index"],thresholdSeconds=threshold,identicalBaselineRates={k:str(v) for k,v in hist.items()},originalSignature=signature(raw),derivedSignature=signature(cleaned))

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["targetSignature"]!=TARGET:raise ValueError("Target")
    if pin["purpose"]!="offline_g6_fr_combined_mixed" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    a=download(root/"prior",pin["prior"],{"decisions":("g6-combined-window-offer-decisions.csv.gz",),"cases":("g6-combined-window-cases.csv.gz",),"report":("g6-combined-window-report.json",)})
    verify(a["decisions"],pin["decisionsSha256"]);verify(a["cases"],pin["casesSha256"])
    ar=json.loads(a["report"].read_text())
    if ar["codeSha"]!=pin["prior"]["codeSha"] or ar["sourcePin"]!=pin["priorSourcePin"] or ar["identityPairs"]!=24115 or ar["caseCount"]!=1638 or ar["passedCases"]!=1638 or ar["cumulativeEstimatedOffers"]!=14517 or ar["candidateSha256"]!=pin["candidateSha256"] or ar["offerDecisions"]!={"COMBINED_SCENARIO_DEPENDENT_REVIEW":4511,"COMBINED_STRUCTURE_REVIEW":70,"NOT_IN_COMBINED_PHASE":19534}:raise ValueError("Prior lineage")
    with gzip.open(a["decisions"],"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115:raise ValueError("Identity")
    groups=collections.defaultdict(list)
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262:raise ValueError("Inventory")
    requests=[];decisions={}
    for sig,rr in sorted(groups.items()):
        if len({r["raw_price_payload"] for r in rr})!=1 or len({r["family"] for r in rr})!=1:raise ValueError("Signature ambiguity")
        raw=json.loads(rr[0]["raw_price_payload"])
        if signature(raw)!=sig or any(r["raw_verified"].lower()!="true" for r in rr):raise ValueError("Raw lineage")
        if sig!=TARGET:continue
        if rr[0]["family"]!="DURATION_BASED+TIME_BASED" or any(r["g6_combined_replay"]!="COMBINED_STRUCTURE_REVIEW" or r["g6_combined_reason"]!="Unsupported rule shape" for r in rr):raise ValueError("Unexpected prior status")
        if any(r["g6_calculability"]!="NOT_YET_CERTIFIED" for r in rr):raise ValueError("Prior estimate")
        d=inspect_tariff(raw)
        if any(json.loads(r["normalized_rules"])!=d["normalized_rules"] or json.loads(r["base_rates"])!=d["base_rates"] for r in rr):raise ValueError("Audit lineage")
        decisions[sig]=dict(offers=len(rr),status="COMBINED_STRUCTURE_REVIEW",reason="",excludedThresholdSeconds=[])
        base,plain,w,proof=simplify(raw)
        decisions[sig]["redundancyProof"]=proof
        rules=rules_for(base,plain,w)
        for f,excluded in fixtures(w):
            decisions[sig]["excludedThresholdSeconds"]=excluded
            ss=segments(w,f);expected=oracle(base,plain,w,f,ss);lo,hi=envelope(base,plain,w,f,ss)
            requests.append(dict(signature=sig,fixture=f,rules=rules,expected=expected,lower={k:str(v) for k,v in lo.items()},upper={k:str(v) for k,v in hi.items()}))
    if len(decisions)!=1 or sum(d["offers"] for d in decisions.values())!=70 or not requests:raise ValueError("Cohort")
    engine=pathlib.Path("migration/v9/g6-candidate/pricing-engine.cjs")
    verify(engine,pin["candidateSha256"]);verify(pathlib.Path("migration/v9/g6-reference/pricing-engine.cjs"),pin["engineSha256"])
    if git_blob(engine)!=pin["candidateGitBlob"] or git_blob(pathlib.Path("scripts/build_electroverse_france_evse_overlay.mjs"))!=pin["compilerBlob"]:raise ValueError("Reference")
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_combined_windows_engine.cjs")
    result=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(result["results"])!=len(requests) or not all(result["guards"].values()) or len(result["guards"])!=4:raise ValueError("Guard")
    cases=[];by=collections.defaultdict(collections.Counter)
    for x,r in zip(requests,result["results"]):
        sig=x["signature"]
        if r["signature"]!=sig or r["scenario"]!=x["fixture"]["id"]:raise ValueError("Order")
        try:good=r["complete"] is True and r["currency"]=="EUR" and all(dec(r[k])==dec(x["expected"][k]) for k in ("total",*DIMS))
        except (ValueError,ArithmeticError):good=False
        agree=x["lower"]==x["upper"] and all(dec(x["lower"][k])==dec(x["expected"][k]) for k in DIMS)
        state="COMBINED_ENGINE_MISMATCH" if not good else "CONDITIONAL_ESTIMATE_AGREEMENT" if agree else "INCALCULABLE_SEMANTICS"
        by[sig][state]+=1
        cases.append(dict(signature=sig,scenario=r["scenario"],session=j(x["fixture"]),oracle=j(x["expected"]),lower_model=j(x["lower"]),upper_model=j(x["upper"]),engine_result=j(r),engine_pass=good,decision=state))
    for sig,d in decisions.items():
        if sig in by:
            d["scenarioDecisions"]=dict(by[sig])
            d["status"]="COMBINED_ENGINE_REVIEW" if by[sig]["COMBINED_ENGINE_MISMATCH"] else "COMBINED_SCENARIO_DEPENDENT_REVIEW"
            if d["excludedThresholdSeconds"]:d["reason"]="THRESHOLDS_OUTSIDE_7_DAY_GUARD"
    out=[]
    for r in rows:
        d=decisions.get(r["tariff_signature"],{})
        out.append({**r,"g6_combined_mixed_replay":d.get("status","NOT_IN_COMBINED_MIXED_PHASE"),"g6_combined_mixed_reason":d.get("reason",""),"g6_combined_mixed_scenarios":j(d.get("scenarioDecisions",{})) if d else ""})
    if sum(r["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for r in out)!=14517:raise ValueError("Prior estimates")
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-combined-mixed-cases.csv.gz",cases,list(cases[0]))
    write_csv(dest/"g6-combined-mixed-offer-decisions.csv.gz",out,list(out[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),combinedOffers=70,combinedSignatures=1,caseCount=len(cases),passedCases=sum(x["engine_pass"] for x in cases),signatureDecisions=decisions,scenarioDecisions=dict(collections.Counter(x["decision"] for x in cases)),offerDecisions=dict(collections.Counter(r["g6_combined_mixed_replay"] for r in out)),guards=result["guards"],cumulativeEstimatedOffers=14517,engineSha256=pin["engineSha256"],candidateSha256=digest(engine),identityChanges=0,pricesPromoted=0,supplierCalls=0,automaticPublication=False,limitations=["Historical whole-session duration selection and elapsed UTC window segmentation, prorated estimates only","Diagnostic conservative rate envelope is not a contractual or invoice bound; no automatic certification","Only redundant independent initial duration rule removed from temporary compilation; raw payload and original decisions preserved, no Production integration"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-combined-mixed-report.json").write_text(j(report))
    print("G6_FR_COMBINED_MIXED "+j({k:v for k,v in report.items() if k not in ("sourcePin","signatureDecisions")}))
if __name__=="__main__":main()
