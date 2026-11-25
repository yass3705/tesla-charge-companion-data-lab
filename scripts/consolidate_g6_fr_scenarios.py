"""G6.4a: consolidate pinned evidence; exact scenario gate, never a ranking tariff."""
import collections,csv,gzip,json,os,pathlib,sys
from decimal import Decimal, InvalidOperation
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import j

EST="ENGINE_ORACLE_PASS_ESTIMATE_ONLY"
REVIEW="NOT_YET_CERTIFIED"
AGREE="CONDITIONAL_ESTIMATE_AGREEMENT"
AMBIG="INCALCULABLE_SEMANTICS"
DATE="DATE_APPLICABILITY_REVIEW"
FAMILY={"simple":"NO_DECLARED_RESTRICTIONS","time":"NO_DECLARED_RESTRICTIONS","free":"NO_DECLARED_RESTRICTIONS","duration":"DURATION_BASED","duration_semantics":"DURATION_BASED","window":"TIME_BASED","combined":"DURATION_BASED+TIME_BASED","mixed":"DURATION_BASED+TIME_BASED"}
def read_csv(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def key(session):
    # All parameters, including date and offsets, retained. No rounding,
    # extrapolation, interpolation or use of a fixture label as evidence.
    if not isinstance(session,dict) or not {"startAt","energy","duration","charging","parking"}<=session.keys():raise ValueError("Incomplete session")
    return j({k:v for k,v in session.items() if k!="id"})
def valid_amount(v):
    try:
        x=Decimal(str(v));return x.is_finite() and x>=0
    except (InvalidOperation,ValueError,TypeError):return False
def gate(record,session):
    if record is None:return "INCALCULABLE_UNTESTED_SESSION"
    try:
        if key(session)!=record["session_key"]:return "INCALCULABLE_UNTESTED_SESSION"
    except (ValueError,TypeError):return "INCALCULABLE_UNTESTED_SESSION"
    if record["decision"]==AGREE and valid_amount(record["estimate_eur"]):return "DIAGNOSTIC_CONDITIONAL_AGREEMENT"
    if record["decision"]=="BASELINE_ESTIMATE_REPLAY_PASS" and valid_amount(record["estimate_eur"]):return "DIAGNOSTIC_BASELINE_REPLAY_PASS"
    return "INCALCULABLE_REVIEW"
def evidence(phase,row,baseline):
    if phase=="window":
        state=row["candidate_decision"];passed=row["candidate_pass"]=="True";engine=json.loads(row["candidate_result"])
    elif phase=="duration_semantics":
        state=row["decision"];passed=True;engine=json.loads(row["historical_engine"])
    else:
        state=row.get("decision","");passed=row.get("engine_pass")=="True";engine=json.loads(row["engine_result"])
    if phase in ("simple","time","free","duration"):
        state="BASELINE_ESTIMATE_REPLAY_PASS" if baseline else "HISTORICAL_REPLAY_ONLY"
    if state not in (AGREE,AMBIG,DATE,"BASELINE_ESTIMATE_REPLAY_PASS","HISTORICAL_REPLAY_ONLY"):raise ValueError("Unexpected decision "+state)
    if not passed:raise ValueError("Replay failure")
    amount=""
    if state in (AGREE,"BASELINE_ESTIMATE_REPLAY_PASS"):
        v=row.get("estimate_eur") if phase=="duration_semantics" else json.loads(row["oracle"])["total"]
        if not valid_amount(v) or engine.get("complete") is not True or engine.get("currency")!="EUR" or not valid_amount(engine.get("total")) or Decimal(str(v))!=Decimal(str(engine["total"])):raise ValueError("Unproved estimate")
        amount=str(v)
    return dict(phase=phase,signature=row["signature"],scenario=row["scenario"],session=row["session"],session_key=key(json.loads(row["session"])),decision=state,estimate_eur=amount,ranking_eligible=False)
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_scenario_consolidation" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","identityChanges")):raise ValueError("Scope")
    phases=["simple","time","free","duration","duration_semantics","window","combined","mixed","date"]
    if [p["phase"] for p in pin["sources"]]!=phases:raise ValueError("Phases")
    verify(pathlib.Path("migration/v9/g6-candidate/pricing-engine.cjs"),pin["candidateSha256"])
    verify(pathlib.Path("migration/v9/g6-reference/pricing-engine.cjs"),pin["engineSha256"])
    ledger=None;cases=[];reports=[]
    for p in pin["sources"]:
        phase=p["phase"];dname=p["prefix"]+"-offer-decisions.csv.gz"
        a=download(root/phase,p["spec"],{"decisions":(dname,),"cases":(p["cases"],),"report":(p["report"],)})
        verify(a["decisions"],p["decisionsSha256"]);verify(a["cases"],p["casesSha256"])
        report=json.loads(a["report"].read_text())
        if report["codeSha"]!=p["spec"]["codeSha"] or report["sourcePin"]!=p["sourcePin"] or report["identityPairs"]!=24115 or report["exportSha256"][dname]!=p["decisionsSha256"] or report["exportSha256"][p["cases"]]!=p["casesSha256"]:raise ValueError("Lineage "+phase)
        rr=read_csv(a["decisions"]);index={(r["national_id"],r["source_id"]):r for r in rr}
        if len(rr)!=24115 or len(index)!=len(rr) or len({r["national_id"] for r in rr})!=len(rr) or len({r["source_id"] for r in rr})!=len(rr):raise ValueError("Identity")
        if ledger is not None:
            if index.keys()!=ledger.keys():raise ValueError("Identity mutation")
            for k,r in index.items():
                old=ledger[k]
                if any(r.get(f)!=v for f,v in old.items() if f!="g6_calculability"):raise ValueError("Prior evidence mutation "+phase)
                if old["g6_calculability"]==EST and r["g6_calculability"]!=EST:raise ValueError("Estimate regression")
        ledger=index
        groups=collections.defaultdict(list)
        for r in rr:groups[r["tariff_signature"]].append(r)
        if len(groups)!=262:raise ValueError("Signatures")
        for sig,group in groups.items():
            if len({(r["raw_price_payload"],r["family"],r["g6_calculability"]) for r in group})!=1 or signature(json.loads(group[0]["raw_price_payload"]))!=sig or any(r["raw_verified"]!="True" for r in group):raise ValueError("Raw lineage")
        phase_cases=read_csv(a["cases"]);seen=set()
        for row in phase_cases:
            sig=row["signature"];g=groups[sig];family=g[0]["family"]
            if (phase=="date" and family not in ("DATE_BASED","DATE_BASED+TIME_BASED")) or (phase!="date" and family!=FAMILY[phase]):raise ValueError("Wrong family")
            k=(sig,row["scenario"])
            if k in seen:raise ValueError("Duplicate scenario")
            seen.add(k)
            e=evidence(phase,row,g[0]["g6_calculability"]==EST)
            e.update(artifact_id=p["spec"]["artifact"],run_id=p["spec"]["run"],offer_count=len(g))
            if gate(e,json.loads(row["session"]))=="INCALCULABLE_UNTESTED_SESSION":raise ValueError("Gate")
            cases.append(e)
        reports.append(dict(phase=phase,artifact=p["spec"]["artifact"],cases=len(phase_cases),decisions=dict(collections.Counter(x["decision"] for x in cases if x["phase"]==phase))))
    rows=list(ledger.values())
    counts=collections.Counter(r["g6_calculability"] for r in rows)
    if counts!={EST:14517,REVIEW:9598}:raise ValueError("Baseline estimate coverage")
    # Each phase is retained; historical-only cases never authorize an estimate.
    covered={e["signature"] for e in cases}
    if covered!={r["tariff_signature"] for r in rows}:raise ValueError("Uncovered signature")
    by=collections.defaultdict(collections.Counter)
    for e in cases:by[e["signature"]][e["decision"]]+=1
    out=[]
    for r in rows:
        sig=r["tariff_signature"]
        out.append({**r,"g64_scenario_evidence":j(dict(by[sig])),"g64_policy":"BASELINE_ESTIMATE_PRESERVED" if r["g6_calculability"]==EST else "DYNAMIC_REVIEW_NO_AUTOMATIC_RANKING","g64_prices_promoted":False})
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-consolidated-offers.csv.gz",out,list(out[0]))
    write_csv(dest/"g6-consolidated-scenarios.csv.gz",cases,list(cases[0]))
    result=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,identityPairs=len(out),signatures=len(covered),baselineEstimations=counts[EST],reviewOffers=counts[REVIEW],cases=len(cases),scenarioDecisions=dict(collections.Counter(x["decision"] for x in cases)),phases=reports,pricesPromoted=0,supplierCalls=0,identityChanges=0,automaticPublication=False,limitations=["Exact archived fixture evidence only; no general live or future tariff applicability","No automatic ranking; arbitrary session evaluator and Production integration remain separate","Four offers have thresholds beyond the seven-day guard"])
    result["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-consolidation-report.json").write_text(j(result))
    print("G6_FR_CONSOLIDATION "+j({k:v for k,v in result.items() if k!="sourcePin"}))
if __name__=="__main__":main()
