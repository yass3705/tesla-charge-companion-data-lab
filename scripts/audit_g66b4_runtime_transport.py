"""G6.6b-4: actual runtime request -> verified gate -> runtime evaluation.
Two-pass isolated process transport, not a browser network endpoint."""
import collections,gzip,hashlib,json,os,pathlib,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.unify_g6_fr_dynamic import load
from scripts.g66b3_quote_gate import QuoteGate
from scripts.replay_g6_fr_simple import j
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b4_runtime_transport" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    a=download(root/"alignment",pin["alignment"],{**{k:(k,) for k in pin["alignmentExports"]},"report":("g66b2-report.json",)})
    for k,v in pin["alignmentExports"].items():verify(a[k],v)
    verify(a["report"],pin["alignmentReportSha256"]);ar=json.loads(a["report"].read_text())
    crosswalk=gzjson(a["g66b2-november-crosswalk.json.gz"]);canonical=gzjson(a["g66b2-national-active-canonical.json.gz"])
    if hashlib.sha256((json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()).hexdigest()!=ar["nationalCanonicalSha256"]:raise ValueError("Canonical SHA")
    g=download(root/"gate",pin["gate"],{"report":("g66b3-report.json",)})
    verify(g["report"],pin["gateReportSha256"]);gr=json.loads(g["report"].read_text())
    if gr["codeSha"]!=pin["gate"]["codeSha"] or gr["priorRegressions"] or gr["runtimeActivated"] or gr["published"]:raise ValueError("Gate lineage")
    r,rr=load(root/"refined",pin["refined"],pin["refinedExports"],pin["refinedReportSha256"],"g6-refined-report.json")
    offers=read_csv(r["g6-refined-offers.csv.gz"])
    lineage=gr["lineage"]
    gate=QuoteGate(offers,crosswalk,canonical,pin["candidateSha256"],lineage)
    stations={s["id"]:s for s in canonical["stations"]};evses={e["id"]:e for e in canonical["evses"]};connectors={c["id"]:c for c in canonical["connectors"]}
    rows=[dict(station={k:stations[r["nationalStationKey"]][k] for k in ("id","name","latitude","longitude","cpoId")},evse={k:evses[r["nationalEvseKey"]][k] for k in ("id","officialEvseId")},connector={k:connectors[r["nationalConnectorKey"]][k] for k in ("id","kind","powerKw")},binding=r) for r in gate.bound.values()]
    if len(rows)!=gr["boundConnectors"]:raise ValueError("Binding coverage")
    def session(at,c,p,e,consumption):
        return dict(startAt=at,timeZone="Europe/Paris",energyKwh=e,durationMinutes=(c+p)/60,chargingMinutes=c/60,postChargeMinutes=p/60,includeCongestionFees=True,consumptionKwhPer100Km=consumption)
    # Independent runtime-driven requests, not the four sessions from G6.6b-3.
    sessions={"new_runtime_day":session("2026-11-26T15:18:21+01:00",1200,300,12.875,17.4),
              "new_runtime_night":session("2026-11-26T22:51:09+01:00",2460,660,29.4,21.2)}
    inp=root/"input.json";inp.write_text(j(dict(rows=rows,sessions=sessions,lineage=lineage)))
    runner=ROOT/"scripts/test_g66b4_runtime_transport.cjs";prod=ROOT/"production"
    requests_path=root/"requests.json";responses_path=root/"responses.json";runtime_path=root/"runtime.json"
    subprocess.run(["node",str(runner),str(prod),str(inp),"collect",str(requests_path)],check=True,timeout=240)
    requests=json.loads(requests_path.read_text())
    if len(requests)!=len(rows)*len(sessions):raise ValueError("Runtime request count")
    responses,n=gate.quote(requests)
    if len(responses)!=len(requests) or n!=len(sessions)*len({r["binding"]["tariff_signature"] for r in rows}):raise ValueError("Gate response coverage")
    responses_path.write_text(j([dict(request=r,response=q) for r,q in zip(requests,responses)]))
    subprocess.run(["node",str(runner),str(prod),str(inp),"verify",str(runtime_path),str(responses_path)],check=True,timeout=300)
    runtime=json.loads(runtime_path.read_text())
    if runtime["checks"]!=len(requests):raise ValueError("Runtime result coverage")
    dest=root/"results";dest.mkdir()
    for name,p in (("requests",requests_path),("responses",responses_path)):
        (dest/("g66b4-"+name+".json.gz")).write_bytes(gzip.compress(p.read_bytes(),mtime=0))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,lineage=lineage,productionSha=pin["productionSha"],runtime=runtime,signatureSessionEvaluations=n,pricesPromoted=0,supplierCalls=0,identityChanges=0,published=False,runtimeActivated=False,limitations=["Actual session engine and shell rankRows/variantMatchesFilters on national identities, isolated Node/Python two-pass transport, not browser/network UI or full area loader","Country/lane controls synthetic and existing Production regression suite separate; no claim of real Direct/Electra/Tesla coverage","Explicit congestion false and chargeTimeline fail closed; planner-generated timelines and full UI transport remain blocked","Geo radius and plug are harness prefilters on real coordinates; pagination slicing tests not actual UI navigation","No public deployment; artifact durability unresolved"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b4-report.json").write_text(j(report));print("G66B4 "+j(report))
if __name__=="__main__":main()
