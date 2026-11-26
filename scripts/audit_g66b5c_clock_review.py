"""G6.6b-5c: isolated replay, explicit candidate response-contract correction.
No provider, publication, catalogue, engine or live runtime change.
"""
import collections,gzip,json,os,pathlib,subprocess,sys
from decimal import Decimal
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.unify_g6_fr_dynamic import load,PASS,engine_agrees
from scripts.g66b5a_planner_gate import planner_session,PROOF
from scripts.g66b5b_clock_gate import clock_quote,spans,format_parts
from scripts.g66b3_quote_gate import result
from scripts.audit_g6_fr_segment_rounding import explain,ROUNDING
from scripts.evaluate_g6_fr_dynamic import prepare,DIMS
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import dec,j
from scripts.replay_g6_fr_combined_windows import rules_for,contains
ROOT=pathlib.Path(__file__).resolve().parents[1]
def mixed_quote(prepared,s,f):
    """Conservative rate envelope: only invariant components can pass.
    Include base/merged and omitted-as-zero alternatives; all reachable bands
    even if above their upper bound (marginal vs whole session is unproved).
    No inference of a duration/clock precedence from the historical engine.
    """
    base,_,compiled=prepared
    cb,plain,groups=compiled
    if cb!=base:raise ValueError("Mixed base discrepancy")
    rows=spans(s,f)
    possible={k:{base[k],plain.get(k,base[k])} for k in DIMS}
    elapsed=dec(f["duration"])*60
    for w,g in groups.items():
        if not any(contains(w,row[3]) for row in rows):continue
        for k,v in g["plain"].items():possible[k].add(v)
        if g["plain"]:
            for k in set(DIMS)-set(g["plain"]):possible[k].add(Decimal(0))
        active={(lo,hi) for k,lo,hi,v in g["bands"] if lo<=elapsed}
        for k,lo,hi,v in g["bands"]:
            if (lo,hi) in active:possible[k].add(v)
        for lo,hi in active:
            for k in set(DIMS)-{k for k,l,h,v in g["bands"] if (l,h)==(lo,hi)}:possible[k].add(Decimal(0))
    qty=dict(energy=dec(f["energy"]),time=dec(f["charging"]),parking=dec(f["parking"]),flat=Decimal(1))
    if any(len(possible[k])!=1 and qty[k]!=0 for k in DIMS):return "INCALCULABLE_MIXED_SEMANTICS",None,None,None
    canonical=format_parts({k:min(possible[k])*qty[k] for k in DIMS})
    return "MODEL_AGREEMENT",canonical,None,rules_for(*compiled)
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b5c_clock_candidate_review" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    oldpinpath=ROOT/"migration/v9/g66b5b-clock-planner-request.json";oldpin=json.loads(oldpinpath.read_text())
    if oldpin["productionSha"]!=pin["productionSha"]:raise ValueError("Production pin")
    a=download(root/"clock",pin["clock"],{**{k:(k,) for k in pin["clockExports"]},"report":("g66b5b-report.json",)})
    for k,v in pin["clockExports"].items():verify(a[k],v)
    verify(a["report"],pin["clockReportSha256"]);ar=json.loads(a["report"].read_text())
    if ar["codeSha"]!=pin["clock"]["codeSha"] or ar["sourcePin"]!=oldpin or ar["legacyRegressions"] or ar["priorPlannerRegressions"] or ar["runtimeActivated"] or ar["published"] or ar["pricesPromoted"]:raise ValueError("Prior lineage")
    requests=gzjson(a["g66b5b-requests.json.gz"]);prior=gzjson(a["g66b5b-responses.json.gz"])
    if len(requests)!=6948 or len(prior)!=6948 or len({j(x) for x in requests})!=6948 or any(r["request"]!=q for r,q in zip(prior,requests)):raise ValueError("Request identity")
    # Replay the previous code unchanged with its ORIGINAL lineage solely for
    # regression comparison; this run's own report has the real current SHA.
    env={**os.environ,"GITHUB_SHA":pin["clock"]["codeSha"]}
    subprocess.run([sys.executable,"-m","scripts.audit_g66b5b_clock_planner",str(oldpinpath),str(root/"regression")],env=env,check=True,timeout=900)
    replay=root/"regression/results"
    for name in ("requests","responses"):
        if gzjson(replay/f"g66b5b-{name}.json.gz")!=(requests if name=="requests" else prior):raise ValueError("G6.6b-5b replay changed")
    raw,rr=load(root/"refined",oldpin["refined"],oldpin["refinedExports"],oldpin["refinedReportSha256"],"g6-refined-report.json")
    offers=read_csv(raw["g6-refined-offers.csv.gz"]);registry={}
    for o in offers:
        sig=o["tariff_signature"];payload=json.loads(o["raw_price_payload"])
        if signature(payload)!=sig or o["raw_verified"]!="True":raise ValueError("Raw signature")
        item=(payload,o["family"],o["g6_calculability"])
        if sig in registry and registry[sig]!=item:raise ValueError("Signature conflict")
        registry[sig]=item
    if len(offers)!=24115 or len(registry)!=262:raise ValueError("Raw inventory")
    from scripts.consolidate_g6_fr_scenarios import EST
    prepared={sig:prepare(raw,family,baseline==EST,sig) for sig,(raw,family,baseline) in registry.items()}
    old_counts=collections.Counter(x["response"]["decision"] for x in prior)
    if old_counts["ENGINE_OR_ROUNDING_REVIEW"]!=385 or old_counts["PLANNER_CLOCK_OR_CALENDAR_REVIEW"]!=288 or old_counts["DATE_APPLICABILITY_REVIEW"]!=3:raise ValueError("Target count")
    engine=ROOT/"migration/v9/g6-candidate/pricing-engine.cjs";verify(engine,oldpin["candidateSha256"])
    runner=ROOT/"scripts/replay_g66b5c_clock_candidate.cjs"
    original_runner=ROOT/"scripts/replay_g66b5b_clock_candidate.cjs"
    jobs=[];pending=[];details=[];updated=[x["response"] for x in prior]
    for i,row in enumerate(prior):
        old=row["response"];q=row["request"];state=old["decision"]
        if state not in ("ENGINE_OR_ROUNDING_REVIEW","PLANNER_CLOCK_OR_CALENDAR_REVIEW","DATE_APPLICABILITY_REVIEW"):continue
        sig=q["tariff_signature"];family=registry[sig][1];s=q["session"]
        if not s["includeCongestionFees"] and old["congestionEvidence"]!=PROOF:raise ValueError("Congestion guard")
        f=planner_session(s)
        d=dict(index=i,signature=sig,family=family,previousDecision=state,decision=state,reason=state,canonical=None,segmented=None,oldEngine=None,engine=None,publicationEligible=False)
        details.append(d)
        try:
            if family=="DURATION_BASED+TIME_BASED":
                status,canonical,segmented,rules=mixed_quote(prepared[sig],s,f)
            else:
                status,canonical,segmented,rules,_=clock_quote(prepared[sig],s,f,family)
        except (ValueError,TypeError,KeyError,ArithmeticError) as ex:
            d["reason"]=str(ex);continue
        d.update(canonical=canonical,segmented=segmented,reason=status)
        if canonical is None:continue
        jobs.append(dict(signature=sig,session=s,rules=rules));pending.append(d)
    def run(path,jobs):
        out=json.loads(subprocess.run(["node",str(path),str(engine)],input=j(jobs),text=True,capture_output=True,check=True,timeout=420).stdout)
        if len(out)!=len(jobs) or any(x["signature"]!=y["signature"] for x,y in zip(out,jobs)):raise ValueError("Candidate order")
        return out
    # Direct contract witness using the actual pinned engine; never accept an
    # explicit refusal, missing total, or mismatched Decimal components.
    witness=dict(signature="contract-witness",session=dict(protocol="planner-v1",startAt="2026-11-26T12:00:00Z",timeZone="Europe/Paris",energy="1.000000",durationMinutes="1.000000",chargingMinutes="1.000000",postChargeMinutes="0.000000",includeCongestionFees=True,chargeTimeline=[dict(offsetMinutes="0.000000",durationMinutes="1.000000",energyKwh="1.000000")]),rules=[dict(scope="allDay",start="00:00",end="24:00",currency="EUR",pricePerKwh="0.5",chargePerMinute="0",idlePerMinute="0",connectionFee="0")])
    before=run(original_runner,[witness])[0];after=run(runner,[witness])[0]
    if before["complete"] is not False or not engine_agrees(dict(energy="0.5",time="0",parking="0",flat="0",total="0.5"),after):raise ValueError("Candidate contract witness")
    refused={**witness,"rules":[{**witness["rules"][0],"billing":"powerMinute"}]}
    if run(runner,[refused])[0]["complete"] is not False:raise ValueError("Explicit refusal accepted")
    old_actual=run(original_runner,jobs);actual=run(runner,jobs)
    for d,b,a in zip(pending,old_actual,actual):
        d.update(oldEngine=b,engine=a)
        canonical,segmented=d["canonical"],d["segmented"]
        if engine_agrees(canonical,a):new=result(PASS,parts=canonical,canonical=canonical)
        elif segmented is not None and explain(canonical,segmented,a):new=result(ROUNDING,parts=segmented,canonical=canonical,segmented=segmented)
        else:
            d["reason"]="CANDIDATE_COMPONENT_MISMATCH" if a["complete"] else "CANDIDATE_EXPLICIT_OR_INVALID_RESPONSE";continue
        i=d["index"];old=updated[i]
        updated[i]={**old,**new};d.update(decision=new["decision"],reason="EXACT_OR_PROVEN_SEGMENT_AGREEMENT")
    for old,new in zip(prior,updated):
        b=old["response"]
        if b["estimateEur"] is not None and b!=new:raise ValueError("Prior price changed")
        if new["publicationEligible"] or new["diagnosticOnly"] is not True:raise ValueError("Promotion")
        if new["estimateEur"] is not None and not old["request"]["session"]["includeCongestionFees"] and new["congestionEvidence"]!=PROOF:raise ValueError("Fee proof")
        if any(b.get(k)!=new.get(k) for k in ("scope","session","nationalId","congestionEvidence")):raise ValueError("Identity change")
    dest=root/"results";dest.mkdir()
    output=[dict(request=q,response=r) for q,r in zip(requests,updated)]
    for name,rows in (("diagnostics",details),("responses",output)):
        (dest/f"g66b5c-{name}.json.gz").write_bytes(gzip.compress(j(rows).encode(),mtime=0))
    transitions=collections.Counter((b["response"]["decision"],a["decision"]) for b,a in zip(prior,updated))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,productionSha=pin["productionSha"],legacyChecks=48204,priorPlannerChecks=2316,clockChecks=6948,priorRegressions=0,targetCases=len(details),candidateComparisons=len(jobs),contractWitness=dict(before=before,after=after,explicitRefusalPassed=True),before=dict(old_counts),after=dict(collections.Counter(r["decision"] for r in updated)),transitions=[dict(before=b,after=a,count=n) for (b,a),n in sorted(transitions.items())],diagnosticReasons=dict(collections.Counter(d["reason"] for d in details)),supplierCalls=0,pricesPromoted=0,identityChanges=0,published=False,runtimeActivated=False,limitations=["Candidate adapter correction only, not billing evidence","Mixed family accepted only on conservative invariant rate envelope and exact independent candidate agreement","Unresolved calendar, temporal fee classification, durable storage, other real lanes and browser remain separate","Prior lineage preserved in responses; new diagnostic report records current code"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b5c-report.json").write_text(j(report));print("G66B5C "+j(report))
if __name__=="__main__":main()
