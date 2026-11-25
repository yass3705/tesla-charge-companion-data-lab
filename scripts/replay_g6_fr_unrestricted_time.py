#!/usr/bin/env python3
"""G6.3a: replay unrestricted time components against the pinned engine; estimates only."""
import collections,csv,gzip,json,os,pathlib,subprocess,sys
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import git_blob,j,dec,Q

VERSION="g6-fr-electroverse-2026-11-25-unrestricted-time-v1"
REASON=["CHARGING_PARKING_CLOCK_AND_ROUNDING_REVIEW"]
def oracle(rates,f):
    quantities={"energy":f["energy"],"time":f["charging"],"parking":f["parking"],"flat":"1"}
    parts={k:(dec(rates[k])*dec(v)).quantize(Q,rounding=ROUND_HALF_UP) for k,v in quantities.items()}
    return {**{k:str(v) for k,v in parts.items()},"total":str(sum(parts.values()))}
def fixtures():
    return [
        dict(id="charge_only",energy="10",charging="30",parking="0",duration="30",startAt="2026-11-25T10:00:00Z"),
        dict(id="charge_and_parking",energy="12.345",charging="45",parking="15",duration="60",startAt="2026-11-25T10:00:00Z"),
        dict(id="fractional_minutes",energy="1.005",charging="1.25",parking="0.75",duration="2",startAt="2026-11-25T10:00:00Z"),
        dict(id="parking_only_phase",energy="0",charging="0",parking="20",duration="20",startAt="2026-11-25T10:00:00Z"),
        dict(id="midnight",energy="23.456",charging="45",parking="45",duration="90",startAt="2026-11-25T22:45:00Z"),
        dict(id="spring_dst",energy="50",charging="100",parking="20",duration="120",startAt="2026-03-29T00:30:00Z"),
        dict(id="autumn_dst",energy="80",charging="210",parking="30",duration="240",startAt="2026-10-25T00:30:00Z"),
    ]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_unrestricted_time_replay" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","identityChanges")):raise ValueError("Scope")
    a=download(root/"prior",pin["prior"],{"decisions.csv.gz":("g6-simple-offer-decisions.csv.gz",),"cases.csv.gz":("g6-simple-engine-cases.csv.gz",),"report.json":("g6-simple-replay-report.json",)})
    verify(a["decisions.csv.gz"],pin["decisionsSha256"]);verify(a["cases.csv.gz"],pin["casesSha256"])
    ar=json.loads(a["report.json"].read_text())
    if ar["codeSha"]!=pin["prior"]["codeSha"] or ar["sourcePin"]!=pin["priorSourcePin"] or ar["identityPairs"]!=24115 or ar["passedCases"]!=570 or ar["passedSignatures"]!=95 or ar["offerDecisions"]!={"SIMPLE_ENGINE_ORACLE_PASS":8876,"NOT_IN_SIMPLE_PHASE":15239} or ar["engineSha256"]!=pin["engineSha256"]:raise ValueError("Prior lineage")
    with gzip.open(a["decisions.csv.gz"],"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115:raise ValueError("Identity coverage")
    groups=collections.defaultdict(list)
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262:raise ValueError("Signature count")
    selected={};split=collections.Counter()
    for sig,rr in groups.items():
        if len({r["raw_price_payload"] for r in rr})!=1 or len({r["audit_status"] for r in rr})!=1 or len({r["g6_simple_replay"] for r in rr})!=1:raise ValueError("Signature ambiguity")
        raw=json.loads(rr[0]["raw_price_payload"])
        if signature(raw)!=sig or any(r["raw_verified"].lower()!="true" for r in rr):raise ValueError("Raw lineage")
        if rr[0]["family"]!="NO_DECLARED_RESTRICTIONS" or rr[0]["audit_status"]!="REVIEW_REQUIRED" or raw.get("isChargingFree") is not False:continue
        d=inspect_tariff(raw);rates=d["base_rates"]
        if d["reasons"]!=REASON or d["condition_fields"] or d["restriction_types"] or d["audit_status"]!="REVIEW_REQUIRED" or any(json.loads(r["reasons"])!=REASON or json.loads(r["base_rates"])!=rates or r["g6_simple_replay"]!="NOT_IN_SIMPLE_PHASE" for r in rr):raise ValueError("Scope changed")
        if set(rates)!={"energy","flat","time","parking","vat"} or dec(rates["vat"])!=0 or any(dec(v)<0 for v in rates.values()) or dec(rates["time"])+dec(rates["parking"])<=0:raise ValueError("Invalid rates")
        selected[sig]=rates
        split["both" if dec(rates["time"])>0 and dec(rates["parking"])>0 else "charge" if dec(rates["time"])>0 else "parking"]+=len(rr)
    if len(selected)!=60 or sum(len(groups[k]) for k in selected)!=5578 or dict(split)!={"charge":4893,"parking":602,"both":83}:raise ValueError("Cohort changed")
    requests=[dict(signature=sig,fixture=f,expected=oracle(rates,f),rates=rates) for sig,rates in sorted(selected.items()) for f in fixtures()]
    engine=pathlib.Path(pin["priorSourcePin"]["engine"]["auditPath"])
    if git_blob(engine)!=pin["priorSourcePin"]["engine"]["gitBlob"]:raise ValueError("Engine blob")
    verify(engine,pin["engineSha256"])
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_unrestricted_time_engine.cjs")
    evaluated=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(evaluated["results"])!=len(requests) or set(evaluated["guards"])!={"missing_charge","missing_parking","negative_time","unknown_fee","missing_duration"} or not all(evaluated["guards"].values()):raise ValueError("Guard failure")
    cases=[];failed=set()
    for x,r in zip(requests,evaluated["results"]):
        if r["signature"]!=x["signature"] or r["scenario"]!=x["fixture"]["id"]:raise ValueError("Result order")
        try:good=r["complete"] is True and r["currency"]=="EUR" and all(dec(r[k])==dec(x["expected"][k]) for k in ("total","energy","time","parking","flat"))
        except (ValueError,ArithmeticError):good=False
        if not good:failed.add(x["signature"])
        cases.append(dict(signature=x["signature"],scenario=x["fixture"]["id"],session=j(x["fixture"]),oracle=j(x["expected"]),engine_result=j(r),engine_pass=good))
    out=[]
    for row in rows:
        sig=row["tariff_signature"]
        status="UNRESTRICTED_TIME_ENGINE_ORACLE_PASS" if sig in selected and sig not in failed else "UNRESTRICTED_TIME_ENGINE_ORACLE_REVIEW" if sig in failed else "NOT_IN_TIME_PHASE"
        out.append({**row,"g6_time_replay":status,"g6_calculability":"ENGINE_ORACLE_PASS_ESTIMATE_ONLY" if status=="UNRESTRICTED_TIME_ENGINE_ORACLE_PASS" else row["g6_calculability"]})
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-time-engine-cases.csv.gz",cases,list(cases[0]))
    write_csv(dest/"g6-time-offer-decisions.csv.gz",out,list(out[0]))
    counts=collections.Counter(x["g6_time_replay"] for x in out)
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),timeSignatures=len(selected),timeOffers=5578,phaseSplit=dict(split),scenariosPerSignature=len(fixtures()),caseCount=len(cases),passedCases=sum(x["engine_pass"] for x in cases),passedSignatures=len(selected)-len(failed),failedSignatures=sorted(failed),offerDecisions=dict(counts),cumulativeEstimatedOffers=sum(x["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for x in out),guards=evaluated["guards"],engineSha256=digest(engine),supplierCalls=0,pricesPromoted=0,identityChanges=0,automaticPublication=False,limitations=["TimeRate mapped to charging minutes, ParkingTimeRate to post-charge minutes, consistent with historical Electroverse adapter and rich-pricing oracle; invoice clock and billing increments not independently established","Exact Decimal prorated estimates at six decimals, not invoice validation; no fee double-counting","Other offers unchanged; G6 global not passed"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-time-replay-report.json").write_text(j(report))
    print("G6_FR_TIME_REPLAY "+j({k:v for k,v in report.items() if k!="sourcePin"}))
if __name__=="__main__":main()
