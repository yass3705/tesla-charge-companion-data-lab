#!/usr/bin/env python3
"""G6.3c: historical whole-session duration bands, separate unresolved billing semantics."""
import collections,csv,gzip,json,os,pathlib,subprocess,sys
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import git_blob,j,dec,Q

VERSION="g6-fr-electroverse-2026-11-25-duration-v1"
DIMS={"energy":"ENERGY","time":"TIME","parking":"PARKING_TIME","flat":"FLAT"}
REASONS={"CONDITIONAL_RULE_ENGINE_AND_ORACLE_REQUIRED","DURATION_BILLING_CLOCK_AND_BOUNDARY_REVIEW","BASE_UNRESTRICTED_RULE_DISAGREEMENT","CHARGING_PARKING_CLOCK_AND_ROUNDING_REVIEW"}
def compile_duration(raw):
    d=inspect_tariff(raw)
    if raw.get("isChargingFree") is not False or d["restriction_types"]!=["DURATION_BASED"] or d["condition_fields"]!=["durationRestrictions"] or set(d["reasons"])-REASONS:
        raise ValueError("Unrecognized duration scope")
    rates={k:dec(d["base_rates"][k]) for k in DIMS}
    if dec(d["base_rates"]["vat"])!=0:raise ValueError("VAT")
    plain={}; bands=[]
    for row in d["normalized_rules"]:
        if set(row["rates"])-set(DIMS):raise ValueError("Unknown component")
        if not row["types"] and not row["conditions"]:
            for k,v in row["rates"].items():
                v=dec(v)
                if k in plain and plain[k]!=v:raise ValueError("Conflicting plain rates")
                plain[k]=v
        elif row["types"]==["DURATION_BASED"] and set(row["conditions"])=={"durationRestrictions"}:
            b=row["conditions"]["durationRestrictions"]
            if set(b)!={"minDurationSeconds","maxDurationSeconds"}:raise ValueError("Unknown bounds")
            lo=b["minDurationSeconds"];hi=b["maxDurationSeconds"]
            if lo is not None and (type(lo) is not int or lo<0):raise ValueError("Invalid min")
            if hi is not None and (type(hi) is not int or hi<=0):raise ValueError("Invalid max")
            lo=lo or 0
            if hi is not None and hi<=lo:raise ValueError("Empty duration band")
            for k,v in row["rates"].items():bands.append((k,lo,hi,dec(v)))
        else:raise ValueError("Unexpected restriction")
    conflict=any(rates[k]!=v for k,v in plain.items())
    rates.update(plain)
    if not bands:raise ValueError("Missing bands")
    for k in DIMS:
        a=sorted((b for b in bands if b[0]==k),key=lambda b:b[1])
        for x,y in zip(a,a[1:]):
            if x[2] is None or x[2]>y[1]:raise ValueError("Overlapping bands")
    # Varying rates mean clock/whole-session vs marginal billing cannot be
    # proven from the archived payload alone. Historical estimate replay
    # remains separate from a commercial decision.
    variable=any(v!=rates[k] for k,lo,hi,v in bands)
    return rates,bands,conflict,variable

def oracle(rates,bands,seconds,charge,park,energy):
    applicable=dict(rates)
    for k,lo,hi,v in bands:
        if seconds>=lo and (hi is None or seconds<hi):applicable[k]=v
    qty={"energy":dec(energy),"time":dec(charge)/60,"parking":dec(park)/60,"flat":Decimal(1)}
    parts={k:(applicable[k]*qty[k]).quantize(Q,rounding=ROUND_HALF_UP) for k in DIMS}
    return {**{k:str(v) for k,v in parts.items()},"total":str(sum(parts.values()))}

