#!/usr/bin/env python3
"""G6.3f: date-filtered historical snapshots vs independent civil-date oracle."""
import collections,csv,gzip,json,os,pathlib,subprocess,sys
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import git_blob,j,dec,Q
from scripts.replay_g6_fr_time_windows import minute,contains,fmt,ZONE

VERSION="g6-fr-electroverse-2026-11-25-date-windows-v1"
DIMS=("energy","time","parking","flat")
TODAY=date(2026,11,25)
REASONS={"CONDITIONAL_RULE_ENGINE_AND_ORACLE_REQUIRED","DATE_APPLICABILITY_AND_BOUNDARY_REVIEW","UNKNOWN_RESTRICTION_TYPE:DATE_BASED","TIMEZONE_WINDOW_AND_DST_REVIEW","BASE_UNRESTRICTED_RULE_DISAGREEMENT","CHARGING_PARKING_CLOCK_AND_ROUNDING_REVIEW"}
def parse(raw):
    d=inspect_tariff(raw)
    if raw.get("isChargingFree") is not False or "DATE_BASED" not in d["restriction_types"] or set(d["restriction_types"])-{"DATE_BASED","TIME_BASED"} or set(d["reasons"])-REASONS:raise ValueError("Unexpected date scope")
    base={k:dec(d["base_rates"][k]) for k in DIMS}
    if dec(d["base_rates"]["vat"])!=0:raise ValueError("VAT")
    rules=[]
    for r in d["normalized_rules"]:
        t=set(r["types"]);c=r["conditions"]
        if t-{"DATE_BASED","TIME_BASED"} or set(c)!=({"dateRestrictions"} if "DATE_BASED" in t else set())|({"timeRestrictions"} if "TIME_BASED" in t else set()) or set(r["rates"])-set(DIMS):raise ValueError("Unknown rule shape")
        lo=hi=None;w=None
        if "DATE_BASED" in t:
            b=c["dateRestrictions"]
            if set(b)!={"startDate","endDate"}:raise ValueError("Unknown date fields")
            lo=date.fromisoformat(b["startDate"]) if b["startDate"] else None
            hi=date.fromisoformat(b["endDate"]) if b["endDate"] else None
            if lo and hi and hi<lo:raise ValueError("Reversed date bounds")
        if "TIME_BASED" in t:
            b=c["timeRestrictions"]
            if set(b)!={"startTime","endTime"}:raise ValueError("Unknown clock fields")
            w=(minute(b["startTime"]),minute(b["endTime"]))
            if w[0]==w[1]:raise ValueError("Equal clock endpoints")
        rules.append((lo,hi,w,{k:dec(v) for k,v in r["rates"].items()}))
    return base,rules
def active(rule,day,inclusive=False):
    lo,hi,_,_=rule
    return (lo is None or day>=lo) and (hi is None or day<hi or inclusive and day==hi)
def snapshot(base,rules,day,inclusive=False):
    groups=collections.defaultdict(dict)
    for r in rules:
        if not active(r,day,inclusive):continue
        target=groups[r[2]]
        for k,v in r[3].items():
            if k in target and target[k]!=v:raise ValueError("Conflicting active rates")
            target[k]=v
    hist={**base,**groups.pop(None,{})}
    if any(sum(contains(w,m) for w in groups)>1 for m in range(1440)):raise ValueError("Overlapping active clock windows")
    return hist,dict(groups)
def engine_rules(hist,windows):
    def rule(scope,start,end,r):
        return dict(scope=scope,start=start,end=end,currency="EUR",pricePerKwh=str(r["energy"]),chargePerMinute=str(r["time"]),idlePerMinute=str(r["parking"]),connectionFee=str(r["flat"]))
    return [rule("allDay","00:00","24:00",hist)]+[rule("timeWindow",fmt(a),fmt(b),{**hist,**r}) for (a,b),r in windows.items()]
