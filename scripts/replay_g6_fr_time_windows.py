#!/usr/bin/env python3
"""G6.3d: historical window compilation and independent UTC elapsed-minute oracle."""
import collections,csv,gzip,json,os,pathlib,subprocess,sys
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import git_blob,j,dec,Q

VERSION="g6-fr-electroverse-2026-11-25-time-windows-v1"
DIMS=("energy","time","parking","flat")
ZONE=ZoneInfo("Europe/Paris")
REASONS={"CONDITIONAL_RULE_ENGINE_AND_ORACLE_REQUIRED","TIMEZONE_WINDOW_AND_DST_REVIEW","BASE_UNRESTRICTED_RULE_DISAGREEMENT","CHARGING_PARKING_CLOCK_AND_ROUNDING_REVIEW"}
def minute(s):
    if not isinstance(s,str) or len(s)!=8 or s[2]!=":" or s[5:]!=":00":raise ValueError("Unsupported time precision")
    h,m=int(s[:2]),int(s[3:5])
    if not 0<=h<=23 or not 0<=m<=59:raise ValueError("Invalid clock")
    return h*60+m
def contains(w,m):
    a,b=w
    return a<=m<b if a<b else m>=a or m<b
def compile_windows(raw):
    d=inspect_tariff(raw)
    if raw.get("isChargingFree") is not False or d["restriction_types"]!=["TIME_BASED"] or d["condition_fields"]!=["timeRestrictions"] or set(d["reasons"])-REASONS:raise ValueError("Unrecognized time scope")
    base={k:dec(d["base_rates"][k]) for k in DIMS}
    if dec(d["base_rates"]["vat"])!=0:raise ValueError("VAT")
    plain={}; windows={}
    for r in d["normalized_rules"]:
        if set(r["rates"])-set(DIMS):raise ValueError("Unknown component")
        rates={k:dec(v) for k,v in r["rates"].items()}
        if r["types"]==[] and r["conditions"]=={}:target=plain
        elif r["types"]==["TIME_BASED"] and set(r["conditions"])=={"timeRestrictions"}:
            t=r["conditions"]["timeRestrictions"]
            if set(t)!={"startTime","endTime"}:raise ValueError("Unknown window fields")
            w=(minute(t["startTime"]),minute(t["endTime"]))
            if w[0]==w[1]:raise ValueError("Equal endpoints")
            target=windows.setdefault(w,{})
        else:raise ValueError("Unknown rule")
        for k,v in rates.items():
            if k in target and target[k]!=v:raise ValueError("Conflicting rates")
            target[k]=v
    if not windows or any(sum(contains(w,m) for w in windows)>1 for m in range(1440)):raise ValueError("Overlapping or missing windows")
    historical={**base,**plain}
    return base,historical,plain,windows
def fmt(m):
    return f"{m//60:02d}:{m%60:02d}"
def rules_for(historical,windows):
    def rule(scope,start,end,r):
        return dict(scope=scope,start=start,end=end,currency="EUR",pricePerKwh=str(r["energy"]),chargePerMinute=str(r["time"]),idlePerMinute=str(r["parking"]),connectionFee=str(r["flat"]))
    return [rule("allDay","00:00","24:00",historical)]+[rule("timeWindow",fmt(a),fmt(b),{**historical,**r}) for (a,b),r in windows.items()]
