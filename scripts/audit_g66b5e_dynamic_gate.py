"""Recompute all previous exact requests through the new dynamic gate."""
import collections,gzip,json,os,pathlib,sys
from decimal import Decimal
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.unify_g6_fr_dynamic import load,PASS
from scripts.g66b3_quote_gate import QuoteGate
from scripts.g66b5e_dynamic_gate import DynamicPlannerGate,ZERO
from scripts.g66b5a_planner_gate import planner_session
from scripts.audit_g66b5d_residual_evidence import conservative_rates,zero_temporal,FEE
from scripts.replay_g6_fr_simple import j
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b5e_dynamic_zero_temporal" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    oldpin=json.loads((ROOT/"migration/v9/g66b5d-residual-evidence-request.json").read_text())
    clockpin=json.loads((ROOT/"migration/v9/g66b5b-clock-planner-request.json").read_text())
    if pin["productionSha"]!=oldpin["productionSha"] or pin["productionSha"]!=clockpin["productionSha"]:raise ValueError("Production pin")
    def pinned(folder,spec,exports,reportsha,reportname):
        a=download(root/folder,spec,{**{k:(k,) for k in exports},"report":(reportname,)})
        for k,v in exports.items():verify(a[k],v)
        verify(a["report"],reportsha);r=json.loads(a["report"].read_text())
        if r["codeSha"]!=spec["codeSha"]:raise ValueError("Code lineage")
        return a,r
    d,dr=pinned("residual",pin["residual"],pin["residualExports"],pin["residualReportSha256"],"g66b5d-report.json")
    if dr["sourcePin"]!=oldpin or dr["priorRegressions"] or dr["sessionZeroTemporalCandidates"]!=198 or dr["quoteGateChanged"] or dr["published"] or dr["pricesPromoted"]:raise ValueError("Residual proof")
    c,cr=pinned("review",pin["clockReview"],pin["clockReviewExports"],pin["clockReviewReportSha256"],"g66b5c-report.json")
    b,br=pinned("clock",pin["clock"],pin["clockExports"],pin["clockReportSha256"],"g66b5b-report.json")
    if cr["priorRegressions"] or cr["published"] or cr["pricesPromoted"] or br["legacyRegressions"] or br["priorPlannerRegressions"] or br["published"]:raise ValueError("Prior proof")
    rows=gzjson(c["g66b5c-responses.json.gz"]);reqs=gzjson(b["g66b5b-requests.json.gz"])
    candidates=gzjson(d["g66b5d-zero-temporal-candidates.json.gz"]);want={x["index"]:x for x in candidates}
    if len(want)!=198 or len(rows)!=6948 or len(reqs)!=6948 or len({j(x) for x in reqs})!=6948 or any(r["request"]!=q for r,q in zip(rows,reqs)):raise ValueError("Request coverage")
    a,ar=pinned("alignment",clockpin["alignment"],clockpin["alignmentExports"],clockpin["alignmentReportSha256"],"g66b2-report.json")
    g,gr=pinned("legacy",clockpin["gate"],{},clockpin["gateReportSha256"],"g66b3-report.json")
    r,rr=load(root/"refined",pin["refined"],pin["refinedExports"],pin["refinedReportSha256"],"g6-refined-report.json")
    legacy=QuoteGate(read_csv(r["g6-refined-offers.csv.gz"]),gzjson(a["g66b2-november-crosswalk.json.gz"]),gzjson(a["g66b2-national-active-canonical.json.gz"]),pin["candidateSha256"],gr["lineage"])
    if len(legacy.bound)!=24102 or len(legacy.registry)!=262:raise ValueError("Registry coverage")
    # Use the old lineage for strict regression comparison; this report records
    # actual new code. New runtime transport of session proof remains a later gate.
    gate=DynamicPlannerGate(legacy,br["lineage"])
    out,n=gate.quote(reqs)
    if len(out)!=6948:raise ValueError("Coverage")
    changed=[]
    for i,(x,new) in enumerate(zip(rows,out)):
        old=x["response"]
        if i not in want:
            if old!=new:raise ValueError("Unexpected change at "+str(i))
            continue
        w=want[i];inc=out[w["includedIndex"]];q=reqs[i]
        if old["decision"]!=FEE or old["estimateEur"] is not None or new["congestionEvidence"]!=ZERO or new["estimateEur"]!=w["archivedEstimateEur"] or new["estimateEur"]!=inc["estimateEur"] or new["components"]!=inc["components"]:raise ValueError("Candidate result")
        if new["session"]!=q["session"] or new["publicationEligible"] or not new["diagnosticOnly"]:raise ValueError("Candidate scope")
        changed.append(i)
    if len(changed)!=198 or sum(q["estimateEur"] is not None for q in out)!=4744:raise ValueError("Coverage gain")
    # Exercise new exact sessions on real bound signatures (not the archived
    # allow-list): 30-minute + 90-minute + 7-day sessions, with both phases,
    # different start hours, including a midnight crossing.
    by={}
    for i in want:by.setdefault(reqs[i]["tariff_signature"],reqs[i])
    probes=[];expected=[]
    for sig,q in sorted(by.items()):
        for start,duration,charge in (("2026-11-26T12:00:00Z",30,20),("2026-11-26T21:59:30Z",90,60),("2026-11-26T23:59:30Z",10080,60)):
            s=dict(protocol="planner-v1",startAt=start,timeZone="Europe/Paris",energy="1.000000",durationMinutes=f"{duration:.6f}",chargingMinutes=f"{charge:.6f}",postChargeMinutes=f"{duration-charge:.6f}",includeCongestionFees=False,chargeTimeline=[dict(offsetMinutes="0.000000",durationMinutes=f"{charge:.6f}",energyKwh="1.000000")])
            q2={**q,"session":s};f=planner_session(s);possible,_=conservative_rates(legacy.prepared[sig],f);expected.append(zero_temporal(possible,f));probes.append(q2)
    if any(j(x) in {j(q) for q in reqs} for x in probes):raise ValueError("Probe equals archive")
    pq,m=gate.quote(probes);n+=m
    if len(pq)!=len(probes):raise ValueError("Probe count")
    for q,r,proof in zip(probes,pq,expected):
        if not proof and (r["decision"]!=FEE or r["estimateEur"] is not None):raise ValueError("Positive rate probe priced")
        if r["estimateEur"] is not None and (r["congestionEvidence"]!=ZERO or not proof):raise ValueError("Probe proof")
    if all(expected) or not any(expected):raise ValueError("Probe lacks boundary variation")
    # Exact scope and input refusal on genuinely changed requests.
    q=probes[0]
    bad=[{**q,"tariff_signature":"not-the-signature"},{**q,"channel":"Electra"},{**q,"session":{**q["session"],"chargingMinutes":"99999.000000"}}]
    badq,_=gate.quote(bad)
    if any(x["estimateEur"] is not None for x in badq):raise ValueError("Scope guard")
    dest=root/"results";dest.mkdir()
    for name,value in (("responses",[dict(request=q,response=r) for q,r in zip(reqs,out)]),("probes",[dict(request=q,response=r,zeroTemporalEnvelope=proof) for q,r,proof in zip(probes,pq,expected)])):
        (dest/f"g66b5e-{name}.json.gz").write_bytes(gzip.compress(j(value).encode(),mtime=0))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,productionSha=pin["productionSha"],checks=6948,priorPricedPreserved=4546,priorRegressions=0,newPriced=198,priced=4744,unpriced=2204,probeCount=len(probes),probeZeroProof=sum(expected),probePositiveRate=sum(not x for x in expected),probePriced=sum(x["estimateEur"] is not None for x in pq),scopeGuards=len(bad),candidateComparisons=n,decisions=dict(collections.Counter(x["decision"] for x in out)),feeProofs=dict(collections.Counter(x.get("congestionEvidence") for x in out)),identityChanges=0,pricesPromoted=0,supplierCalls=0,published=False,runtimeActivated=False,limitations=["Exact session zero temporal proof concerns archived components only; no external fee assertion","Dynamic Data Lab gate only; Production transport and browser not activated","Representative cohorts not whole identity replay; other lanes and archive durability remain open"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b5e-report.json").write_text(j(report));print("G66B5E "+j(report))
if __name__=="__main__":main()
