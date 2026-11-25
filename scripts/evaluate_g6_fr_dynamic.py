"""G6.4b: conservative session-specific diagnostic; never a ranking tariff.
The rate envelope is deliberately wider than historical billing models.
Unknown components, uncertain dates and engine disagreement fail closed.
"""
import collections,json,os,pathlib,subprocess,sys
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP,InvalidOperation
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import j,Q,dec
from scripts.replay_g6_fr_time_windows import ZONE,minute,contains,compile_windows,rules_for as window_rules
from scripts.replay_g6_fr_duration import compile_duration,DIMS as DIM_IDS
from scripts.replay_g6_fr_combined_windows import compile_combined,rules_for as combined_rules
from scripts.replay_g6_fr_combined_mixed import simplify
from scripts.replay_g6_fr_date_windows import parse,snapshot,engine_rules
from scripts.consolidate_g6_fr_scenarios import read_csv,EST,REVIEW

DIMS=("energy","time","parking","flat")
MAX=7*86400
MIXED="5831d10403740c9e5e715fa151991d63588f28cd7e71fe0678e43c82e5936464"
def amount(v):
    x=dec(v)
    if not x.is_finite() or x<0:raise ValueError("Invalid amount")
    return x
def session(f):
    at=datetime.fromisoformat(f["startAt"])
    if at.tzinfo is None or at.utcoffset() is None:raise ValueError("Missing time offset")
    at=at.astimezone(timezone.utc)
    if at.microsecond:raise ValueError("Unsupported subsecond start")
    if any(k in f for k in ("seconds","chargeSeconds","parkSeconds")):
        s,c,p=(f[k] for k in ("seconds","chargeSeconds","parkSeconds"))
        if any(type(v) is not int for v in (s,c,p)):raise ValueError("Invalid seconds")
        # Minutes are redundant in historical exports; compare to their exact seconds.
        for k,v in (("duration",s),("charging",c),("parking",p)):
            if k in f and abs(amount(f[k])*60-v)>Decimal("0.000000001"):raise ValueError("Inconsistent minutes")
    else:
        seconds=[amount(f[k])*60 for k in ("duration","charging","parking")]
        if any(v!=v.to_integral_value() for v in seconds):raise ValueError("Unsupported subsecond duration")
        s,c,p=map(int,seconds)
    e=amount(f["energy"])
    if not 0<s<=MAX or min(c,p)<0 or c+p!=s or (not c and e):raise ValueError("Invalid session")
    return at,s,c,p,e
def samples(at,s):
    # Include every touched civil minute, even for a non-minute-aligned start.
    end=at+timedelta(seconds=s)
    t=at.replace(second=0,microsecond=0)
    while t<end:
        local=t.astimezone(ZONE)
        yield local.date(),local.hour*60+local.minute
        t+=timedelta(minutes=1)
def prepare(raw,family,baseline,sig):
    d=inspect_tariff(raw)
    base={k:amount(d["base_rates"][k]) for k in DIMS}
    if amount(d["base_rates"]["vat"])!=0:raise ValueError("Unsupported VAT")
    # Re-run established structural compiler before applying any new gate.
    if family=="DURATION_BASED":compiled=compile_duration(raw)
    elif family=="TIME_BASED":compiled=compile_windows(raw)
    elif family=="DURATION_BASED+TIME_BASED":
        compiled=simplify(raw)[:3] if sig==MIXED else compile_combined(raw)
    elif family in ("DATE_BASED","DATE_BASED+TIME_BASED"):compiled=parse(raw)
    elif family=="NO_DECLARED_RESTRICTIONS" and baseline:compiled=None
    else:raise ValueError("Unrecognized family")
    rr=[]
    for r in d["normalized_rules"]:
        types=set(r["types"]);cond=r["conditions"]
        expected={v for k,v in (("DATE_BASED","dateRestrictions"),("TIME_BASED","timeRestrictions"),("DURATION_BASED","durationRestrictions")) if k in types}
        if types-{"DATE_BASED","TIME_BASED","DURATION_BASED"} or set(cond)!=expected or set(r["rates"])-set(DIMS):raise ValueError("Unknown rule")
        lo=hi=None;w=None;threshold=0
        if "DATE_BASED" in types:
            b=cond["dateRestrictions"];lo=date.fromisoformat(b["startDate"]) if b["startDate"] else None;hi=date.fromisoformat(b["endDate"]) if b["endDate"] else None
        if "TIME_BASED" in types:
            b=cond["timeRestrictions"];w=(minute(b["startTime"]),minute(b["endTime"]))
        if "DURATION_BASED" in types:threshold=cond["durationRestrictions"]["minDurationSeconds"] or 0
        rr.append((types,lo,hi,w,threshold,{k:amount(v) for k,v in r["rates"].items()}))
    return base,rr,compiled
