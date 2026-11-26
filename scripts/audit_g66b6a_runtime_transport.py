"""G6.6b-6a: actual runtime planner -> dynamic gate -> exact runtime result.
The transport is an offline test adapter, not a deployed quote service.
"""
import collections,gzip,json,os,pathlib,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.unify_g6_fr_dynamic import load
from scripts.g66b3_quote_gate import QuoteGate
from scripts.g66b5e_dynamic_gate import DynamicPlannerGate,ZERO
from scripts.replay_g6_fr_simple import j
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b6a_runtime_transport" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    oldpin=json.loads((ROOT/"migration/v9/g66b5e-dynamic-zero-request.json").read_text())
    clockpin=json.loads((ROOT/"migration/v9/g66b5b-clock-planner-request.json").read_text())
    if pin["previousProductionSha"]!=oldpin["productionSha"]:raise ValueError("Production predecessor")
    prod=ROOT/"production"
    if subprocess.check_output(["git","-C",str(prod),"rev-parse","HEAD"],text=True).strip()!=pin["productionSha"]:raise ValueError("Production pin")
    def pinned(folder,spec,exports,reportsha,reportname):
        a=download(root/folder,spec,{**{k:(k,) for k in exports},"report":(reportname,)})
        for k,v in exports.items():verify(a[k],v)
        verify(a["report"],reportsha);r=json.loads(a["report"].read_text())
        if r["codeSha"]!=spec["codeSha"]:raise ValueError("Code lineage")
        return a,r
    d,dr=pinned("dynamic",pin["dynamicGate"],pin["dynamicExports"],pin["dynamicReportSha256"],"g66b5e-report.json")
    if dr["sourcePin"]!=oldpin or dr["priorRegressions"] or dr["priced"]!=4744 or dr["published"] or dr["pricesPromoted"] or dr["runtimeActivated"]:raise ValueError("Dynamic proof")
    prior=gzjson(d["g66b5e-responses.json.gz"])
    if len(prior)!=6948 or len({j(x["request"]) for x in prior})!=6948:raise ValueError("Prior coverage")
    a,ar=pinned("alignment",clockpin["alignment"],clockpin["alignmentExports"],clockpin["alignmentReportSha256"],"g66b2-report.json")
    g,gr=pinned("legacy",clockpin["gate"],{},clockpin["gateReportSha256"],"g66b3-report.json")
    r,rr=load(root/"refined",oldpin["refined"],oldpin["refinedExports"],oldpin["refinedReportSha256"],"g6-refined-report.json")
    canonical=gzjson(a["g66b2-national-active-canonical.json.gz"])
    legacy=QuoteGate(read_csv(r["g6-refined-offers.csv.gz"]),gzjson(a["g66b2-november-crosswalk.json.gz"]),canonical,oldpin["candidateSha256"],gr["lineage"])
    if len(legacy.bound)!=24102 or len(legacy.registry)!=262:raise ValueError("Registry coverage")
    lineage={**gr["lineage"],"codeSha":pin["dynamicGate"]["codeSha"],"legacyGateCodeSha":gr["lineage"]["codeSha"],"protocol":"planner-v1"}
    gate=DynamicPlannerGate(legacy,lineage)
    stations={s["id"]:s for s in canonical["stations"]};evses={e["id"]:e for e in canonical["evses"]};connectors={c["id"]:c for c in canonical["connectors"]}
    cohorts=collections.defaultdict(list)
    for r in legacy.bound.values():cohorts[r["tariff_signature"],r["national_mode"],r["national_kw"]].append(r)
    rows=[]
    for k,rr in sorted(cohorts.items()):
        r=min(rr,key=lambda v:v["national_id"])
        rows.append(dict(station={k:stations[r["nationalStationKey"]][k] for k in ("id","name","latitude","longitude","cpoId")},evse={k:evses[r["nationalEvseKey"]][k] for k in ("id","officialEvseId")},connector={k:connectors[r["nationalConnectorKey"]][k] for k in ("id","kind","powerKw")},binding=r,weight=len(rr)))
    if len(rows)!=579 or sum(r["weight"] for r in rows)!=24102:raise ValueError("Cohort coverage")
    inp=root/"input.json";inp.write_text(j(dict(rows=rows,lineage=lineage,evidence=gate.evidence)))
    runner=ROOT/"scripts/test_g66b6a_runtime_transport.cjs"
    req=root/"requests.json";res=root/"responses.json";run=root/"runtime-result.json"
    subprocess.run(["node",str(runner),str(prod),str(inp),"collect",str(req)],check=True,timeout=240)
    requests=json.loads(req.read_text())
    if len(requests)!=6948 or len({j(q) for q in requests})!=6948 or any(q!=x["request"] for q,x in zip(requests,prior)):raise ValueError("Actual planner request regression")
    quotes,n=gate.quote(requests)
    if len(quotes)!=6948:raise ValueError("Gate coverage")
    for old,new in zip(prior,quotes):
        old=old["response"]
        if {k:v for k,v in old.items() if k!="lineage"}!={k:v for k,v in new.items() if k!="lineage"} or new["lineage"]!=lineage:raise ValueError("Dynamic quote regression")
        if new["publicationEligible"] or not new["diagnosticOnly"]:raise ValueError("Promotion")
    if sum(x["estimateEur"] is not None for x in quotes)!=4744 or sum(x.get("congestionEvidence")==ZERO for x in quotes)!=198:raise ValueError("Priced coverage")
    res.write_text(j([dict(request=q,response=r) for q,r in zip(requests,quotes)]))
    subprocess.run(["node",str(runner),str(prod),str(inp),"verify",str(run),str(res)],check=True,timeout=300)
    runtime=json.loads(run.read_text())
    if runtime["checks"]!=6948 or sum(x["priced"] for x in runtime["coverage"].values())!=4744 or sum(x["unpriced"] for x in runtime["coverage"].values())!=2204:raise ValueError("Runtime coverage")
    dest=root/"results";dest.mkdir()
    for name,p in (("requests",req),("responses",res)):
        (dest/("g66b6a-"+name+".json.gz")).write_bytes(gzip.compress(p.read_bytes(),mtime=0))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,lineage=lineage,productionSha=pin["productionSha"],checks=6948,priorRegressions=0,priced=4744,unpriced=2204,sessionZeroPriced=198,candidateComparisons=n,runtime=runtime,identityChanges=0,pricesPromoted=0,supplierCalls=0,published=False,runtimeActivated=False,limitations=["Actual Node runtime planner and session engine with an isolated exact request/response transport; not an HTTP service or browser deployment","Dynamic gate recomputed all requests; archived results serve only as regression baseline","Representative cohorts, weighted inference not full identity replay; real other-lane and browser tests and durable archive remain open"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b6a-report.json").write_text(j(report));print("G66B6A "+j(report))
if __name__=="__main__":main()
