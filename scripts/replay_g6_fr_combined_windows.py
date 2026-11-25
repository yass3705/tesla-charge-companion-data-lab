#!/usr/bin/env python3
"""G6.3e: combined duration/clock windows against the isolated candidate."""
import collections,csv,gzip,json,os,pathlib,subprocess,sys
from datetime import datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import git_blob,j,dec,Q
from scripts.replay_g6_fr_time_windows import minute,contains,fmt,ZONE

VERSION="g6-fr-electroverse-2026-11-25-combined-windows-v1"
DIMS={"energy":"ENERGY","time":"TIME","parking":"PARKING_TIME","flat":"FLAT"}
MAX=7*24*3600
REASONS={"CONDITIONAL_RULE_ENGINE_AND_ORACLE_REQUIRED","DURATION_BILLING_CLOCK_AND_BOUNDARY_REVIEW","TIMEZONE_WINDOW_AND_DST_REVIEW","BASE_UNRESTRICTED_RULE_DISAGREEMENT","CHARGING_PARKING_CLOCK_AND_ROUNDING_REVIEW"}
def compile_combined(raw):
    d=inspect_tariff(raw)
    if raw.get("isChargingFree") is not False or d["restriction_types"]!=["DURATION_BASED","TIME_BASED"] or set(d["condition_fields"])!={"durationRestrictions","timeRestrictions"} or set(d["reasons"])-REASONS:raise ValueError("Unknown scope")
    base={k:dec(d["base_rates"][k]) for k in DIMS}
    if dec(d["base_rates"]["vat"])!=0:raise ValueError("VAT")
    plain={};groups={}
    def merge(target,rates):
        for k,v in rates.items():
            if k in target and target[k]!=v:raise ValueError("Conflicting plain rates")
            target[k]=v
    for r in d["normalized_rules"]:
        if set(r["rates"])-set(DIMS):raise ValueError("Unknown component")
        rates={k:dec(v) for k,v in r["rates"].items()}
        types=set(r["types"]);c=r["conditions"]
        if not types and not c:merge(plain,rates);continue
        if "TIME_BASED" not in types or set(c)!={"timeRestrictions"}|({"durationRestrictions"} if "DURATION_BASED" in types else set()) or types-{"TIME_BASED","DURATION_BASED"}:raise ValueError("Unsupported rule shape")
        t=c["timeRestrictions"]
        if set(t)!={"startTime","endTime"}:raise ValueError("Unknown clock fields")
        w=(minute(t["startTime"]),minute(t["endTime"]))
        if w[0]==w[1]:raise ValueError("Equal window endpoints")
        g=groups.setdefault(w,{"plain":{},"bands":[]})
        if "DURATION_BASED" not in types:merge(g["plain"],rates);continue
        b=c["durationRestrictions"]
        if set(b)!={"minDurationSeconds","maxDurationSeconds"}:raise ValueError("Unknown bounds")
        lo,hi=b["minDurationSeconds"],b["maxDurationSeconds"]
        if lo is not None and (type(lo) is not int or lo<0):raise ValueError("Invalid lower bound")
        if hi is not None and (type(hi) is not int or hi<=0):raise ValueError("Invalid upper bound")
        lo=lo or 0
        if hi is not None and hi<=lo:raise ValueError("Empty band")
        g["bands"].extend((k,lo,hi,v) for k,v in rates.items())
    if not groups or not any(g["bands"] for g in groups.values()):raise ValueError("Missing combined bands")
    if any(sum(contains(w,m) for w in groups)>1 for m in range(1440)):raise ValueError("Overlapping windows")
    for g in groups.values():
        for k in DIMS:
            a=sorted((b for b in g["bands"] if b[0]==k),key=lambda x:x[1])
            for x,y in zip(a,a[1:]):
                if x[2] is None or x[2]>y[1]:raise ValueError("Overlapping duration bands")
    return base,plain,groups

def rules_for(base,plain,groups):
    hist={**base,**plain}
    def rule(scope,start,end,r,bands):
        return dict(scope=scope,start=start,end=end,currency="EUR",pricePerKwh=str(r["energy"]),chargePerMinute=str(r["time"]),idlePerMinute=str(r["parking"]),connectionFee=str(r["flat"]),ocpiDurationBands=[[DIMS[k],lo,hi,str(v)] for k,lo,hi,v in bands])
    return [rule("allDay","00:00","24:00",hist,[])]+[rule("timeWindow",fmt(a),fmt(b),{**hist,**g["plain"]},g["bands"]) for (a,b),g in groups.items()]