def envelope(prepared,f,family,baseline):
    at,s,c,p,e=session(f)
    base,rr,compiled=prepared
    clock=set(samples(at,s)) if "TIME_BASED" in family or "DATE_BASED" in family else set()
    days={day for day,m in clock}
    # Calendar eligibility is not commercial proof; gaps under either endpoint
    # convention remain unknown even if the base itself is numeric.
    if "DATE_BASED" in family:
        dated=[r for r in rr if "DATE_BASED" in r[0]]
        if any(not any((lo is None or day>=lo) and (hi is None or day<hi) for _,lo,hi,_,_,_ in dated) for day in days):
            return "DATE_APPLICABILITY_REVIEW",None
    possible={k:{v} for k,v in base.items()}
    for types,lo,hi,w,threshold,rates in rr:
        if threshold>s:continue
        if w is not None or "DATE_BASED" in types:
            # Cross-product deliberately includes start-date snapshot and
            # session date changes; upper endpoint inclusive as alternative.
            if not any((lo is None or day>=lo) and (hi is None or day<=hi) for day in days):continue
            if w is not None and not any(contains(w,m) for day,m in clock):continue
        for k,v in rates.items():possible[k].add(v)
        if types:
            for k in set(DIMS)-set(rates):possible[k].add(Decimal(0))
    qty={"energy":e,"time":dec(c)/60,"parking":dec(p)/60,"flat":Decimal(1)}
    if any(len(possible[k])!=1 and qty[k]!=0 for k in DIMS):return "INCALCULABLE_SEMANTICS",None
    parts={k:(min(possible[k])*qty[k]).quantize(Q,rounding=ROUND_HALF_UP) for k in DIMS}
    return "DIAGNOSTIC_RATE_AGREEMENT",{**{k:str(v) for k,v in parts.items()},"total":str(sum(parts.values()))}
def historical_rules(prepared,f,family):
    base,rr,compiled=prepared
    def all_day(r,bands=()):
        return [dict(scope="allDay",start="00:00",end="24:00",currency="EUR",pricePerKwh=str(r["energy"]),chargePerMinute=str(r["time"]),idlePerMinute=str(r["parking"]),connectionFee=str(r["flat"]),ocpiDurationBands=list(bands))]
    if family=="DURATION_BASED":
        rates,bands,_,_=compiled
        return all_day(rates,[(DIM_IDS[k],lo,hi,str(v)) for k,lo,hi,v in bands])
    if family=="TIME_BASED":
        _,hist,_,w=compiled
        return window_rules(hist,w)
    if family=="DURATION_BASED+TIME_BASED":return combined_rules(*compiled)
    if "DATE_BASED" in family:
        at,*_=session(f);h,w=snapshot(*compiled,at.astimezone(ZONE).date())
        return engine_rules(h,w)
    return all_day(base)
