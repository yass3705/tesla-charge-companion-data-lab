"""G6.5a: unified diagnostic gate and isolated synthetic ranking; never production."""
import collections,json,os,pathlib,subprocess,sys
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import j,dec,Q
from scripts.evaluate_g6_fr_dynamic import prepare,session,envelope,historical_rules,fixtures,DIMS
from scripts.refine_g6_fr_dynamic import quote,FAMILIES
from scripts.consolidate_g6_fr_scenarios import read_csv,EST,REVIEW

PASS="DIAGNOSTIC_ESTIMATE_AGREEMENT"
def diagnose(prepared,f,family,baseline):
    session(f)
    if family in FAMILIES:
        state,parts,models,errors=quote(prepared,f,family)
        detail=j({"models":models,"errors":errors})
    else:
        state,parts=envelope(prepared,f,family,baseline)
        detail=""
    return state,parts,detail
def engine_agrees(parts,r):
    try:
        return r["complete"] is True and r["currency"]=="EUR" and all(dec(r[k]).is_finite() and dec(r[k])==dec(parts[k]) and dec(r[k])>=0 for k in (*DIMS,"total"))
    except (ValueError,KeyError,TypeError,ArithmeticError):return False
def rank(rows,energy,efficiency=Decimal("0.18"),limit=20):
    """Synthetic France-wide cohort, not a geographic or live TCC search."""
    energy=dec(energy);efficiency=dec(efficiency)
    if not energy.is_finite() or energy<0 or not efficiency.is_finite() or efficiency<=0 or type(limit) is not int or limit<=0:raise ValueError("Ranking inputs")
    eligible=[]
    for r in rows:
        if r["decision"]!=PASS:continue
        try:v=dec(r["estimate_eur"])
        except (ValueError,TypeError,ArithmeticError):raise ValueError("Invalid eligible estimate")
        if not v.is_finite() or v<0:raise ValueError("Invalid eligible estimate")
        eligible.append((v,r["national_id"],r["source_id"],r))
    ordered=sorted(eligible,key=lambda x:x[:3])
    out=[]
    for i,(v,n,s,r) in enumerate(ordered[:limit],1):
        out.append({**r,"rank_cost":i,"estimate_cost_per_km":str((v*efficiency/energy).quantize(Q,rounding=ROUND_HALF_UP)) if energy else "","ranking_simulation_only":True})
    return out,len(eligible)
def load(root,spec,exports,report_sha,report_name):
    a=download(root,spec,{**{k:(k,) for k in exports},"report":(report_name,)})
    for k,v in exports.items():verify(a[k],v)
    verify(a["report"],report_sha)
    r=json.loads(a["report"].read_text())
    if r["codeSha"]!=spec["codeSha"] or r["exportSha256"]!=exports or r["identityPairs"]!=24115 or r["baselineEstimations"]!=14517 or r["reviewOffers"]!=9598 or any(r[k]!=0 for k in ("supplierCalls","identityChanges","pricesPromoted")) or r["automaticPublication"] is not False:raise ValueError("Lineage")
    return a,r
