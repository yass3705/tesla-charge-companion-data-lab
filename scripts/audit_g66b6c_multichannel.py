"""G6.6b-6c archived real data A/B runtime, no provider or deployment."""
import collections,gzip,json,os,pathlib,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.unify_g6_fr_dynamic import load
from scripts.g66b3_quote_gate import QuoteGate
from scripts.g66b5e_dynamic_gate import DynamicPlannerGate
from scripts.replay_g6_fr_simple import j
from scripts.build_v9_archived_direct_profiles import replay,normalize as direct_normalize,FAMILIES
from scripts.build_v9_archived_emsp import build as build_emsp
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b6c_multichannel_regression" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    oldpin=json.loads((ROOT/"migration/v9/g66b6b-ranking-transport-request.json").read_text())
    dynpin=json.loads((ROOT/"migration/v9/g66b5e-dynamic-zero-request.json").read_text())
    clockpin=json.loads((ROOT/"migration/v9/g66b5b-clock-planner-request.json").read_text())
    prod=ROOT/"production";base=ROOT/"production-baseline"
    for folder,k in ((prod,"productionSha"),(base,"baselineProductionSha")):
        if subprocess.check_output(["git","-C",str(folder),"rev-parse","HEAD"],text=True).strip()!=pin[k]:raise ValueError("Production pin")
    def pinned(folder,spec,exports,reportsha,reportname):
        a=download(root/folder,spec,{**{k:(k,) for k in exports},"report":(reportname,)})
        for k,v in exports.items():verify(a[k],v)
        verify(a["report"],reportsha);r=json.loads(a["report"].read_text())
        if r["codeSha"]!=spec["codeSha"]:raise ValueError("Code lineage")
        return a,r
    t,tr=pinned("ranking",pin["ranking"],pin["rankingExports"],pin["rankingReportSha256"],"g66b6b-report.json")
    if tr["sourcePin"]!=oldpin or tr["productionSha"]!=pin["productionSha"] or tr["priorRegressions"] or tr["checks"]!=1840 or tr["published"] or tr["pricesPromoted"] or tr["runtimeActivated"]:raise ValueError("Prior proof")
    prior=gzjson(t["g66b6b-responses.json.gz"]);req0=gzjson(t["g66b6b-requests.json.gz"])
    if len(prior)!=1840 or len({j(x["request"]) for x in prior})!=1840 or any(x["request"]!=q for x,q in zip(prior,req0)):raise ValueError("Prior coverage")
    a,ar=pinned("alignment",clockpin["alignment"],clockpin["alignmentExports"],clockpin["alignmentReportSha256"],"g66b2-report.json")
    g,gr=pinned("legacy",clockpin["gate"],{},clockpin["gateReportSha256"],"g66b3-report.json")
    r,rr=load(root/"refined",dynpin["refined"],dynpin["refinedExports"],dynpin["refinedReportSha256"],"g6-refined-report.json")
    canonical=gzjson(a["g66b2-national-active-canonical.json.gz"])
    legacy=QuoteGate(read_csv(r["g6-refined-offers.csv.gz"]),gzjson(a["g66b2-november-crosswalk.json.gz"]),canonical,dynpin["candidateSha256"],gr["lineage"])
    if len(legacy.bound)!=24102 or len(legacy.registry)!=262:raise ValueError("Registry coverage")
    lineage=tr["lineage"];gate=DynamicPlannerGate(legacy,lineage)
    # Archived normalizers, no new matching policy or provider access.
    nat=root/"national.json";nat.write_text(j(canonical))
    work=root/"compiler";work.mkdir();archives={};provenance={}
    for family in FAMILIES:archives[family],provenance[family]=replay(family,work)
    direct,dr=direct_normalize(canonical,archives,provenance)
    directfile=root/"direct.json";directfile.write_text(j(direct))
    er=build_emsp(nat,ROOT/"data/platforms/electra/france","Electra",root/"electra")
    electrafile=root/"electra/FR__electra_emsp_exact.json"
    electra=json.loads(electrafile.read_text())
    mac=ROOT/"data/tesla/mac/catalogue.json";verify(mac,pin["teslaCatalogueSha256"])
    manifest=json.loads((ROOT/"data/tesla/mac/last-good.json").read_text())
    if manifest["catalogueSha256"]!=pin["teslaCatalogueSha256"] or manifest["status"]!="last-good" or manifest["stationCount"]!=len(json.loads(mac.read_text())):raise ValueError("Mac archive proof")
    stations={s["id"]:s for s in canonical["stations"]};evses={e["id"]:e for e in canonical["evses"]};connectors={c["id"]:c for c in canonical["connectors"]}
    de={o["scope"]["evseId"] for o in direct["offers"] if not o.get("calculationHold")}
    ee={o["scope"]["evseId"] for o in electra["offers"] if not o.get("calculationHold")}
    # Preserve real IDs and choose bounded, deterministic cohorts by lane
    # intersection, signature and nominal power, with all triple overlaps
    # preferred. No transfer or fabrication of an offer.
    groups=collections.defaultdict(list);eligible=collections.Counter()
    for b in legacy.bound.values():
        e=b["nationalEvseKey"];lanes=("direct" if e in de else "")+("electra" if e in ee else "")
        if not lanes:continue
        eligible[lanes]+=1;groups[lanes,b["tariff_signature"],b["national_mode"],b["national_kw"]].append(b)
    rows=[]
    for k,bb in sorted(groups.items()):
        b=min(bb,key=lambda v:v["national_id"])
        rows.append(dict(station={k:stations[b["nationalStationKey"]][k] for k in ("id","name","latitude","longitude","cpoId")},evse={k:evses[b["nationalEvseKey"]][k] for k in ("id","officialEvseId")},connector={k:connectors[b["nationalConnectorKey"]][k] for k in ("id","kind","powerKw")},binding=b))
    if not rows:raise ValueError("No mixed real scope")
    inp=root/"input.json";inp.write_text(j(dict(archives={"Direct":str(directfile),"Electra":str(electrafile)},tesla=str(mac),mixed=rows,mixedStationIds=sorted({b["station"]["id"] for b in rows}),lineage=lineage)))
    runner=ROOT/"scripts/test_g66b6c_multichannel.cjs";req=root/"requests.json";res=root/"responses.json";run=root/"multichannel.json"
    subprocess.run(["node","--max-old-space-size=6144",str(runner),str(prod),str(base),str(inp),"collect",str(req)],check=True,timeout=900)
    requests=json.loads(req.read_text())
    if not requests or len({j(q) for q in requests})!=len(requests):raise ValueError("Request coverage")
    quotes,n=gate.quote(requests)
    if len(quotes)!=len(requests):raise ValueError("Gate coverage")
    priorMap={j(x["request"]):x["response"] for x in prior};matched=0
    for q,r in zip(requests,quotes):
        if r["publicationEligible"] or not r["diagnosticOnly"]:raise ValueError("Promotion")
        if j(q) in priorMap:
            if r!=priorMap[j(q)]:raise ValueError("Electroverse prior regression")
            matched+=1
    res.write_text(j([dict(request=q,response=r) for q,r in zip(requests,quotes)]))
    subprocess.run(["node","--max-old-space-size=6144",str(runner),str(prod),str(base),str(inp),"verify",str(run),str(res)],check=True,timeout=900)
    runtime=json.loads(run.read_text())
    if runtime["uniqueRequests"]!=len(requests):raise ValueError("Mixed coverage")
    dest=root/"results";dest.mkdir()
    for name,p in (("requests",req),("responses",res)):
        (dest/("g66b6c-"+name+".json.gz")).write_bytes(gzip.compress(p.read_bytes(),mtime=0))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,lineage=lineage,productionSha=pin["productionSha"],baselineProductionSha=pin["baselineProductionSha"],checks=len(requests),priorExactMatches=matched,priorRegressions=0,candidateComparisons=n,archiveInputs={"Direct":{"sha256":digest(directfile),"families":dr["families"],"provenance":provenance},"Electra":{"sha256":digest(electrafile),"attributedOffers":er["attributedOffers"],"archiveOffers":er["archiveOffers"],"holds":er["calculationHolds"],"provenance":er["provenance"]},"Tesla":{"sha256":digest(mac),"stations":manifest["stationCount"],"countryDates":manifest["countryDates"]}},eligibleMixedConnectors=dict(eligible),mixedCohorts=len(rows),runtime=runtime,identityChanges=0,pricesPromoted=0,supplierCalls=0,published=False,runtimeActivated=False,limitations=["Actual archives: FR Ze-Watt/Zephyre and historical Electra exact national overlay plus Tesla last-good Mac in nine countries; not every Direct operator or Electra source worldwide","A/B exact tariff evaluation over all compiled offers in these archives; mixed scoped representatives, not entire national replay","Tesla catalogue historical, not new Mac publication; other Tesla autonomy guards exercised in CI","No browser, service, physical plug/channel UI filter or durable archive validation"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b6c-report.json").write_text(j(report));print("G66B6C "+j(report))
if __name__=="__main__":main()