def fixtures():
    # New non-archived sessions including partial minutes, energy fractions,
    # different charge/parking split and a civil-date transition.
    for name,start,c,p,e in (
        ("short","2026-11-25T12:07:00Z",433,0,"3.725"),
        ("park","2026-11-25T16:19:00Z",0,1379,"0"),
        ("mixed","2026-11-25T20:53:00Z",1771,761,"17.243"),
        ("midnight","2026-11-25T22:54:00Z",1277,883,"9.781"),
        ("dst","2026-10-25T00:47:00Z",3631,139,"24.256"),
        ("long","2026-11-25T09:13:00Z",14400,7200,"56.5")):
        yield dict(id=name,startAt=start,seconds=c+p,chargeSeconds=c,parkSeconds=p,energy=e,duration=str(dec(c+p)/60),charging=str(dec(c)/60),parking=str(dec(p)/60))
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_dynamic_session_gate" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","identityChanges")):raise ValueError("Scope")
    a=download(root/"prior",pin["prior"],{"offers":("g6-consolidated-offers.csv.gz",),"cases":("g6-consolidated-scenarios.csv.gz",),"report":("g6-consolidation-report.json",)})
    verify(a["offers"],pin["exports"]["g6-consolidated-offers.csv.gz"]);verify(a["cases"],pin["exports"]["g6-consolidated-scenarios.csv.gz"]);verify(a["report"],pin["reportSha256"])
    ar=json.loads(a["report"].read_text())
    if ar["codeSha"]!=pin["prior"]["codeSha"] or ar["exportSha256"]!=pin["exports"] or ar["identityPairs"]!=24115 or ar["baselineEstimations"]!=14517 or ar["reviewOffers"]!=9598 or ar["cases"]!=6703 or ar["pricesPromoted"]!=0:raise ValueError("Prior lineage")
    engine=pathlib.Path("migration/v9/g6-candidate/pricing-engine.cjs");verify(engine,pin["candidateSha256"]);verify(pathlib.Path("migration/v9/g6-reference/pricing-engine.cjs"),pin["engineSha256"])
    rows=read_csv(a["offers"]);old=read_csv(a["cases"]);groups=collections.defaultdict(list)
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=len(rows) or len({r["source_id"] for r in rows})!=len(rows) or len(old)!=6703:raise ValueError("Identity or evidence")
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262 or collections.Counter(r["g6_calculability"] for r in rows)!={EST:14517,REVIEW:9598}:raise ValueError("Inventory")
    cases=[];requests=[];request_indexes=[];prepared_by={}
    for sig,rr in sorted(groups.items()):
        r=rr[0];raw=json.loads(r["raw_price_payload"]);family=r["family"];baseline=r["g6_calculability"]==EST
        if signature(raw)!=sig or any(x["raw_price_payload"]!=r["raw_price_payload"] or x["family"]!=family or x["raw_verified"]!="True" or x["g6_calculability"]!=r["g6_calculability"] for x in rr):raise ValueError("Raw lineage")
        try:prepared=prepare(raw,family,baseline,sig);prepared_by[sig]=prepared
        except (ValueError,KeyError,TypeError,ArithmeticError) as ex:prepared=None;error=str(ex)
        for f in fixtures():
            state="STRUCTURE_REVIEW";parts=None;reason=""
            if prepared is None:reason=error
            else:
                try:state,parts=envelope(prepared,f,family,baseline)
                except (ValueError,KeyError,TypeError,ArithmeticError) as ex:state="SESSION_REVIEW";reason=str(ex)
            row=dict(signature=sig,family=family,offer_count=len(rr),scenario=f["id"],session=j(f),decision=state,reason=reason,oracle=j(parts) if parts else "",engine_result="",estimate_eur="",ranking_eligible=False)
            if parts is not None:
                try:rules=historical_rules(prepared,f,family)
                except (ValueError,KeyError,TypeError,ArithmeticError) as ex:row["decision"]="HISTORICAL_ENGINE_STRUCTURE_REVIEW";row["reason"]=str(ex)
                else:
                    requests.append(dict(signature=sig,fixture=f,rules=rules));request_indexes.append(len(cases))
            cases.append(row)
    if not requests:raise ValueError("No engine comparisons")
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_combined_windows_engine.cjs")
    result=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(result["results"])!=len(requests) or len(result["guards"])!=4 or not all(result["guards"].values()):raise ValueError("Engine guards")
    for i,req,r in zip(request_indexes,requests,result["results"]):
        row=cases[i];parts=json.loads(row["oracle"])
        if r["signature"]!=req["signature"] or r["scenario"]!=req["fixture"]["id"]:raise ValueError("Order")
        row["engine_result"]=j(r)
        try:good=r["complete"] is True and r["currency"]=="EUR" and all(dec(r[k])==dec(parts[k]) for k in (*DIMS,"total"))
        except (ValueError,TypeError,ArithmeticError):good=False
        row["decision"]="DIAGNOSTIC_ESTIMATE_AGREEMENT" if good else "ENGINE_OR_ROUNDING_REVIEW"
        if good:row["estimate_eur"]=parts["total"]
    # Retain the prior cases byte-for-byte as evidence; compare independent
    # envelope results on prior accepted scenarios without overriding them.
    regression=collections.Counter();historical=[]
    for r in old:
        if r["decision"] not in ("BASELINE_ESTIMATE_REPLAY_PASS","CONDITIONAL_ESTIMATE_AGREEMENT"):continue
        sig=r["signature"];group=groups[sig][0];prepared=prepared_by.get(sig)
        state="STRUCTURE_REVIEW";parts=None
        if prepared is not None:
            try:state,parts=envelope(prepared,json.loads(r["session"]),group["family"],group["g6_calculability"]==EST)
            except (ValueError,KeyError,TypeError,ArithmeticError):state="SESSION_REVIEW"
        if parts is not None:state="AGREEMENT_REPRODUCED" if dec(parts["total"])==dec(r["estimate_eur"]) else "AMOUNT_REVIEW"
        regression[(r["decision"],state)]+=1
        historical.append({**r,"g64b_diagnostic":state,"g64b_amount":parts["total"] if parts else ""})
    by=collections.defaultdict(collections.Counter)
    for r in cases:by[r["signature"]][r["decision"]]+=1
    out=[{**r,"g64b_diagnostic_scenarios":j(dict(by[r["tariff_signature"]])),"g64b_prices_promoted":False} for r in rows]
    if len(cases)!=len(groups)*len(list(fixtures())) or len(out)!=24115 or sum(r["g6_calculability"]==EST for r in out)!=14517:raise ValueError("Output coverage")
    dest=root/"results";dest.mkdir()
    for name,data in (("g6-dynamic-offers.csv.gz",out),("g6-dynamic-new-scenarios.csv.gz",cases),("g6-dynamic-prior-agreements.csv.gz",historical)):
        write_csv(dest/name,data,list(data[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,identityPairs=len(out),signatures=len(groups),baselineEstimations=14517,reviewOffers=9598,newCases=len(cases),engineComparisons=len(requests),scenarioDecisions=dict(collections.Counter(r["decision"] for r in cases)),priorAgreementChecks={a:{b:n for (x,b),n in regression.items() if x==a} for a in {x for x,b in regression}},guards=result["guards"],pricesPromoted=0,supplierCalls=0,identityChanges=0,automaticPublication=False,limitations=["Diagnostic only; no supplier invoice or current date applicability proof","Conservative component envelope can reject previously agreed scenarios; prior decisions retained unchanged","Candidate engine compared only on envelope-convergent scenarios; exact component mismatch stays in review","Four thresholds above seven days remain outside tested scope"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-dynamic-report.json").write_text(j(report))
    print("G6_FR_DYNAMIC "+j({k:v for k,v in report.items() if k!="sourcePin"}))
if __name__=="__main__":main()