def scenarios(bands):
    bounds={x for _,lo,hi,_ in bands for x in (lo,hi) if x is not None and x>0}
    durations={1,60,3600,14400}
    for b in bounds:durations.update((max(1,b-1),b,b+1))
    for s in sorted(durations):
        for mode,charge in (("charge",s),("mixed",s//2),("parking",0)):
            yield dict(id=f"{s}s_{mode}",duration=str(dec(s)/60),charging=str(dec(charge)/60),parking=str(dec(s-charge)/60),energy="10.125" if charge else "0",startAt="2026-11-25T10:00:00Z",seconds=s,chargeSeconds=charge,parkSeconds=s-charge)

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_duration_replay" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    a=download(root/"prior",pin["prior"],{"decisions.csv.gz":("g6-free-offer-decisions.csv.gz",),"cases.csv.gz":("g6-free-engine-cases.csv.gz",),"report.json":("g6-free-replay-report.json",)})
    verify(a["decisions.csv.gz"],pin["decisionsSha256"]);verify(a["cases.csv.gz"],pin["casesSha256"])
    ar=json.loads(a["report.json"].read_text())
    if ar["codeSha"]!=pin["prior"]["codeSha"] or ar["sourcePin"]!=pin["priorSourcePin"] or ar["identityPairs"]!=24115 or ar["passedCases"]!=7 or ar["cumulativeEstimatedOffers"]!=14509 or ar["engineSha256"]!=pin["engineSha256"]:raise ValueError("Prior lineage")
    with gzip.open(a["decisions.csv.gz"],"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115 or sum(r["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for r in rows)!=14509:raise ValueError("Identity/estimate coverage")
    groups=collections.defaultdict(list)
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262:raise ValueError("Signature inventory")
    decisions={};requests=[];candidate_count=0
    for sig,rr in sorted(groups.items()):
        if len({r["raw_price_payload"] for r in rr})!=1 or len({r["family"] for r in rr})!=1:raise ValueError("Signature ambiguity")
        raw=json.loads(rr[0]["raw_price_payload"])
        if signature(raw)!=sig or any(r["raw_verified"].lower()!="true" for r in rr):raise ValueError("Raw lineage")
        if rr[0]["family"]!="DURATION_BASED":continue
        candidate_count+=len(rr)
        if any(r["g6_calculability"]!="NOT_YET_CERTIFIED" for r in rr):raise ValueError("Prior estimate changed")
        d=inspect_tariff(raw)
        if any(json.loads(r["normalized_rules"])!=d["normalized_rules"] or json.loads(r["base_rates"])!=d["base_rates"] or json.loads(r["reasons"])!=d["reasons"] for r in rr):raise ValueError("Historical audit mismatch")
        try:rates,bands,conflict,variable=compile_duration(raw)
        except ValueError as e:
            decisions[sig]={"status":"DURATION_STRUCTURE_REVIEW","reason":str(e),"count":len(rr)}
            continue
        decisions[sig]={"status":"DURATION_REPLAY_PENDING","reason":"BASE_RULE_DISAGREEMENT" if conflict else "BILLING_CLOCK_OR_MARGINAL_SEMANTICS_UNPROVEN" if variable else "RATE_INVARIANT","count":len(rr)}
        encoded={**{k:str(v) for k,v in rates.items()},"bands":[[DIMS[k],lo,hi,str(v)] for k,lo,hi,v in bands]}
        for f in scenarios(bands):
            requests.append(dict(signature=sig,fixture=f,rates=encoded,expected=oracle(rates,bands,f["seconds"],f["chargeSeconds"],f["parkSeconds"],f["energy"])))
    if len(decisions)!=40 or candidate_count!=2062:raise ValueError("Pinned cohort mismatch")
    spec=pin["priorSourcePin"]["priorSourcePin"]["priorSourcePin"]["engine"];engine=pathlib.Path(spec["auditPath"])
    if git_blob(engine)!=spec["gitBlob"] or git_blob(pathlib.Path("scripts/build_electroverse_france_evse_overlay.mjs"))!=pin["compilerBlob"]:raise ValueError("Historical reference blob")
    verify(engine,pin["engineSha256"])
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_duration_engine.cjs")
    evaluated=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(evaluated["results"])!=len(requests) or not all(evaluated["guards"].values()) or len(evaluated["guards"])!=5:raise ValueError("Engine guard")
    cases=[];failed=set()
    for x,r in zip(requests,evaluated["results"]):
        sig=x["signature"]
        if r["signature"]!=sig or r["scenario"]!=x["fixture"]["id"]:raise ValueError("Result order")
        try:good=r["complete"] is True and r["currency"]=="EUR" and all(dec(r[k])==dec(x["expected"][k]) for k in ("total","energy","time","parking","flat"))
        except (ValueError,ArithmeticError):good=False
        if not good:failed.add(sig)
        cases.append(dict(signature=sig,scenario=r["scenario"],session=j(x["fixture"]),oracle=j(x["expected"]),engine_result=j(r),engine_pass=good))
    for sig,d in decisions.items():
        if d["status"]!="DURATION_REPLAY_PENDING":continue
        d["status"]="DURATION_ENGINE_MISMATCH" if sig in failed else "DURATION_ENGINE_ORACLE_PASS_ESTIMATE_ONLY" if d["reason"]=="RATE_INVARIANT" else "DURATION_HISTORICAL_REPLAY_PASS_SEMANTICS_REVIEW"
    out=[]
    for r in rows:
        d=decisions.get(r["tariff_signature"],{})
        status=d.get("status","NOT_IN_DURATION_PHASE")
        out.append({**r,"g6_duration_replay":status,"g6_duration_reason":d.get("reason",""),"g6_calculability":"ENGINE_ORACLE_PASS_ESTIMATE_ONLY" if status=="DURATION_ENGINE_ORACLE_PASS_ESTIMATE_ONLY" else r["g6_calculability"]})
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-duration-engine-cases.csv.gz",cases,list(cases[0]))
    write_csv(dest/"g6-duration-offer-decisions.csv.gz",out,list(out[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),durationOffers=candidate_count,durationSignatures=len(decisions),caseCount=len(cases),passedCases=sum(x["engine_pass"] for x in cases),signatureDecisions=decisions,offerDecisions=dict(collections.Counter(r["g6_duration_replay"] for r in out)),cumulativeEstimatedOffers=sum(r["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for r in out),guards=evaluated["guards"],engineSha256=digest(engine),supplierCalls=0,pricesPromoted=0,identityChanges=0,automaticPublication=False,limitations=["Historical compiler overrides plain rates and chooses duration bands on whole-session duration, inclusive lower and exclusive upper bounds; independent Decimal oracle checks only that convention","Rate-changing bands or conflicting base/plain rules remain uncertified: no assumption of marginal surcharge, billing clock or invoice rounding","No supplier, Production or publication"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-duration-replay-report.json").write_text(j(report))
    print("G6_FR_DURATION_REPLAY "+j({k:v for k,v in report.items() if k not in ("sourcePin","signatureDecisions")}))
if __name__=="__main__":main()