def fixtures(windows):
    # Exact UTC elapsed time. 0.2 kWh per charge minute avoids segment rounding noise.
    starts={"day":datetime(2026,11,25,11,tzinfo=timezone.utc),"midnight":datetime(2026,11,25,22,45,tzinfo=timezone.utc),"spring_dst":datetime(2026,3,29,0,30,tzinfo=timezone.utc),"autumn_dst":datetime(2026,10,25,0,30,tzinfo=timezone.utc)}
    for m in sorted({v for w in windows for v in w}):
        at=datetime(2026,11,25,m//60,m%60,tzinfo=ZONE).astimezone(timezone.utc)
        for delta in (-15,-1,0,1):starts[f"boundary_{m}_{delta}"]=at+timedelta(minutes=delta)
    for label,at in starts.items():
        for mode,c,p in (("charge",60,0),("mixed",30,30),("parking",0,60)):
            yield dict(id=label+"_"+mode,startAt=at.isoformat(),charging=c,parking=p,duration=c+p,energy=str(dec(c)*Decimal("0.2")))
def oracle(seed,windows,f,replace_missing=False,start_only=False):
    at=datetime.fromisoformat(f["startAt"]);c=f["charging"]
    def get(i):
        local=(at+timedelta(minutes=i)).astimezone(ZONE);m=local.hour*60+local.minute
        active=next((r for w,r in windows.items() if contains(w,m)),None)
        if active is None:return seed
        return {**({k:Decimal(0) for k in DIMS} if replace_missing else seed),**active}
    parts={k:Decimal(0) for k in DIMS}
    parts["flat"]=get(0)["flat"]
    for i in range(f["duration"]):
        r=get(0 if start_only else i)
        if i<c:parts["energy"]+=Decimal("0.2")*r["energy"];parts["time"]+=r["time"]
        else:parts["parking"]+=r["parking"]
    return {**{k:str(v.quantize(Q,rounding=ROUND_HALF_UP)) for k,v in parts.items()},"total":str(sum(parts.values()).quantize(Q,rounding=ROUND_HALF_UP))}
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_time_windows" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    a=download(root/"prior",pin["prior"],{"decisions.csv.gz":("g6-duration-semantics-offer-decisions.csv.gz",),"cases.csv.gz":("g6-duration-semantics-cases.csv.gz",),"delayed.csv.gz":("g6-duration-delayed-alternatives.csv.gz",),"report.json":("g6-duration-semantics-report.json",)})
    for k,h in (("decisions","decisionsSha256"),("cases","casesSha256"),("delayed","delayedSha256")):verify(a[k+".csv.gz"],pin[h])
    ar=json.loads(a["report.json"].read_text())
    if ar["codeSha"]!=pin["prior"]["codeSha"] or ar["sourcePin"]!=pin["priorSourcePin"] or ar["identityPairs"]!=24115 or ar["cumulativeEstimatedOffers"]!=14517 or ar["delayedPassed"]!=984 or ar["scenarioDecisions"]!={"CONDITIONAL_ESTIMATE_AGREEMENT":438,"INCALCULABLE_SEMANTICS":354} or ar["engineSha256"]!=pin["engineSha256"]:raise ValueError("Prior lineage")
    with gzip.open(a["decisions.csv.gz"],"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115:raise ValueError("Identity")
    groups=collections.defaultdict(list)
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262:raise ValueError("Signature inventory")
    requests=[];decisions={}
    for sig,rr in sorted(groups.items()):
        if len({r["raw_price_payload"] for r in rr})!=1 or len({r["family"] for r in rr})!=1:raise ValueError("Signature ambiguity")
        raw=json.loads(rr[0]["raw_price_payload"])
        if signature(raw)!=sig or any(r["raw_verified"].lower()!="true" for r in rr):raise ValueError("Raw lineage")
        if rr[0]["family"]!="TIME_BASED":continue
        if any(r["g6_calculability"]!="NOT_YET_CERTIFIED" for r in rr):raise ValueError("Previous estimate")
        decisions[sig]=dict(offers=len(rr),status="TIME_WINDOW_REVIEW",reason="")
        try:base,historical,plain,windows=compile_windows(raw)
        except ValueError as e:
            decisions[sig]["reason"]=str(e);continue
        for f in fixtures(windows):
            models={f"{b}_{m}_{s}":oracle(seed,windows,f,replace_missing=(m=="replace"),start_only=(s=="start")) for b,seed in (("base",base),("historical",historical)) for m in ("inherit","replace") for s in ("segmented","start")}
            expected=models["historical_inherit_segmented"]
            requests.append(dict(signature=sig,fixture=f,rules=rules_for(historical,windows),expected=expected,models=models))
    if len(decisions)!=18 or sum(d["offers"] for d in decisions.values())!=1367 or not requests:raise ValueError("Cohort")
    node=pin
    while "engine" not in node:node=node["priorSourcePin"]
    spec=node["engine"];engine=pathlib.Path(spec["auditPath"])
    if git_blob(engine)!=spec["gitBlob"] or git_blob(pathlib.Path("scripts/build_electroverse_france_evse_overlay.mjs"))!=pin["compilerBlob"]:raise ValueError("Reference")
    verify(engine,pin["engineSha256"])
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_time_windows_engine.cjs")
    result=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(result["results"])!=len(requests) or not all(result["guards"].values()) or len(result["guards"])!=4:raise ValueError("Guard")
    cases=[];by=collections.defaultdict(collections.Counter)
    for x,r in zip(requests,result["results"]):
        sig=x["signature"]
        if r["signature"]!=sig or r["scenario"]!=x["fixture"]["id"]:raise ValueError("Result order")
        try:good=r["complete"] is True and r["currency"]=="EUR" and all(dec(r[k])==dec(x["expected"][k]) for k in ("total",*DIMS))
        except (ValueError,ArithmeticError):good=False
        agree=len({j(v) for v in x["models"].values()})==1
        state="TIME_WINDOW_ENGINE_MISMATCH" if not good else "CONDITIONAL_ESTIMATE_AGREEMENT" if agree else "INCALCULABLE_SEMANTICS"
        by[sig][state]+=1
        cases.append(dict(signature=sig,scenario=r["scenario"],session=j(x["fixture"]),oracle=j(x["expected"]),alternatives=j(x["models"]),engine_result=j(r),engine_pass=good,decision=state))
    for sig,d in decisions.items():
        if sig in by:
            d["scenarioDecisions"]=dict(by[sig]);d["status"]="TIME_WINDOW_ENGINE_REVIEW" if by[sig]["TIME_WINDOW_ENGINE_MISMATCH"] else "TIME_WINDOW_SCENARIO_DEPENDENT_REVIEW"
    out=[]
    for r in rows:
        d=decisions.get(r["tariff_signature"],{})
        out.append({**r,"g6_time_window_replay":d.get("status","NOT_IN_TIME_WINDOW_PHASE"),"g6_time_window_reason":d.get("reason",""),"g6_time_window_scenarios":j(d.get("scenarioDecisions",{})) if d else ""})
    if sum(r["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for r in out)!=14517:raise ValueError("Prior estimates")
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-time-window-cases.csv.gz",cases,list(cases[0]))
    write_csv(dest/"g6-time-window-offer-decisions.csv.gz",out,list(out[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),timeWindowOffers=1367,timeWindowSignatures=18,caseCount=len(cases),passedCases=sum(x["engine_pass"] for x in cases),signatureDecisions=decisions,scenarioDecisions=dict(collections.Counter(x["decision"] for x in cases)),offerDecisions=dict(collections.Counter(r["g6_time_window_replay"] for r in out)),guards=result["guards"],cumulativeEstimatedOffers=14517,engineSha256=digest(engine),identityChanges=0,pricesPromoted=0,supplierCalls=0,automaticPublication=False,limitations=["Historical base/plain merge, window overrides and segmented calculation replayed; independent UTC minute oracle respects Paris civil clock and DST; fee once at start","Alternative missing component replacement vs inheritance and start-only vs segmented selection are diagnostic hypotheses, not proof of contract","No new unconditional certification, no supplier or Production changes; conditional results not ranked"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-time-window-report.json").write_text(j(report))
    print("G6_FR_TIME_WINDOWS "+j({k:v for k,v in report.items() if k not in ("sourcePin","signatureDecisions")}))
if __name__=="__main__":main()
