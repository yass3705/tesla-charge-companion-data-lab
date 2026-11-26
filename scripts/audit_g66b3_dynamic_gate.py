"""Validate the callable quote boundary on pinned G6.6b-2 and raw G6 signatures."""
import collections,gzip,hashlib,json,os,pathlib,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.unify_g6_fr_dynamic import load,extra_fixtures,PASS
from scripts.evaluate_g6_fr_dynamic import fixtures
from scripts.audit_g6_fr_segment_rounding import ROUNDING
from scripts.g66b3_quote_gate import QuoteGate,SCOPE,SESSION,fixture
from scripts.replay_g6_fr_simple import dec,j

def user_session(start,c,p,e,fees=True):
    return dict(startAt=start,timeZone="Europe/Paris",energy=e,seconds=c+p,chargeSeconds=c,parkSeconds=p,includeCongestionFees=fees)
def as_user(f):return user_session(f["startAt"],f["chargeSeconds"],f["parkSeconds"],f["energy"])
def request(row,s):return dict(country="FR",channel="Electroverse",session=s,**{k:row[k] for k in SCOPE})
def write(path,rows):
    path.write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode(),mtime=0))

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b3_dynamic_quote_gate" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    a=download(root/"alignment",pin["alignment"],{**{k:(k,) for k in pin["alignmentExports"]},"report":("g66b2-report.json",)})
    for k,v in pin["alignmentExports"].items():verify(a[k],v)
    verify(a["report"],pin["alignmentReportSha256"]);ar=json.loads(a["report"].read_text())
    if ar["codeSha"]!=pin["alignment"]["codeSha"] or ar["exportSha256"]!=pin["alignmentExports"] or ar["runtimeActivated"] or ar["published"] or ar["pricesPromoted"] or ar["identityChanges"]:raise ValueError("Alignment lineage")
    crosswalk=gzjson(a["g66b2-november-crosswalk.json.gz"]);canonical=gzjson(a["g66b2-national-active-canonical.json.gz"])
    canonical_bytes=(json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
    if hashlib.sha256(canonical_bytes).hexdigest()!=ar["nationalCanonicalSha256"]:raise ValueError("Canonical SHA")
    if dict(collections.Counter(r["reason"] for r in crosswalk))!=ar["newCounts"] or len(canonical["connectors"])!=ar["activeProfiles"]:raise ValueError("Crosswalk count")
    r,rr=load(root/"refined",pin["refined"],pin["refinedExports"],pin["refinedReportSha256"],"g6-refined-report.json")
    offers=read_csv(r["g6-refined-offers.csv.gz"])
    prior=download(root/"prior",pin["previous"],{"quotes":("g66-runtime-quotes.csv.gz",)})
    verify(prior["quotes"],pin["previousQuotesSha256"])
    old={(r["signature"],r["scenario"]):r for r in read_csv(prior["quotes"])}
    lineage=dict(candidateSha256=pin["candidateSha256"],nationalCanonicalSha256=ar["nationalCanonicalSha256"],alignmentArtifact=pin["alignment"]["artifact"],rawArtifact=pin["refined"]["artifact"],rawExportSha256=pin["refinedExports"]["g6-refined-offers.csv.gz"],codeSha=os.environ.get("GITHUB_SHA"))
    gate=QuoteGate(offers,crosswalk,canonical,pin["candidateSha256"],lineage)
    if len(gate.bound)!=ar["newCounts"]["EXACT_RUNTIME_CROSSWALK"]:raise ValueError("Binding coverage")
    hist={f["id"]:as_user(f) for f in list(fixtures())+list(extra_fixtures()) if f["id"] in ("short","overnight_partial")}
    hist["ui_new_mixed"]=user_session("2026-11-25T18:21:13Z",2117,437,"24.789")
    jobs={(sig,name):(sig,fixture(s)) for name,s in hist.items() for sig in gate.registry}
    out=gate.evaluate_signatures(jobs)
    if set(out)!=set(old):raise ValueError("Historical coverage")
    for key,v in out.items():
        prev=old[key]
        if v["decision"]!=prev["decision"] or (v["estimateEur"] or "")!=prev["estimate_eur"]:raise ValueError("Prior quote regression "+str(key))
    # Exercise full request scope, all approved connectors, new sessions and one repeat.
    sessions={"new_day":user_session("2026-11-26T14:37:19+01:00",973,211,"8.963"),
              "new_night":user_session("2026-11-26T22:42:39+01:00",2513,1451,"34.217"),
              "new_dst":user_session("2026-10-25T02:19:21+02:00",4111,619,"31.419"),
              "new_parking":user_session("2026-11-26T18:02:21+01:00",0,1169,"0")}
    rows=list(gate.bound.values());coverage={};dest=root/"results";dest.mkdir()
    for name,s in sessions.items():
        req=[request(r,s) for r in rows];quotes,n=gate.quote(req)
        if len(quotes)!=len(req) or n!=len({r["tariff_signature"] for r in rows}):raise ValueError("Request coverage")
        if any(q["publicationEligible"] or q.get("scope")!={k:r[k] for k in SCOPE} or q.get("session")!=s or (q["estimateEur"] is None)!=(q["decision"] not in (PASS,ROUNDING)) for q,r in zip(quotes,rows)):raise ValueError("Response binding")
        coverage[name]=dict(collections.Counter(q["decision"] for q in quotes))
        write(dest/("g66b3-"+name+".json.gz"),quotes)
    r=rows[0];s=sessions["new_day"];base=request(r,s)
    bad=[dict(base,country="IT"),dict(base,channel="Direct"),dict(base,source_id="wrong"),dict(base,tariff_signature="wrong"),dict(base,nationalConnectorKey="wrong"),dict(base,nationalStationKey="wrong"),dict(base,nationalEvseKey="wrong"),
         dict(base,session=dict(s,includeCongestionFees=False)),dict(base,session=dict(s,timeZone="UTC")),dict(base,session=dict(s,startAt="2026-11-26T14:00:00")),dict(base,session=dict(s,seconds=s["seconds"]+1)),dict(base,session=dict(s,energy="-1")),dict(base,session=dict(s,chargeSeconds=True)),dict(base,session={k:v for k,v in s.items() if k!="parkSeconds"})]
    invalid,called=gate.quote(bad)
    if called or any(q["estimateEur"] is not None or q["publicationEligible"] for q in invalid):raise ValueError("Invalid request did not fail closed")
    repeated,called=gate.quote([base,base])
    if called!=1 or repeated[0]!=repeated[1]:raise ValueError("Exact session deduplication")
    write(dest/"g66b3-regression.json.gz",[dict(signature=k[0],scenario=k[1],**v) for k,v in sorted(out.items())])
    write(dest/"g66b3-guards.json.gz",invalid)
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,lineage=lineage,identityPairs=len(crosswalk),boundConnectors=len(rows),signatures=len(gate.registry),priorCases=len(old),priorRegressions=0,newSessions=len(sessions),newConnectorQuotes=len(rows)*len(sessions),coverage=coverage,guards=len(bad)+1,pricesPromoted=0,supplierCalls=0,identityChanges=0,published=False,runtimeActivated=False,limitations=["Callable isolated Python/Node diagnostic adapter, not deployed browser or HTTP service","Explicit includeCongestionFees=true means all known raw components are retained; exclusion false fails closed because separate surcharge classification has not been proven","No cost/km or UI ranking claimed; integration with real session inputs and existing channels separate","Unknown or ambiguous offers remain unpriced; no commercial verification","Artifacts remain expiring until archived"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b3-report.json").write_text(j(report))
    print("G66B3 "+j(report))
if __name__=="__main__":main()
