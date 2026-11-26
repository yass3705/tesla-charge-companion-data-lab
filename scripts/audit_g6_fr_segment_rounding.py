"""G6.5b: independently reproduce segment rounding, retain both estimates.
No tolerance-based acceptance and no change to candidate engine or source data.
"""
import collections,json,os,pathlib,subprocess,sys
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import digest,verify,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import j,dec,Q
from scripts.evaluate_g6_fr_dynamic import prepare,session,historical_rules,DIMS
from scripts.refine_g6_fr_dynamic import intervals,FAMILIES
from scripts.consolidate_g6_fr_scenarios import read_csv,EST,REVIEW
from scripts.unify_g6_fr_dynamic import load,diagnose,engine_agrees,rank,PASS

CENTS=Decimal("0.01")
ROUNDING="SEGMENT_ROUNDING_EXPLAINED"
def q(x):return x.quantize(Q,rounding=ROUND_HALF_UP)
def clock(x):
    h,m=map(int,x.split(":"));return h*60+m
def select(rules,m):
    windows=[]
    for i,r in enumerate(rules):
        if r["scope"]=="allDay":continue
        if r["scope"]!="timeWindow":raise ValueError("Unsupported rule scope")
        a,b=clock(r["start"]),clock(r["end"])
        if (a<=m<b if a<b else m>=a or m<b):windows.append(i)
    if len(windows)>1:raise ValueError("Overlapping windows")
    if windows:return windows[0]
    all_day=[i for i,r in enumerate(rules) if r["scope"]=="allDay"]
    if len(all_day)!=1:raise ValueError("Missing or ambiguous baseline")
    return all_day[0]
def segment_oracle(rules,f):
    """Decimal independent UTC segmentation at rule changes (not phase changes)."""
    at,s,c,p,e=session(f)
    fields={"energy":"pricePerKwh","time":"chargePerMinute","parking":"idlePerMinute","flat":"connectionFee"}
    allowed={"scope","start","end","currency",*fields.values()}
    if any(set(r)-allowed or r.get("currency","EUR")!="EUR" for r in rules):raise ValueError("Unsupported rule dimensions")
    spans=[]
    for a,b,day,m in intervals(at,s,c):
        index=select(rules,m)
        if spans and spans[-1][2]==index:spans[-1]=(spans[-1][0],b,index)
        else:spans.append((a,b,index))
    parts={k:Decimal(0) for k in DIMS};details=[]
    for a,b,i in spans:
        r=rules[i];rates={k:dec(r[v]) for k,v in fields.items()}
        ch=max(0,min(c,b)-a);pa=max(0,b-max(a,c))
        qty={"energy":e*dec(ch)/c if c else Decimal(0),"time":dec(ch)/60,"parking":dec(pa)/60,"flat":Decimal(int(a==0))}
        segment={k:q(qty[k]*rates[k]) for k in DIMS}
        for k,v in segment.items():parts[k]+=v
        details.append(dict(startSecond=a,endSecond=b,ruleIndex=i,chargeSeconds=ch,parkingSeconds=pa,components={k:str(v) for k,v in segment.items()}))
    return {**{k:str(v) for k,v in parts.items()},"total":str(sum(parts.values()))},details