def fixtures(groups):
    bounds={n for g in groups.values() for _,lo,hi,_ in g["bands"] for n in (lo,hi) if n is not None and n>0}
    durations={900,3600,14400}
    excluded=sorted(b for b in bounds if b+1>MAX)
    for b in bounds:
        if b+1<=MAX:durations.update((max(1,b-1),b,b+1))
    # Clock changes are sampled at each boundary; threshold changes at representative
    # inside/outside times. Avoid a combinatorial product of all long sessions.
    starts={"day":datetime(2026,11,25,11,tzinfo=timezone.utc),"night":datetime(2026,11,25,23,tzinfo=timezone.utc),"spring":datetime(2026,3,29,0,30,tzinfo=timezone.utc),"autumn":datetime(2026,10,25,0,30,tzinfo=timezone.utc)}
    for m in sorted({x for w in groups for x in w}):
        at=datetime(2026,11,25,m//60,m%60,tzinfo=ZONE).astimezone(timezone.utc)
        for delta in (-15,0):starts[f"edge_{m}_{delta}"]=at+timedelta(minutes=delta)
    pairs={(label,3600) for label in starts}|{(label,s) for label in ("day","night") for s in durations}
    # At every window entry exercise the largest reachable threshold as well.
    reachable=[b for b in bounds if b+1<=MAX]
    if reachable:
        b=max(reachable)
        pairs|={(label,b+1) for label in starts if label.startswith("edge_")}
    for label,s in sorted(pairs):
        for mode,c in (("charge",s),("mixed",s//2),("parking",0)):
            yield dict(id=f"{label}_{s}s_{mode}",startAt=starts[label].isoformat(),seconds=s,chargeSeconds=c,parkSeconds=s-c,duration=str(dec(s)/60),charging=str(dec(c)/60),parking=str(dec(s-c)/60),energy="12" if c else "0"),excluded

def segments(groups,f):
    at=datetime.fromisoformat(f["startAt"]);s=f["seconds"]
    # Fixtures start exactly at a UTC minute. Iterate elapsed civil clock
    # minute samples, then coalesce equal windows to match arithmetic segments.
    out=[]
    for i in range(0,s,60):
        local=(at+timedelta(seconds=i)).astimezone(ZONE);m=local.hour*60+local.minute
        w=next((w for w in groups if contains(w,m)),None)
        end=min(s,i+60)
        if out and out[-1][2]==w:out[-1]=(out[-1][0],end,w)
        else:out.append((i,end,w))
    return out

def historical_rates(hist,g,total):
    r={**hist,**g["plain"]} if g else dict(hist)
    for k,lo,hi,v in (g["bands"] if g else []):
        if total>=lo and (hi is None or total<hi):r[k]=v
    return r
def rounded(x):return x.quantize(Q,rounding=ROUND_HALF_UP)
def oracle(base,plain,groups,f,ss):
    hist={**base,**plain};parts={k:Decimal(0) for k in DIMS};c=f["chargeSeconds"];s=f["seconds"];e=dec(f["energy"])
    for a,b,w in ss:
        r=historical_rates(hist,groups.get(w),s)
        ch=max(0,min(c,b)-a);pa=max(0,b-max(a,c))
        amounts=dict(energy=e*dec(ch)/c if c else Decimal(0),time=dec(ch)/60,parking=dec(pa)/60,flat=Decimal(int(a==0)))
        for k,v in amounts.items():parts[k]+=rounded(v*r[k])
    return {**{k:str(v) for k,v in parts.items()},"total":str(sum(parts.values()))}

def envelope(base,plain,groups,f,ss):
    # Conservative agreement diagnostic only: include base, plain, all
    # reachable rates from visited or starting windows, omitted-as-zero in
    # restricted rules. No assumption about billing clock or marginal fees.
    possible={k:{base[k],plain.get(k,base[k])} for k in DIMS}
    for w in {w for _,_,w in ss if w is not None}:
        g=groups[w]
        for k,v in g["plain"].items():possible[k].add(v)
        if g["plain"]:
            for k in set(DIMS)-set(g["plain"]):possible[k].add(Decimal(0))
        for k,lo,hi,v in g["bands"]:
            if lo<=f["seconds"]:possible[k].add(v)
        # Missing band components may be inherited or zeroed; conservative
        # zero alternative only where a reachable restricted band exists.
        active={(lo,hi) for _,lo,hi,_ in g["bands"] if lo<=f["seconds"]}
        for lo,hi in active:
            for k in set(DIMS)-{k for k,l,h,_ in g["bands"] if (l,h)==(lo,hi)}:possible[k].add(Decimal(0))
    qty={"energy":dec(f["energy"]),"time":dec(f["chargeSeconds"])/60,"parking":dec(f["parkSeconds"])/60,"flat":Decimal(1)}
    low={k:rounded(min(v)*qty[k]) for k,v in possible.items()}
    high={k:rounded(max(v)*qty[k]) for k,v in possible.items()}
    return low,high

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_combined_windows" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    a=download(root/"prior",pin["prior"],{"decisions":("g6-window-candidate-offer-decisions.csv.gz",),"cases":("g6-window-candidate-cases.csv.gz",),"report":("g6-window-candidate-report.json",)})
    verify(a["decisions"],pin["decisionsSha256"]);verify(a["cases"],pin["casesSha256"])
    ar=json.loads(a["report"].read_text())
    if ar["codeSha"]!=pin["prior"]["codeSha"] or ar["sourcePin"]!=pin["priorSourcePin"] or ar["identityPairs"]!=24115 or ar["candidatePassed"]!=684 or ar["fixedCases"]!=16 or ar["cumulativeEstimatedOffers"]!=14517 or ar["candidateSha256"]!=pin["candidateSha256"] or sum(r["passed"] for r in ar["regressions"])!=2803:raise ValueError("Prior lineage")
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
        if rr[0]["family"]!="DURATION_BASED+TIME_BASED":continue
        if any(r["g6_calculability"]!="NOT_YET_CERTIFIED" for r in rr):raise ValueError("Prior estimate")
        d=inspect_tariff(raw)
        if any(json.loads(r["normalized_rules"])!=d["normalized_rules"] or json.loads(r["base_rates"])!=d["base_rates"] for r in rr):raise ValueError("Audit lineage")
        decisions[sig]=dict(offers=len(rr),status="COMBINED_STRUCTURE_REVIEW",reason="",excludedThresholdSeconds=[])
        try:base,plain,w=compile_combined(raw)
        except ValueError as e:decisions[sig]["reason"]=str(e);continue
        rules=rules_for(base,plain,w)
        for f,excluded in fixtures(w):
            decisions[sig]["excludedThresholdSeconds"]=excluded
            ss=segments(w,f);expected=oracle(base,plain,w,f,ss);lo,hi=envelope(base,plain,w,f,ss)
            requests.append(dict(signature=sig,fixture=f,rules=rules,expected=expected,lower={k:str(v) for k,v in lo.items()},upper={k:str(v) for k,v in hi.items()}))
    if len(decisions)!=25 or sum(d["offers"] for d in decisions.values())!=4581 or not requests:raise ValueError("Cohort")
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
        out.append({**r,"g6_combined_replay":d.get("status","NOT_IN_COMBINED_PHASE"),"g6_combined_reason":d.get("reason",""),"g6_combined_scenarios":j(d.get("scenarioDecisions",{})) if d else ""})
    if sum(r["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for r in out)!=14517:raise ValueError("Prior estimates")
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-combined-window-cases.csv.gz",cases,list(cases[0]))
    write_csv(dest/"g6-combined-window-offer-decisions.csv.gz",out,list(out[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),combinedOffers=4581,combinedSignatures=25,caseCount=len(cases),passedCases=sum(x["engine_pass"] for x in cases),signatureDecisions=decisions,scenarioDecisions=dict(collections.Counter(x["decision"] for x in cases)),offerDecisions=dict(collections.Counter(r["g6_combined_replay"] for r in out)),guards=result["guards"],cumulativeEstimatedOffers=14517,engineSha256=pin["engineSha256"],candidateSha256=digest(engine),identityChanges=0,pricesPromoted=0,supplierCalls=0,automaticPublication=False,limitations=["Historical whole-session duration selection and elapsed UTC window segmentation, prorated estimates only","Diagnostic conservative rate envelope is not a contractual or invoice bound; no automatic certification","Thresholds exceeding seven-day candidate guard explicitly retained without testing those boundaries; no Production integration"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-combined-window-report.json").write_text(j(report))
    print("G6_FR_COMBINED_WINDOWS "+j({k:v for k,v in report.items() if k not in ("sourcePin","signatureDecisions")}))
if __name__=="__main__":main()