def extra_fixtures():
    for name,start,c,p,e in (
      ("short_partial","2026-11-25T16:42:17Z",829,0,"7.123"),
      ("overnight_partial","2026-11-25T22:48:37Z",1861,599,"20.527"),
      ("spring_transition","2026-03-29T00:49:31Z",3661,733,"32.149"),
      ("parking_only","2026-11-25T19:52:12Z",0,1801,"0"),
      ("threshold_long","2026-11-25T08:01:00Z",7200,3600,"55.5"),
      ("mixed_day","2026-11-25T11:19:13Z",1223,469,"13.425")):
        yield dict(id=name,startAt=start,seconds=c+p,chargeSeconds=c,parkSeconds=p,energy=e,duration=str(dec(c+p)/60),charging=str(dec(c)/60),parking=str(dec(p)/60))
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_unified_ranking_simulation" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","identityChanges")):raise ValueError("Scope")
    a,ar=load(root/"refined",pin["refined"],pin["refinedExports"],pin["refinedReportSha256"],"g6-refined-report.json")
    b,br=load(root/"dynamic",pin["dynamic"],pin["dynamicExports"],pin["dynamicReportSha256"],"g6-dynamic-report.json")
    if ar["targetCases"]!=555 or ar["targetDecisions"]!={PASS:528,"INCALCULABLE_SEMANTICS":20,"MODEL_OR_ENERGY_ALLOCATION_REVIEW":7} or br["newCases"]!=1572:raise ValueError("Prior coverage")
    rows=read_csv(a["g6-refined-offers.csv.gz"]);prior_rows=read_csv(b["g6-dynamic-offers.csv.gz"])
    key=lambda r:(r["national_id"],r["source_id"])
    prior_index={key(r):r for r in prior_rows}
    if len(rows)!=24115 or len(prior_index)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115 or {key(r) for r in rows}!=prior_index.keys():raise ValueError("Identities")
    for r in rows:
        if any(r.get(k)!=v for k,v in prior_index[key(r)].items()):raise ValueError("Historical decision changed")
    if collections.Counter(r["g6_calculability"] for r in rows)!={EST:14517,REVIEW:9598}:raise ValueError("Baseline")
    groups=collections.defaultdict(list)
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262:raise ValueError("Signature count")
    engine=pathlib.Path("migration/v9/g6-candidate/pricing-engine.cjs");verify(engine,pin["candidateSha256"])
    dynamic=read_csv(b["g6-dynamic-new-scenarios.csv.gz"]);refined=read_csv(a["g6-refined-scenarios.csv.gz"])
    old_cases=read_csv(b["g6-dynamic-prior-agreements.csv.gz"])
    if len(dynamic)!=1572 or len(refined)!=1845 or len(old_cases)!=4177:raise ValueError("Historical coverage")
    # The refined gate owns only the three explicitly refined families.
    expected={(r["signature"],r["scenario"]):r for r in dynamic}
    for r in refined:
        if r["cohort"]=="new":expected[r["signature"],r["scenario"]]=r
    if len(expected)!=1572 or sum(r["decision"]==PASS for r in expected.values())!=1350:raise ValueError("Unified expected")
    fxs=list(fixtures())+list(extra_fixtures())
    cases=[];requests=[];indices=[]
    for sig,rr in sorted(groups.items()):
        r=rr[0];raw=json.loads(r["raw_price_payload"]);family=r["family"];baseline=r["g6_calculability"]==EST
        if signature(raw)!=sig or any(x["raw_price_payload"]!=r["raw_price_payload"] or x["family"]!=family or x["raw_verified"]!="True" or x["g6_calculability"]!=r["g6_calculability"] for x in rr):raise ValueError("Raw lineage")
        try:prepared=prepare(raw,family,baseline,sig)
        except (ValueError,KeyError,TypeError,ArithmeticError) as ex:prepared=None;err=str(ex)
        for f in fxs:
            previous=expected.get((sig,f["id"]))
            state="STRUCTURE_REVIEW";parts=None;detail=err if prepared is None else ""
            if prepared is not None:
                try:state,parts,detail=diagnose(prepared,f,family,baseline)
                except (ValueError,KeyError,TypeError,ArithmeticError) as ex:state="SESSION_OR_MODEL_REVIEW";detail=str(ex)
            row=dict(signature=sig,family=family,offer_count=len(rr),baseline=baseline,scenario=f["id"],cohort="regression" if previous else "new",session=j(f),previous=previous["decision"] if previous else "",decision=state,reason=detail,oracle=j(parts) if parts else "",engine_result="",estimate_eur="",publication_eligible=False)
            if parts is not None:
                try:rules=historical_rules(prepared,f,family)
                except (ValueError,KeyError,TypeError,ArithmeticError) as ex:row["decision"]="HISTORICAL_ENGINE_STRUCTURE_REVIEW";row["reason"]=str(ex)
                else:requests.append(dict(signature=sig,fixture=f,rules=rules));indices.append(len(cases))
            cases.append(row)
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_combined_windows_engine.cjs")
    result=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(result["results"])!=len(requests) or len(result["guards"])!=4 or not all(result["guards"].values()):raise ValueError("Engine guards")
    for i,req,r in zip(indices,requests,result["results"]):
        row=cases[i];parts=json.loads(row["oracle"])
        if r["signature"]!=req["signature"] or r["scenario"]!=req["fixture"]["id"]:raise ValueError("Order")
        row["engine_result"]=j(r);good=engine_agrees(parts,r)
        row["decision"]=PASS if good else "ENGINE_OR_ROUNDING_REVIEW"
        if good:row["estimate_eur"]=parts["total"]
    regressions=[]
    for r in cases:
        p=expected.get((r["signature"],r["scenario"]))
        if p and (p["decision"]!=r["decision"] or (p["decision"]==PASS and dec(p["estimate_eur"])!=dec(r["estimate_eur"]))):regressions.append(dict(signature=r["signature"],scenario=r["scenario"],previous=p["decision"],current=r["decision"]))
    if len(cases)!=3144:raise ValueError("Scenario coverage")
    case_index={(r["signature"],r["scenario"]):r for r in cases}
    ranking=[];coverage=[];decisions=[]
    for f in fxs:
        candidates=[]
        for r in rows:
            d=case_index[r["tariff_signature"],f["id"]]
            candidates.append(dict(national_id=r["national_id"],source_id=r["source_id"],signature=r["tariff_signature"],scenario=f["id"],baseline=r["g6_calculability"],decision=d["decision"],estimate_eur=d["estimate_eur"]))
        top,n=rank(candidates,f["energy"])
        if top!=rank(list(reversed(candidates)),f["energy"])[0] or any(r["decision"]!=PASS for r in top) or len(top)!=min(20,n):raise ValueError("Ranking gate or deterministic order")
        ranking.extend(top);decisions.extend(candidates)
        status=collections.Counter((r["baseline"],r["decision"]) for r in candidates)
        coverage.append(dict(scenario=f["id"],eligible=n,baselineEligible=status[EST,PASS],reviewEligible=status[REVIEW,PASS],excluded=len(candidates)-n,reviewExcluded=9598-status[REVIEW,PASS],costPerKmDefined=dec(f["energy"])>0))
    dest=root/"results";dest.mkdir()
    for name,data in (("g6-unified-signature-scenarios.csv.gz",cases),("g6-unified-offer-scenarios.csv.gz",decisions),("g6-unified-top20-simulation.csv.gz",ranking)):
        write_csv(dest/name,data,list(data[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,identityPairs=len(rows),signatures=len(groups),baselineEstimations=14517,reviewOffers=9598,regressionCases=1572,newCases=1572,caseCount=len(cases),engineComparisons=len(requests),regressionDifferences=regressions,priorHistoricalAgreementsRetained=len(old_cases),historicalResidualCases=27,rankingCoverage=coverage,scenarioDecisions={c:dict(collections.Counter(r["decision"] for r in cases if r["cohort"]==c)) for c in ("regression","new")},guards=result["guards"],pricesPromoted=0,supplierCalls=0,identityChanges=0,automaticPublication=False,limitations=["Synthetic nationwide ranking, no geography, power filtering, availability or other channels","Cost/km uses illustrative 0.18 kWh/km; undefined for zero energy; cost/km ordering same for fixed positive energy","Historical archived estimates only; commercial applicability and runtime integration remain unproven","No prices promoted; regression differences block further integration"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-unified-report.json").write_text(j(report))
    print("G6_FR_UNIFIED "+j({k:v for k,v in report.items() if k!="sourcePin"}))
    if regressions:raise ValueError("Unified regression differences: "+str(len(regressions)))
if __name__=="__main__":main()