def fixtures(rules):
    starts={"current":datetime(2026,11,25,12,tzinfo=ZONE),"spring":datetime(2026,3,29,1,30,tzinfo=ZONE),"autumn":datetime(2026,10,25,2,30,tzinfo=ZONE)}
    edges={d for lo,hi,_,_ in rules for d in (lo,hi) if d}
    for d in sorted(edges):
        at=datetime.combine(d,datetime.min.time(),tzinfo=ZONE).astimezone(timezone.utc)
        for m in (-60,-15,-1,0,1,60,720):starts[f"{d}_{m}m"]=at+timedelta(minutes=m)
    for m in sorted({v for _,_,w,_ in rules if w for v in w}):
        at=datetime(2026,11,25,m//60,m%60,tzinfo=ZONE).astimezone(timezone.utc)
        for off in (-15,0):starts[f"clock_{m}_{off}"]=at+timedelta(minutes=off)
    for name,at in starts.items():
        for mode,c,p in (("charge",60,0),("mixed",30,30),("parking",0,60)):
            yield dict(id=name+"_"+mode,startAt=at.astimezone(timezone.utc).isoformat(),duration=c+p,charging=c,parking=p,energy=str(dec(c)*Decimal("0.2")))
def quote(base,rules,f,mode="snapshot",inclusive=False,replace=False):
    """Independent minute oracle, same prorating as existing replay."""
    at=datetime.fromisoformat(f["startAt"]);start=at.astimezone(ZONE).date();cache={}
    parts={k:Decimal(0) for k in DIMS}
    for i in range(f["duration"]):
        local=(at+timedelta(minutes=i)).astimezone(ZONE);day=start if mode=="snapshot" else local.date()
        if day not in cache:cache[day]=snapshot(base,rules,day,inclusive)
        hist,windows=cache[day];m=local.hour*60+local.minute
        selected=next((r for w,r in windows.items() if contains(w,m)),None)
        rates=hist if selected is None else {**({k:Decimal(0) for k in DIMS} if replace else hist),**selected}
        if i==0:parts["flat"]=rates["flat"]
        if i<f["charging"]:parts["energy"]+=Decimal("0.2")*rates["energy"];parts["time"]+=rates["time"]
        else:parts["parking"]+=rates["parking"]
    return {**{k:str(v.quantize(Q,rounding=ROUND_HALF_UP)) for k,v in parts.items()},"total":str(sum(parts.values()).quantize(Q,rounding=ROUND_HALF_UP))}
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_date_windows" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    a=download(root/"prior",pin["prior"],{"decisions":("g6-combined-mixed-offer-decisions.csv.gz",),"cases":("g6-combined-mixed-cases.csv.gz",),"report":("g6-combined-mixed-report.json",)})
    verify(a["decisions"],pin["decisionsSha256"]);verify(a["cases"],pin["casesSha256"])
    ar=json.loads(a["report"].read_text())
    if ar["codeSha"]!=pin["prior"]["codeSha"] or ar["sourcePin"]!=pin["priorSourcePin"] or ar["identityPairs"]!=24115 or ar["caseCount"]!=66 or ar["passedCases"]!=66 or ar["combinedOffers"]!=70 or ar["cumulativeEstimatedOffers"]!=14517 or ar["candidateSha256"]!=pin["candidateSha256"]:raise ValueError("Prior lineage")
    with gzip.open(a["decisions"],"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115:raise ValueError("Identity")
    groups=collections.defaultdict(list)
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262:raise ValueError("Inventory")
    requests=[];decisions={};cases=[];by=collections.defaultdict(collections.Counter)
    for sig,rr in sorted(groups.items()):
        if len({r["raw_price_payload"] for r in rr})!=1 or len({r["family"] for r in rr})!=1:raise ValueError("Signature ambiguity")
        raw=json.loads(rr[0]["raw_price_payload"])
        if signature(raw)!=sig or any(r["raw_verified"].lower()!="true" for r in rr):raise ValueError("Raw lineage")
        if rr[0]["family"] not in ("DATE_BASED","DATE_BASED+TIME_BASED"):continue
        if any(r["g6_calculability"]!="NOT_YET_CERTIFIED" for r in rr):raise ValueError("Prior estimate")
        d=inspect_tariff(raw)
        if any(json.loads(r["normalized_rules"])!=d["normalized_rules"] or json.loads(r["base_rates"])!=d["base_rates"] for r in rr):raise ValueError("Audit lineage")
        decisions[sig]=dict(offers=len(rr),family=rr[0]["family"],status="DATE_STRUCTURE_REVIEW",reason="")
        try:base,rules=parse(raw)
        except ValueError as e:decisions[sig]["reason"]=str(e);continue
        decisions[sig]["emptyDateIntervals"]=sum(lo is not None and lo==hi for lo,hi,_,_ in rules)
        decisions[sig]["activeAtAudit"]=sum(active(r,TODAY) for r in rules)
        for f in fixtures(rules):
            day=datetime.fromisoformat(f["startAt"]).astimezone(ZONE).date()
            try:
                hist,w=snapshot(base,rules,day);expected=quote(base,rules,f)
            except ValueError as e:
                state="DATE_HISTORICAL_STRUCTURE_REVIEW";by[sig][state]+=1
                cases.append(dict(signature=sig,scenario=f["id"],session=j(f),oracle="",alternatives="",engine_result="",engine_pass="",decision=state,reason=str(e)))
                continue
            models={};errors={}
            for mode in ("snapshot","dynamic"):
                for inc in (False,True):
                    for repl in (False,True):
                        name=f"{mode}_{'inclusive' if inc else 'exclusive'}_{'replace' if repl else 'inherit'}"
                        try:models[name]=quote(base,rules,f,mode,inc,repl)
                        except ValueError as e:errors[name]=str(e)
            # No active dated rule can mean unconfirmed applicability, even
            # if the historical snapshot falls back to a numeric base.
            start=datetime.fromisoformat(f["startAt"])
            gap=any(not any(active(r,(start+timedelta(minutes=i)).astimezone(ZONE).date()) for r in rules) for i in range(f["duration"]))
            requests.append(dict(signature=sig,fixture=f,rules=engine_rules(hist,w),expected=expected,models=models,errors=errors,gap=gap))
    if len(decisions)!=23 or sum(d["offers"] for d in decisions.values())!=1596 or collections.Counter({k:sum(d["offers"] for d in decisions.values() if d["family"]==k) for k in ("DATE_BASED","DATE_BASED+TIME_BASED")})!={"DATE_BASED":1499,"DATE_BASED+TIME_BASED":97} or not requests:raise ValueError("Cohort")
    engine=pathlib.Path("migration/v9/g6-candidate/pricing-engine.cjs")
    verify(engine,pin["candidateSha256"]);verify(pathlib.Path("migration/v9/g6-reference/pricing-engine.cjs"),pin["engineSha256"])
    if git_blob(engine)!=pin["candidateGitBlob"] or git_blob(pathlib.Path("scripts/build_electroverse_france_evse_overlay.mjs"))!=pin["compilerBlob"]:raise ValueError("Reference")
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_time_windows_engine.cjs")
    result=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(result["results"])!=len(requests) or not all(result["guards"].values()) or len(result["guards"])!=4:raise ValueError("Guard")
    for x,r in zip(requests,result["results"]):
        sig=x["signature"]
        if r["signature"]!=sig or r["scenario"]!=x["fixture"]["id"]:raise ValueError("Order")
        try:good=r["complete"] is True and r["currency"]=="EUR" and all(dec(r[k])==dec(x["expected"][k]) for k in ("total",*DIMS))
        except (ValueError,ArithmeticError):good=False
        agree=not x["errors"] and not x["gap"] and len({j(v) for v in x["models"].values()})==1
        state="DATE_ENGINE_MISMATCH" if not good else "DATE_APPLICABILITY_REVIEW" if x["gap"] else "CONDITIONAL_ESTIMATE_AGREEMENT" if agree else "INCALCULABLE_SEMANTICS"
        by[sig][state]+=1
        cases.append(dict(signature=sig,scenario=r["scenario"],session=j(x["fixture"]),oracle=j(x["expected"]),alternatives=j({"models":x["models"],"errors":x["errors"]}),engine_result=j(r),engine_pass=good,decision=state,reason="No active dated rule" if x["gap"] else ""))
    for sig,d in decisions.items():
        if sig in by:
            d["scenarioDecisions"]=dict(by[sig])
            d["status"]="DATE_ENGINE_REVIEW" if by[sig]["DATE_ENGINE_MISMATCH"] else "DATE_SCENARIO_DEPENDENT_REVIEW"
    out=[]
    for r in rows:
        d=decisions.get(r["tariff_signature"],{})
        out.append({**r,"g6_date_replay":d.get("status","NOT_IN_DATE_PHASE"),"g6_date_reason":d.get("reason",""),"g6_date_scenarios":j(d.get("scenarioDecisions",{})) if d else ""})
    if sum(r["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for r in out)!=14517:raise ValueError("Prior estimates")
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-date-window-cases.csv.gz",cases,list(cases[0]))
    write_csv(dest/"g6-date-window-offer-decisions.csv.gz",out,list(out[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),dateOffers=1596,dateSignatures=23,caseCount=len(cases),executedCases=len(requests),passedCases=sum(x["engine_pass"] is True for x in cases),signatureDecisions=decisions,scenarioDecisions=dict(collections.Counter(x["decision"] for x in cases)),offerDecisions=dict(collections.Counter(r["g6_date_replay"] for r in out)),guards=result["guards"],cumulativeEstimatedOffers=14517,engineSha256=pin["engineSha256"],candidateSha256=digest(engine),identityChanges=0,pricesPromoted=0,supplierCalls=0,automaticPublication=False,limitations=["Historical compiler selects date intervals at build time, inclusive start/exclusive end; replay fixes snapshot at session start only to inspect archived versions, not actual old tariffs","Compare snapshot to dynamically changing civil date, inclusive end and missing window components as diagnostic hypotheses; no active dated rule is not a confirmed historical price","Zero-length exclusive intervals and conflicting historical rules retained in evidence; no contract proof, automatic certification or Production integration"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-date-window-report.json").write_text(j(report))
    print("G6_FR_DATE_WINDOWS "+j({k:v for k,v in report.items() if k not in ("sourcePin","signatureDecisions")}))
if __name__=="__main__":main()