def explain(canonical,segmented,engine):
    if not engine_agrees(segmented,engine):return False
    # Exact segment arithmetic plus equal displayed cents, never epsilon.
    return all(dec(canonical[k]).quantize(CENTS,rounding=ROUND_HALF_UP)==dec(segmented[k]).quantize(CENTS,rounding=ROUND_HALF_UP) for k in (*DIMS,"total"))
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_segment_rounding_audit" or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    a,ar=load(root/"unified",pin["unified"],pin["unifiedExports"],pin["unifiedReportSha256"],"g6-unified-report.json")
    b,br=load(root/"refined",pin["refined"],pin["refinedExports"],pin["refinedReportSha256"],"g6-refined-report.json")
    if ar["caseCount"]!=3144 or ar["regressionDifferences"] or ar["engineComparisons"]!=2706:raise ValueError("Prior run")
    offers=read_csv(b["g6-refined-offers.csv.gz"]);rows=read_csv(a["g6-unified-signature-scenarios.csv.gz"]);old_offer=read_csv(a["g6-unified-offer-scenarios.csv.gz"]);old_rank=read_csv(a["g6-unified-top20-simulation.csv.gz"])
    if len(offers)!=24115 or len({r["national_id"] for r in offers})!=24115 or len({r["source_id"] for r in offers})!=24115 or len(rows)!=3144 or len(old_offer)!=24115*12 or len(old_rank)!=240 or collections.Counter(r["g6_calculability"] for r in offers)!={EST:14517,REVIEW:9598}:raise ValueError("Coverage")
    groups=collections.defaultdict(list)
    for r in offers:groups[r["tariff_signature"]].append(r)
    prepared={}
    for sig,rr in groups.items():
        r=rr[0];raw=json.loads(r["raw_price_payload"])
        if signature(raw)!=sig or any(x["raw_verified"]!="True" or x["raw_price_payload"]!=r["raw_price_payload"] or x["family"]!=r["family"] or x["g6_calculability"]!=r["g6_calculability"] for x in rr):raise ValueError("Raw lineage")
        prepared[sig]=prepare(raw,r["family"],r["g6_calculability"]==EST,sig)
    if len(prepared)!=262:raise ValueError("Signatures")
    targets=[r for r in rows if r["decision"]=="ENGINE_OR_ROUNDING_REVIEW"]
    if len(targets)!=5 or sum(int(r["offer_count"]) for r in targets)!=135 or {r["scenario"] for r in targets}!={"overnight_partial"}:raise ValueError("Target")
    requests=[];indices=[]
    for i,r in enumerate(rows):
        if not r["engine_result"]:continue
        f=json.loads(r["session"]);sig=r["signature"];p=prepared[sig]
        state,parts,detail=diagnose(p,f,r["family"],r["baseline"]=="True")
        if parts is None or parts!=json.loads(r["oracle"]):raise ValueError("Canonical oracle regression")
        requests.append(dict(signature=sig,fixture=f,rules=historical_rules(p,f,r["family"])));indices.append(i)
    engine=pathlib.Path("migration/v9/g6-candidate/pricing-engine.cjs");verify(engine,pin["candidateSha256"])
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_combined_windows_engine.cjs")
    res=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(requests)!=2706 or len(res["results"])!=2706 or len(res["guards"])!=4 or not all(res["guards"].values()):raise ValueError("Engine guards")
    rerun={};details=[]
    for i,req,r in zip(indices,requests,res["results"]):
        old=rows[i]
        if r!=json.loads(old["engine_result"]):raise ValueError("Candidate regression")
        if old["decision"]==PASS and not engine_agrees(json.loads(old["oracle"]),r):raise ValueError("Prior agreement regression")
        if old["decision"]!="ENGINE_OR_ROUNDING_REVIEW":continue
        if old["family"] not in FAMILIES:raise ValueError("Unsupported family")
        canonical=json.loads(old["oracle"])
        segmented,segments=segment_oracle(req["rules"],req["fixture"])
        good=explain(canonical,segmented,r)
        detail=dict(signature=old["signature"],scenario=old["scenario"],offer_count=old["offer_count"],decision=ROUNDING if good else "UNRESOLVED_ENGINE_REVIEW",canonical=j(canonical),segmented=j(segmented),engine=j(r),segments=j(segments),delta_eur=str(dec(segmented["total"])-dec(canonical["total"])),publication_eligible=False)
        details.append(detail)
        if good:rerun[old["signature"],old["scenario"]]=segmented["total"]
    # Keep original decisions; explicit diagnostic eligibility only for the
    # isolated ranking. All non-target amounts and identities unchanged.
    fixed=[{**r,"g65b_decision":ROUNDING if (r["signature"],r["scenario"]) in rerun else r["decision"],"g65b_estimate_eur":rerun.get((r["signature"],r["scenario"]),r["estimate_eur"]),"publication_eligible":False} for r in rows]
    by={(r["signature"],r["scenario"]):r for r in fixed}
    out=[];rankings=[];coverage=[]
    for scenario in sorted({r["scenario"] for r in fixed}):
        candidates=[]
        for r in old_offer:
            if r["scenario"]!=scenario:continue
            d=by[r["signature"],scenario];k=(r["signature"],scenario)
            if r["decision"]!=d["decision"] or r["estimate_eur"]!=d["estimate_eur"]:raise ValueError("Original offer evidence")
            x={**r,"g65b_decision":d["g65b_decision"],"g65b_estimate_eur":d["g65b_estimate_eur"]}
            out.append(x)
            candidates.append({**r,"decision":PASS if k in rerun else r["decision"],"estimate_eur":d["g65b_estimate_eur"]})
        if len(candidates)!=24115:raise ValueError("Scenario inventory")
        f=json.loads(next(r["session"] for r in fixed if r["scenario"]==scenario))
        top,n=rank(candidates,f["energy"])
        if top!=rank(list(reversed(candidates)),f["energy"])[0]:raise ValueError("Ranking order")
        rankings.extend(top);coverage.append(dict(scenario=scenario,eligible=n,reviewEligible=sum(r["baseline"]==REVIEW and r["decision"]==PASS for r in candidates)))
    dest=root/"results";dest.mkdir()
    for name,data in (("g6-rounding-targets.csv.gz",details),("g6-rounding-signature-scenarios.csv.gz",fixed),("g6-rounding-offer-scenarios.csv.gz",out),("g6-rounding-top20-simulation.csv.gz",rankings)):
        write_csv(dest/name,data,list(data[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,identityPairs=len(offers),signatures=len(groups),baselineEstimations=14517,reviewOffers=9598,targetCases=len(targets),explainedCases=len(rerun),explainedOffers=sum(int(r["offer_count"]) for r in details if r["decision"]==ROUNDING),candidateReplayed=len(requests),priorAgreementRegressions=0,rankingCoverage=coverage,guards=res["guards"],identityChanges=0,pricesPromoted=0,supplierCalls=0,automaticPublication=False,limitations=["Exact segmented versus whole-component rounding diagnostic, not invoice proof","Original decisions retained; explained cases added only to isolated ranking","No geography, other channels or runtime integration"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-rounding-report.json").write_text(j(report))
    print("G6_FR_ROUNDING "+j({k:v for k,v in report.items() if k!="sourcePin"}))
    if len(rerun)!=5:raise ValueError("Unresolved rounding targets")
if __name__=="__main__":main()
