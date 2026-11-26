"""G6.6b-5b: clock planner extension and regression replay."""
import collections,gzip,hashlib,json,os,pathlib,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.unify_g6_fr_dynamic import load,PASS
from scripts.g66b3_quote_gate import QuoteGate
from scripts.g66b5a_planner_gate import PlannerGate,PROOF,planner_session
from scripts.g66b5b_clock_gate import ClockPlannerGate
from scripts.audit_g6_fr_segment_rounding import ROUNDING
from scripts.replay_g6_fr_simple import j
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b5b_clock_planner" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    a=download(root/"alignment",pin["alignment"],{**{k:(k,) for k in pin["alignmentExports"]},"report":("g66b2-report.json",)})
    for k,v in pin["alignmentExports"].items():verify(a[k],v)
    verify(a["report"],pin["alignmentReportSha256"]);ar=json.loads(a["report"].read_text())
    crosswalk=gzjson(a["g66b2-november-crosswalk.json.gz"]);canonical=gzjson(a["g66b2-national-active-canonical.json.gz"])
    if hashlib.sha256((json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()).hexdigest()!=ar["nationalCanonicalSha256"]:raise ValueError("Canonical SHA")
    g=download(root/"gate",pin["gate"],{"report":("g66b3-report.json",)})
    verify(g["report"],pin["gateReportSha256"]);gr=json.loads(g["report"].read_text())
    if gr["codeSha"]!=pin["gate"]["codeSha"] or gr["priorRegressions"] or gr["runtimeActivated"] or gr["published"]:raise ValueError("Gate lineage")
    previous=download(root/"runtime",pin["runtime"],{**{k:(k,) for k in pin["runtimeExports"]},"report":("g66b4-report.json",)})
    for k,v in pin["runtimeExports"].items():verify(previous[k],v)
    verify(previous["report"],pin["runtimeReportSha256"]);pr=json.loads(previous["report"].read_text())
    if pr["codeSha"]!=pin["runtime"]["codeSha"] or pr["runtime"]["checks"]!=48204 or pr["published"] or pr["runtimeActivated"] or pr["pricesPromoted"]:raise ValueError("Runtime proof")
    r,rr=load(root/"refined",pin["refined"],pin["refinedExports"],pin["refinedReportSha256"],"g6-refined-report.json")
    offers=read_csv(r["g6-refined-offers.csv.gz"])
    legacy=QuoteGate(offers,crosswalk,canonical,pin["candidateSha256"],gr["lineage"])
    old_requests=gzjson(previous["g66b4-requests.json.gz"]);old_responses=gzjson(previous["g66b4-responses.json.gz"])
    replay,n=legacy.quote(old_requests)
    if len(replay)!=48204 or len(old_responses)!=len(replay) or any(row["request"]!=req or row["response"]!=res for row,req,res in zip(old_responses,old_requests,replay)):raise ValueError("Legacy quote regression")
    del old_requests,old_responses,replay
    lineage={**gr["lineage"],"codeSha":os.environ.get("GITHUB_SHA"),"legacyGateCodeSha":gr["lineage"]["codeSha"],"protocol":"planner-v1"}
    prior=download(root/"planner",pin["planner"],{**{k:(k,) for k in pin["plannerExports"]},"report":("g66b5a-report.json",)})
    for k,v in pin["plannerExports"].items():verify(prior[k],v)
    verify(prior["report"],pin["plannerReportSha256"]);pa=json.loads(prior["report"].read_text())
    if pa["codeSha"]!=pin["planner"]["codeSha"] or pa["runtime"]["checks"]!=2316 or pa["legacyRegressions"] or pa["published"] or pa["pricesPromoted"]:raise ValueError("Prior planner lineage")
    previous_requests=gzjson(prior["g66b5a-requests.json.gz"]);previous_responses=gzjson(prior["g66b5a-responses.json.gz"])
    old,n=PlannerGate(legacy,pa["lineage"]).quote(previous_requests)
    if len(old)!=2316 or len(previous_responses)!=len(old) or any(row["request"]!=req or row["response"]!=res for row,req,res in zip(previous_responses,previous_requests,old)):raise ValueError("Planner legacy regression")
    gate=ClockPlannerGate(legacy,lineage)
    extended,n=gate.quote(previous_requests);transitions=collections.Counter()
    for before,after in zip(old,extended):
        transitions[before["decision"],after["decision"]]+=1
        if before["decision"]!="PLANNER_CLOCK_OR_CALENDAR_REVIEW":
            if {k:v for k,v in before.items() if k!="lineage"}!={k:v for k,v in after.items() if k!="lineage"}:raise ValueError("Prior non-clock decision changed")
        if before["estimateEur"] is not None and before["estimateEur"]!=after["estimateEur"]:raise ValueError("Prior estimate changed")
    del old,extended,previous_requests,previous_responses
    inv=collections.Counter();sig_inv=collections.Counter();bound_inv=collections.Counter();details=[]
    for sig,proof in sorted(gate.evidence.items()):sig_inv[proof]+=1
    for r in offers:inv[gate.evidence[r["tariff_signature"]]]+=1
    for r in legacy.bound.values():bound_inv[gate.evidence[r["tariff_signature"]]]+=1
    if sum(sig_inv.values())!=262 or sum(inv.values())!=24115 or sum(bound_inv.values())!=24102:raise ValueError("Inventory coverage")
    counts=collections.Counter(r["tariff_signature"] for r in offers);bound_counts=collections.Counter(r["tariff_signature"] for r in legacy.bound.values())
    for sig,proof in sorted(gate.evidence.items()):details.append(dict(signature=sig,family=legacy.registry[sig]["family"],congestionEvidence=proof,identities=counts[sig],bound=bound_counts[sig]))
    stations={s["id"]:s for s in canonical["stations"]};evses={e["id"]:e for e in canonical["evses"]};connectors={c["id"]:c for c in canonical["connectors"]}
    cohorts=collections.defaultdict(list)
    for r in legacy.bound.values():cohorts[r["tariff_signature"],r["national_mode"],r["national_kw"]].append(r)
    rows=[]
    for k,rr in sorted(cohorts.items()):
        r=min(rr,key=lambda v:v["national_id"])
        rows.append(dict(station={k:stations[r["nationalStationKey"]][k] for k in ("id","name","latitude","longitude","cpoId")},evse={k:evses[r["nationalEvseKey"]][k] for k in ("id","officialEvseId")},connector={k:connectors[r["nationalConnectorKey"]][k] for k in ("id","kind","powerKw")},binding=r,weight=len(rr)))
    if sum(r["weight"] for r in rows)!=24102:raise ValueError("Cohort coverage")
    inp=root/"input.json";inp.write_text(j(dict(rows=rows,lineage=lineage,evidence=gate.evidence)))
    runner=ROOT/"scripts/test_g66b5b_clock_transport.cjs";prod=ROOT/"production"
    req=root/"requests.json";res=root/"responses.json";run=root/"runtime-result.json"
    subprocess.run(["node",str(runner),str(prod),str(inp),"collect",str(req)],check=True,timeout=240)
    requests=json.loads(req.read_text())
    if len(requests)!=len(rows)*12 or len({j(x) for x in requests})!=len(requests):raise ValueError("Planner request coverage")
    invalid=collections.Counter()
    for x in requests:
        try:planner_session(x["session"])
        except (ValueError,TypeError,KeyError,ArithmeticError) as ex:invalid[str(ex)]+=1
    if invalid:print("Planner input refusals",dict(invalid))
    quotes,n=gate.quote(requests)
    if len(quotes)!=len(requests) or any(q["publicationEligible"] for q in quotes):raise ValueError("Response coverage")
    if any(q["estimateEur"] is not None and (q["decision"] not in (PASS,ROUNDING) or (not x["session"]["includeCongestionFees"] and q.get("congestionEvidence")!=PROOF)) for x,q in zip(requests,quotes)):raise ValueError("Price gate")
    res.write_text(j([dict(request=x,response=q) for x,q in zip(requests,quotes)]))
    subprocess.run(["node",str(runner),str(prod),str(inp),"verify",str(run),str(res)],check=True,timeout=300)
    runtime=json.loads(run.read_text())
    if runtime["checks"]!=len(requests):raise ValueError("Runtime coverage")
    dest=root/"results";dest.mkdir()
    for name,p in (("requests",req),("responses",res)):
        (dest/("g66b5b-"+name+".json.gz")).write_bytes(gzip.compress(p.read_bytes(),mtime=0))
    (dest/"g66b5b-congestion-inventory.json").write_text(j(details))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,lineage=lineage,productionSha=pin["productionSha"],legacyChecks=48204,legacyRegressions=0,priorPlannerChecks=2316,priorPlannerRegressions=0,priorPlannerTransitions=[dict(before=a,after=b,count=n) for (a,b),n in sorted(transitions.items())],signatures=len(gate.evidence),identityPairs=len(offers),boundConnectors=len(legacy.bound),cohorts=len(rows),feeEvidenceSignatures=dict(sig_inv),feeEvidenceIdentities=dict(inv),feeEvidenceBound=dict(bound_inv),runtime=runtime,plannerInputRefusals=dict(invalid),candidateComparisons=n,pricesPromoted=0,supplierCalls=0,identityChanges=0,published=False,runtimeActivated=False,limitations=["Clock/date models use piecewise planner energy and real UTC civil-minute boundaries; start-locked vs dynamic, inclusive/exclusive date and replacement semantics must still agree. Mixed duration+clock family remains unresolved.","No arbitrary redistribution of residual energy or duration; exact reconciliation required for clock/date cases. Within each modeled planner step energy is proportional to elapsed time, not measured meter data.","Archived proof only for congestion exclusion; positive temporal fees not relabeled.","Representative cohorts, weighted inference not full identity replay; actual planner/session in Node, no browser; durability and real other-lane regression remain open"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b5b-report.json").write_text(j(report));print("G66B5B "+j(report))
if __name__=="__main__":main()
