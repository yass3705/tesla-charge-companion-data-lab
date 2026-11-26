"""G6.6b-6b actual shell ranking, scoped diagnostic transport, offline."""
import collections,gzip,json,os,pathlib,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.unify_g6_fr_dynamic import load
from scripts.g66b3_quote_gate import QuoteGate
from scripts.g66b5e_dynamic_gate import DynamicPlannerGate
from scripts.replay_g6_fr_simple import j
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b6b_ranked_comparison" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    oldpin=json.loads((ROOT/"migration/v9/g66b6a-runtime-transport-request.json").read_text())
    dynpin=json.loads((ROOT/"migration/v9/g66b5e-dynamic-zero-request.json").read_text())
    clockpin=json.loads((ROOT/"migration/v9/g66b5b-clock-planner-request.json").read_text())
    prod=ROOT/"production"
    if subprocess.check_output(["git","-C",str(prod),"rev-parse","HEAD"],text=True).strip()!=pin["productionSha"] or oldpin["productionSha"]!=pin["previousProductionSha"]:raise ValueError("Production pin")
    def pinned(folder,spec,exports,reportsha,reportname):
        a=download(root/folder,spec,{**{k:(k,) for k in exports},"report":(reportname,)})
        for k,v in exports.items():verify(a[k],v)
        verify(a["report"],reportsha);r=json.loads(a["report"].read_text())
        if r["codeSha"]!=spec["codeSha"]:raise ValueError("Code lineage")
        return a,r
    t,tr=pinned("transport",pin["transport"],pin["transportExports"],pin["transportReportSha256"],"g66b6a-report.json")
    if tr["sourcePin"]!=oldpin or tr["productionSha"]!=pin["previousProductionSha"] or tr["priorRegressions"] or tr["priced"]!=4744 or tr["unpriced"]!=2204 or tr["published"] or tr["pricesPromoted"] or tr["runtimeActivated"]:raise ValueError("Prior transport proof")
    prior=gzjson(t["g66b6a-responses.json.gz"]);req0=gzjson(t["g66b6a-requests.json.gz"])
    if len(prior)!=6948 or len({j(x["request"]) for x in prior})!=6948 or any(x["request"]!=q for x,q in zip(prior,req0)):raise ValueError("Prior coverage")
    a,ar=pinned("alignment",clockpin["alignment"],clockpin["alignmentExports"],clockpin["alignmentReportSha256"],"g66b2-report.json")
    g,gr=pinned("legacy",clockpin["gate"],{},clockpin["gateReportSha256"],"g66b3-report.json")
    r,rr=load(root/"refined",dynpin["refined"],dynpin["refinedExports"],dynpin["refinedReportSha256"],"g6-refined-report.json")
    canonical=gzjson(a["g66b2-national-active-canonical.json.gz"])
    legacy=QuoteGate(read_csv(r["g6-refined-offers.csv.gz"]),gzjson(a["g66b2-november-crosswalk.json.gz"]),canonical,dynpin["candidateSha256"],gr["lineage"])
    if len(legacy.bound)!=24102 or len(legacy.registry)!=262:raise ValueError("Registry coverage")
    lineage=tr["lineage"];gate=DynamicPlannerGate(legacy,lineage)
    stations={s["id"]:s for s in canonical["stations"]};evses={e["id"]:e for e in canonical["evses"]};connectors={c["id"]:c for c in canonical["connectors"]}
    cohorts=collections.defaultdict(list)
    for r in legacy.bound.values():cohorts[r["tariff_signature"],r["national_mode"],r["national_kw"]].append(r)
    rows=[]
    for k,rr in sorted(cohorts.items()):
        r=min(rr,key=lambda v:v["national_id"])
        rows.append(dict(station={k:stations[r["nationalStationKey"]][k] for k in ("id","name","latitude","longitude","cpoId")},evse={k:evses[r["nationalEvseKey"]][k] for k in ("id","officialEvseId")},connector={k:connectors[r["nationalConnectorKey"]][k] for k in ("id","kind","powerKw")},binding=r,weight=len(rr)))
    if len(rows)!=579 or sum(r["weight"] for r in rows)!=24102:raise ValueError("Cohort coverage")
    inp=root/"input.json";inp.write_text(j(dict(rows=rows,lineage=lineage)))
    runner=ROOT/"scripts/test_g66b6b_ranking_transport.cjs";req=root/"requests.json";res=root/"responses.json";run=root/"ranking.json"
    subprocess.run(["node",str(runner),str(prod),str(inp),"collect",str(req)],check=True,timeout=420)
    requests=json.loads(req.read_text())
    if len(requests)<1737 or len({j(q) for q in requests})!=len(requests):raise ValueError("Request coverage")
    quotes,n=gate.quote(requests)
    if len(quotes)!=len(requests):raise ValueError("Gate coverage")
    baseline={j(x["request"]):x["response"] for x in prior};matched=0
    for q,r in zip(requests,quotes):
        if r["publicationEligible"] or not r["diagnosticOnly"]:raise ValueError("Promotion")
        if j(q) in baseline:
            if r!=baseline[j(q)]:raise ValueError("Prior price regression")
            matched+=1
    if matched<1737:raise ValueError("Prior exact session coverage")
    res.write_text(j([dict(request=q,response=r) for q,r in zip(requests,quotes)]))
    subprocess.run(["node",str(runner),str(prod),str(inp),"verify",str(run),str(res)],check=True,timeout=420)
    runtime=json.loads(run.read_text())
    if runtime["uniqueRequests"]!=len(requests):raise ValueError("Transport coverage")
    dest=root/"results";dest.mkdir()
    for name,p in (("requests",req),("responses",res)):
        (dest/("g66b6b-"+name+".json.gz")).write_bytes(gzip.compress(p.read_bytes(),mtime=0))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,lineage=lineage,productionSha=pin["productionSha"],checks=len(requests),priorExactMatches=matched,priorRegressions=0,candidateComparisons=n,runtime=runtime,identityChanges=0,pricesPromoted=0,supplierCalls=0,published=False,runtimeActivated=False,limitations=["Actual shell functions and geographic data engine in Node, injected exact transport; no service, public config or browser activation","579 representative connectors grouped by real station identity; not full national replay","Physical plug subtype and channel UI filters not implemented or validated here; AC/DC, power, operator and lane separation tested","Top 20 and subsequent prefixes tested via ranking API; interactive DOM rendering remains G6.6b-6d","Other real lanes and durable archive remain open"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b6b-report.json").write_text(j(report));print("G66B6B "+j(report))
if __name__=="__main__":main()
