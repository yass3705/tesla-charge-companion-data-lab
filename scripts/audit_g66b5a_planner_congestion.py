"""G6.6b-5a: archived fee classification and actual planner protocol replay."""
import collections,gzip,hashlib,json,os,pathlib,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.unify_g6_fr_dynamic import load,PASS
from scripts.g66b3_quote_gate import QuoteGate
from scripts.g66b5a_planner_gate import PlannerGate,PROOF,planner_session
from scripts.replay_g6_fr_simple import j
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b5a_planner_congestion" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
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
    gate=PlannerGate(legacy,lineage)
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
    runner=ROOT/"scripts/test_g66b5a_planner_transport.cjs";prod=ROOT/"production"
    req=root/"requests.json";res=root/"responses.json";run=root/"runtime-result.json"
    subprocess.run(["node",str(runner),str(prod),str(inp),"collect",str(req)],check=True,timeout=240)
    requests=json.loads(req.read_text())
    if len(requests)!=len(rows)*4 or len({j(x) for x in requests})!=len(requests):raise ValueError("Planner request coverage")
    invalid=collections.Counter()
    for x in requests:
        try:planner_session(x["session"])
        except (ValueError,TypeError,KeyError,ArithmeticError) as ex:invalid[str(ex)]+=1
    if invalid:print("Planner input refusals",dict(invalid))
    quotes,n=gate.quote(requests)
    if len(quotes)!=len(requests) or any(q["publicationEligible"] for q in quotes):raise ValueError("Response coverage")
    if any(q["estimateEur"] is not None and (q["decision"]!=PASS or (not x["session"]["includeCongestionFees"] and q.get("congestionEvidence")!=PROOF)) for x,q in zip(requests,quotes)):raise ValueError("Price gate")
    res.write_text(j([dict(request=x,response=q) for x,q in zip(requests,quotes)]))
    subprocess.run(["node",str(runner),str(prod),str(inp),"verify",str(run),str(res)],check=True,timeout=300)
    runtime=json.loads(run.read_text())
    if runtime["checks"]!=len(requests):raise ValueError("Runtime coverage")
    dest=root/"results";dest.mkdir()
    for name,p in (("requests",req),("responses",res)):
        (dest/("g66b5a-"+name+".json.gz")).write_bytes(gzip.compress(p.read_bytes(),mtime=0))
    (dest/"g66b5a-congestion-inventory.json").write_text(j(details))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,lineage=lineage,productionSha=pin["productionSha"],legacyChecks=48204,legacyRegressions=0,signatures=len(gate.evidence),identityPairs=len(offers),boundConnectors=len(legacy.bound),cohorts=len(rows),feeEvidenceSignatures=dict(sig_inv),feeEvidenceIdentities=dict(inv),feeEvidenceBound=dict(bound_inv),runtime=runtime,plannerInputRefusals=dict(invalid),candidateComparisons=n,pricesPromoted=0,supplierCalls=0,identityChanges=0,published=False,runtimeActivated=False,limitations=["First safe tranche: fractional unrestricted/duration-only rate envelope and actual planner transport. Clock/calendar-dependent sessions, variable rate allocation and ambiguous duration remain unresolved.","Proof of no positive temporal component in archived signature only; not a claim about external/live congestion fees. Positive time/parking rates are not relabeled congestion.","Representative per signature/current/power; weighted coverage is cohort inference, not individual replay. Legacy gate replay exact; actual planner and session in Node, no browser or UI activation.","Timeline steps retained, six-decimal representation coherence only; energy-rate invariance means detailed allocation cannot change the energy total. No uniform distribution assumption for variable prices.","Artifact durability and real other-lane non-regression remain open"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b5a-report.json").write_text(j(report));print("G66B5A "+j(report))
if __name__=="__main__":main()
