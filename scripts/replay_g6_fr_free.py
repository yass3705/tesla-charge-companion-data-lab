#!/usr/bin/env python3
"""G6.3b: explicit zero-priced free flag; preserve historical G5/G6 evidence."""
import collections,csv,gzip,json,os,pathlib,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff,parse_components
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import git_blob,j,dec
from scripts.replay_g6_fr_unrestricted_time import fixtures,oracle

VERSION="g6-fr-electroverse-2026-11-25-free-v1"
EXPECTED={"FREE_FLAG_AND_COMPONENTS_REVIEW","FREE_WITH_PRICED_COMPONENTS_REVIEW"}
DIMS={"energy","time","parking","flat","vat"}
def free_gate(raw):
    if raw.get("isChargingFree") is not True:return False,"FREE_FLAG_NOT_TRUE"
    if set(raw)!={"isChargingFree","priceComponents","complexPricingDetail"}:return False,"UNKNOWN_PAYLOAD_FIELD"
    cx=raw.get("complexPricingDetail")
    if not isinstance(cx,dict) or cx.get("currency")!="EUR":return False,"CURRENCY_NOT_PROVEN"
    if cx.get("restrictions")!=[]:return False,"RESTRICTIONS_NOT_EXPLICITLY_EMPTY"
    if set(cx)-{"currency","restrictions","__typename"}:return False,"UNKNOWN_COMPLEX_FIELD"
    components=raw.get("priceComponents")
    rates,errors=parse_components(components,"BASE")
    if errors or set(rates)!=DIMS:return False,"COMPONENTS_MISSING_OR_UNRECOGNIZED"
    if any(set(x)-{"__typename","formattedValue"} for x in components):return False,"UNKNOWN_COMPONENT_FIELD"
    if any(v!=0 for v in rates.values()):return False,"FREE_FLAG_NONZERO_COMPONENT"
    if set(inspect_tariff(raw)["reasons"])-EXPECTED:return False,"OTHER_TARIFF_REVIEW_REASON"
    return True,"FREE_FLAG_EXPLICIT_ZERO_COMPONENTS"
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_explicit_free_replay" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    a=download(root/"prior",pin["prior"],{"decisions.csv.gz":("g6-time-offer-decisions.csv.gz",),"cases.csv.gz":("g6-time-engine-cases.csv.gz",),"report.json":("g6-time-replay-report.json",)})
    verify(a["decisions.csv.gz"],pin["decisionsSha256"]);verify(a["cases.csv.gz"],pin["casesSha256"])
    ar=json.loads(a["report.json"].read_text())
    if ar["codeSha"]!=pin["prior"]["codeSha"] or ar["sourcePin"]!=pin["priorSourcePin"] or ar["identityPairs"]!=24115 or ar["passedCases"]!=420 or ar["passedSignatures"]!=60 or ar["cumulativeEstimatedOffers"]!=14454 or ar["engineSha256"]!=pin["engineSha256"]:raise ValueError("Prior lineage")
    with gzip.open(a["decisions.csv.gz"],"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115:raise ValueError("Identity coverage")
    free=[];groups=collections.defaultdict(list)
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262:raise ValueError("Signature count")
    for sig,rr in groups.items():
        if len({r["raw_price_payload"] for r in rr})!=1:raise ValueError("Signature ambiguity")
        raw=json.loads(rr[0]["raw_price_payload"])
        if signature(raw)!=sig or any(r["raw_verified"].lower()!="true" for r in rr):raise ValueError("Raw lineage")
        if raw.get("isChargingFree") is True:
            ok,reason=free_gate(raw)
            if not ok:raise ValueError("Free cohort must be reviewed: "+reason)
            if any(set(json.loads(r["reasons"]))!=EXPECTED or r["g6_calculability"]!="NOT_YET_CERTIFIED" or r["family"]!="NO_DECLARED_RESTRICTIONS" for r in rr):raise ValueError("Historical free scope")
            free.extend(rr)
    sigs={r["tariff_signature"] for r in free}
    if len(free)!=55 or sigs!={pin["freeSignature"]} or len({r["station_id"] for r in free})!=4:raise ValueError("Free cohort changed")
    sig=pin["freeSignature"];rates={k:"0" for k in DIMS}
    requests=[dict(signature=sig,fixture=f,expected=oracle(rates,f),rates=rates) for f in fixtures()]
    spec=pin["priorSourcePin"]["priorSourcePin"]["engine"];engine=pathlib.Path(spec["auditPath"])
    if git_blob(engine)!=spec["gitBlob"]:raise ValueError("Engine blob")
    verify(engine,pin["engineSha256"])
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_unrestricted_time_engine.cjs")
    evaluated=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(evaluated["results"])!=len(requests) or set(evaluated["guards"])!={"missing_charge","missing_parking","negative_time","unknown_fee","missing_duration"} or not all(evaluated["guards"].values()):raise ValueError("Engine guards")
    cases=[]
    for x,r in zip(requests,evaluated["results"]):
        if r["signature"]!=sig or r["scenario"]!=x["fixture"]["id"]:raise ValueError("Result order")
        good=r["complete"] is True and r["currency"]=="EUR" and all(r[k] is not None and dec(r[k])==0 for k in ("total","energy","time","parking","flat"))
        cases.append(dict(signature=sig,scenario=x["fixture"]["id"],session=j(x["fixture"]),oracle=j(x["expected"]),engine_result=j(r),engine_pass=good))
    passed=all(x["engine_pass"] for x in cases)
    out=[]
    for r in rows:
        selected=r["tariff_signature"]==sig
        status=("EXPLICIT_FREE_ENGINE_ORACLE_PASS" if passed else "EXPLICIT_FREE_ENGINE_ORACLE_REVIEW") if selected else "NOT_IN_FREE_PHASE"
        out.append({**r,"g6_free_replay":status,"g6_free_reason":"FREE_FLAG_EXPLICIT_ZERO_COMPONENTS" if selected else "",
            "g6_calculability":"ENGINE_ORACLE_PASS_ESTIMATE_ONLY" if selected and passed else r["g6_calculability"]})
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-free-engine-cases.csv.gz",cases,list(cases[0]))
    write_csv(dest/"g6-free-offer-decisions.csv.gz",out,list(out[0]))
    counts=collections.Counter(x["g6_free_replay"] for x in out)
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),freeOffers=55,freeSignatures=1,freeStations=4,caseCount=len(cases),passedCases=sum(x["engine_pass"] for x in cases),passedSignatures=int(passed),offerDecisions=dict(counts),cumulativeEstimatedOffers=sum(x["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for x in out),guards=evaluated["guards"],engineSha256=digest(engine),supplierCalls=0,pricesPromoted=0,identityChanges=0,automaticPublication=False,limitations=["Only explicit true with complete zero-valued components, EUR and explicitly empty restrictions","G5 historic reasons retained; G6 decision separate; positive, missing or unknown price data never deemed free","No assertion of current provider tariff or invoice; no publication"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-free-replay-report.json").write_text(j(report))
    print("G6_FR_FREE_REPLAY "+j({k:v for k,v in report.items() if k!="sourcePin"}))
if __name__=="__main__":main()
