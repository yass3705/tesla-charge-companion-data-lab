"""G6.4c: phase-aware independent diagnostic for clock and calendar offers.
Only candidate-confirmed agreements; no current price or invoice certification.
"""
import collections,itertools,json,os,pathlib,subprocess,sys
from datetime import timedelta
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import j,Q,dec
from scripts.replay_g6_fr_time_windows import ZONE,contains
from scripts.replay_g6_fr_date_windows import snapshot,active
from scripts.evaluate_g6_fr_dynamic import session,prepare,historical_rules,DIMS
from scripts.consolidate_g6_fr_scenarios import read_csv,EST,REVIEW

FAMILIES={"TIME_BASED","DATE_BASED","DATE_BASED+TIME_BASED"}
def intervals(at,s,c):
    """Exact elapsed seconds split at civil minute and charge/parking boundaries."""
    i=0
    while i<s:
        t=at+timedelta(seconds=i)
        b=min(s,i+60-t.second,c if i<c else s)
        local=t.astimezone(ZONE)
        yield i,b,local.date(),local.hour*60+local.minute
        i=b
def quote(prepared,f,family):
    at,s,c,p,e=session(f)
    spans=list(intervals(at,s,c));day0,m0=spans[0][2:]
    _,_,compiled=prepared
    models={};errors={}
    if family=="TIME_BASED":
        base,hist,_,windows=compiled
        variants=list(itertools.product(("base","historical"),(False,True),(False,True)))
        def pick(v,day,m):
            seed,replace,start=v
            r=base if seed=="base" else hist
            w=next((r0 for w0,r0 in windows.items() if contains(w0,m0 if start else m)),None)
            return r if w is None else {**({k:Decimal(0) for k in DIMS} if replace else r),**w}
    else:
        base,rules=compiled
        if any(not any(active(r,d) for r in rules if r[0] is not None or r[1] is not None) for d in {x[2] for x in spans}):
            return "DATE_APPLICABILITY_REVIEW",None,{},{}
        variants=list(itertools.product(("snapshot","dynamic"),(False,True),(False,True),(False,True)))
        cache={}
        def pick(v,day,m):
            mode,inclusive,replace,start=v
            d=day0 if mode=="snapshot" else day
            if (d,inclusive) not in cache:cache[d,inclusive]=snapshot(base,rules,d,inclusive)
            hist,windows=cache[d,inclusive]
            w=next((r0 for w0,r0 in windows.items() if contains(w0,m0 if start else m)),None)
            return hist if w is None else {**({k:Decimal(0) for k in DIMS} if replace else hist),**w}
    for v in variants:
        name=j(v)
        try:
            parts={k:Decimal(0) for k in DIMS};energy_rates=set()
            for a,b,day,m in spans:
                r=pick(v,day,m)
                if a==0:parts["flat"]=r["flat"]
                dt=dec(b-a)/60
                if a<c:
                    parts["time"]+=dt*r["time"]
                    if e:energy_rates.add(r["energy"])
                else:parts["parking"]+=dt*r["parking"]
            # No uniform energy-distribution assumption for dynamic inputs.
            if len(energy_rates)>1:raise ValueError("Energy allocation across variable rates unproven")
            parts["energy"]=e*next(iter(energy_rates),Decimal(0))
            parts={k:x.quantize(Q,rounding=ROUND_HALF_UP) for k,x in parts.items()}
            models[name]={**{k:str(x) for k,x in parts.items()},"total":str(sum(parts.values()))}
        except (ValueError,KeyError,TypeError,ArithmeticError) as ex:errors[name]=str(ex)
    if errors:return "MODEL_OR_ENERGY_ALLOCATION_REVIEW",None,models,errors
    if len({j(x) for x in models.values()})!=1:return "INCALCULABLE_SEMANTICS",None,models,errors
    return "MODEL_AGREEMENT",next(iter(models.values())),models,errors
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_phase_aware_refinement" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","identityChanges")):raise ValueError("Scope")
    files={"offers":"g6-dynamic-offers.csv.gz","new":"g6-dynamic-new-scenarios.csv.gz","prior":"g6-dynamic-prior-agreements.csv.gz","report":"g6-dynamic-report.json"}
    a=download(root/"prior",pin["prior"],{k:(v,) for k,v in files.items()})
    for k,v in files.items():verify(a[k],pin["reportSha256"] if k=="report" else pin["exports"][v])
    ar=json.loads(a["report"].read_text())
    if ar["codeSha"]!=pin["prior"]["codeSha"] or ar["identityPairs"]!=24115 or ar["baselineEstimations"]!=14517 or ar["reviewOffers"]!=9598 or ar["newCases"]!=1572 or ar["exportSha256"]!=pin["exports"] or ar["pricesPromoted"]!=0:raise ValueError("Lineage")
    engine=pathlib.Path("migration/v9/g6-candidate/pricing-engine.cjs");verify(engine,pin["candidateSha256"])
    rows=read_csv(a["offers"]);old=read_csv(a["prior"]);new=read_csv(a["new"]);groups=collections.defaultdict(list)
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=len(rows) or len({r["source_id"] for r in rows})!=len(rows) or len(old)!=4177 or len(new)!=1572:raise ValueError("Coverage")
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262 or collections.Counter(r["g6_calculability"] for r in rows)!={EST:14517,REVIEW:9598}:raise ValueError("Inventory")
    target=[r for r in old if r["g64b_diagnostic"]!="AGREEMENT_REPRODUCED"]
    if len(target)!=555 or len({r["signature"] for r in target})!=20 or collections.Counter(r["phase"] for r in target)!={"date":428,"window":127}:raise ValueError("Target")
    prepared={}
    for sig,rr in groups.items():
        r=rr[0];raw=json.loads(r["raw_price_payload"])
        if signature(raw)!=sig or any(x["raw_price_payload"]!=r["raw_price_payload"] or x["family"]!=r["family"] or x["raw_verified"]!="True" or x["g6_calculability"]!=r["g6_calculability"] for x in rr):raise ValueError("Raw lineage")
        if r["family"] in FAMILIES:prepared[sig]=prepare(raw,r["family"],r["g6_calculability"]==EST,sig)
    cases=[];requests=[];indices=[]
    for cohort,source in (("prior",old),("new",new)):
        for r in source:
            sig=r["signature"];family=groups[sig][0]["family"]
            if family not in FAMILIES:continue
            prev=r["g64b_diagnostic"] if cohort=="prior" else r["decision"]
            state,parts,models,errors=quote(prepared[sig],json.loads(r["session"]),family)
            row=dict(cohort=cohort,signature=sig,family=family,phase=r.get("phase","new"),scenario=r["scenario"],session=r["session"],offer_count=len(groups[sig]),previous=prev,previous_estimate=r.get("estimate_eur",""),decision=state,oracle=j(parts) if parts else "",models=j(models),errors=j(errors),engine_result="",estimate_eur="",ranking_eligible=False)
            if parts is not None:
                try:rules=historical_rules(prepared[sig],json.loads(r["session"]),family)
                except (ValueError,KeyError,TypeError,ArithmeticError):row["decision"]="HISTORICAL_ENGINE_STRUCTURE_REVIEW"
                else:
                    requests.append(dict(signature=sig,fixture=json.loads(r["session"]),rules=rules));indices.append(len(cases))
            cases.append(row)
    if not requests:raise ValueError("No comparisons")
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_combined_windows_engine.cjs")
    result=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(result["results"])!=len(requests) or len(result["guards"])!=4 or not all(result["guards"].values()):raise ValueError("Guards")
    for i,req,r in zip(indices,requests,result["results"]):
        row=cases[i];parts=json.loads(row["oracle"])
        if r["signature"]!=req["signature"] or r["scenario"]!=req["fixture"]["id"]:raise ValueError("Order")
        row["engine_result"]=j(r)
        try:good=r["complete"] is True and r["currency"]=="EUR" and all(dec(r[k])==dec(parts[k]) for k in (*DIMS,"total"))
        except (ValueError,TypeError,ArithmeticError):good=False
        if row["previous_estimate"] and dec(row["previous_estimate"])!=dec(parts["total"]):good=False
        row["decision"]="DIAGNOSTIC_ESTIMATE_AGREEMENT" if good else "ENGINE_OR_PRIOR_AMOUNT_REVIEW"
        if good:row["estimate_eur"]=parts["total"]
    targeted=[r for r in cases if r["cohort"]=="prior" and r["previous"]=="INCALCULABLE_SEMANTICS"]
    if len(targeted)!=555:raise ValueError("Target replay")
    transitions=collections.Counter((r["cohort"],r["previous"],r["decision"]) for r in cases)
    # Preserve previous new/prior decisions; these columns only add diagnostic evidence.
    by=collections.defaultdict(collections.Counter)
    for r in cases:
        if r["cohort"]=="new":by[r["signature"]][r["decision"]]+=1
    out=[{**r,"g64c_refined_new_scenarios":j(dict(by[r["tariff_signature"]])),"g64c_prices_promoted":False} for r in rows]
    if len(out)!=24115 or sum(r["g6_calculability"]==EST for r in out)!=14517:raise ValueError("Preservation")
    dest=root/"results";dest.mkdir()
    for name,data in (("g6-refined-offers.csv.gz",out),("g6-refined-scenarios.csv.gz",cases),("g6-refined-target.csv.gz",targeted)):
        write_csv(dest/name,data,list(data[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,identityPairs=len(out),baselineEstimations=14517,reviewOffers=9598,signatures=len(prepared),caseCount=len(cases),engineComparisons=len(requests),targetCases=len(targeted),targetDecisions=dict(collections.Counter(r["decision"] for r in targeted)),targetByFamily={f:dict(collections.Counter(r["decision"] for r in targeted if r["family"]==f)) for f in sorted(FAMILIES)},transitions=[dict(cohort=c,previous=p,decision=d,count=n) for (c,p,d),n in sorted(transitions.items())],guards=result["guards"],pricesPromoted=0,identityChanges=0,supplierCalls=0,automaticPublication=False,limitations=["Only clock/date families refined; prior decisions retained","Calendar gaps, conflicting dates, unknown energy distribution, engine or historical estimate differences fail closed","Models are diagnostic, not contractual or live applicability proof"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-refined-report.json").write_text(j(report))
    print("G6_FR_REFINED "+j({k:v for k,v in report.items() if k!="sourcePin"}))
if __name__=="__main__":main()
