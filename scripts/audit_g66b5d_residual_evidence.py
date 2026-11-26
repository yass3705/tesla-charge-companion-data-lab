"""G6.6b-5d offline residual evidence; no quote gate or publication change."""
import collections,gzip,json,os,pathlib,sys
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv,EST
from scripts.unify_g6_fr_dynamic import load,PASS
from scripts.g66b5a_planner_gate import planner_session,congestion_evidence,PROOF
from scripts.audit_g6_fr_segment_rounding import ROUNDING
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.evaluate_g6_fr_dynamic import prepare,DIMS
from scripts.replay_g6_fr_simple import dec,j
from scripts.replay_g6_fr_time_windows import ZONE,contains
ROOT=pathlib.Path(__file__).resolve().parents[1]
FEE="CONGESTION_EXCLUSION_NOT_PROVEN"
MIX="PLANNER_CLOCK_OR_CALENDAR_REVIEW"
SEM="INCALCULABLE_SEMANTICS"
DATE="DATE_APPLICABILITY_REVIEW"
def civil_samples(f):
    at=datetime.fromisoformat(f["startAt"]).astimezone(timezone.utc)
    end=at+timedelta(microseconds=int(dec(f["duration"])*60000000))
    t=at.replace(second=0,microsecond=0);days=set();minutes=set()
    while t<end:
        local=t.astimezone(ZONE)
        days.add(local.date());minutes.add(local.hour*60+local.minute)
        t+=timedelta(minutes=1)
    if not days:raise ValueError("Empty session")
    return days,minutes
def conservative_rates(prepared,f):
    """Over-approximate possible rates, not a billing selection.
    Include all base/unconditional rates; any lower threshold reached by
    total elapsed might apply, regardless of upper bound or actual phase.
    For temporal proof deliberately ignore date restrictions entirely.
    Clock samples include session start and every touched local minute;
    omitted components may be inherited or zero. Never infer congestion.
    """
    base,rr,_=prepared;days,minutes=civil_samples(f)
    elapsed=dec(f["duration"])*60
    possible={k:{v} for k,v in base.items()}
    for types,lo,hi,w,threshold,rates in rr:
        if threshold>elapsed:continue
        if w is not None and not any(contains(w,m) for m in minutes):continue
        for k,v in rates.items():possible[k].add(v)
        if types:
            for k in set(DIMS)-set(rates):possible[k].add(Decimal(0))
    return possible,days
def zero_temporal(possible,f):
    qty={"time":dec(f["charging"]),"parking":dec(f["parking"])}
    return all(qty[k]==0 or possible[k]=={Decimal(0)} for k in qty)
def normalized_key(q,fee=True):
    return j({**q,"session":{**q["session"],"includeCongestionFees":fee}})
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b5d_residual_evidence" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    oldpin=json.loads((ROOT/"migration/v9/g66b5c-clock-review-request.json").read_text())
    if pin["productionSha"]!=oldpin["productionSha"]:raise ValueError("Production pin")
    c=download(root/"review",pin["clockReview"],{**{k:(k,) for k in pin["clockReviewExports"]},"report":("g66b5c-report.json",)})
    for k,v in pin["clockReviewExports"].items():verify(c[k],v)
    verify(c["report"],pin["clockReviewReportSha256"]);cr=json.loads(c["report"].read_text())
    if cr["codeSha"]!=pin["clockReview"]["codeSha"] or cr["sourcePin"]!=oldpin or cr["priorRegressions"] or cr["published"] or cr["runtimeActivated"] or cr["pricesPromoted"] or cr["supplierCalls"]:raise ValueError("Prior review proof")
    b=download(root/"clock",pin["clock"],{**{k:(k,) for k in pin["clockExports"]},"report":("g66b5b-report.json",)})
    for k,v in pin["clockExports"].items():verify(b[k],v)
    verify(b["report"],pin["clockReportSha256"]);br=json.loads(b["report"].read_text())
    if br["codeSha"]!=pin["clock"]["codeSha"] or br["legacyRegressions"] or br["priorPlannerRegressions"] or br["published"] or br["pricesPromoted"]:raise ValueError("Clock proof")
    old=gzjson(b["g66b5b-responses.json.gz"]);rows=gzjson(c["g66b5c-responses.json.gz"]);diagnostics=gzjson(c["g66b5c-diagnostics.json.gz"])
    reqs=gzjson(b["g66b5b-requests.json.gz"])
    if len(old)!=6948 or len(rows)!=6948 or len(reqs)!=6948 or len({j(x) for x in reqs})!=6948 or len(diagnostics)!=676:raise ValueError("Coverage")
    if any(x["request"]!=y["request"] or x["request"]!=q for x,y,q in zip(old,rows,reqs)):raise ValueError("Request mutation")
    if any(x!=y for x,y in zip(old,rows) if x["response"]["estimateEur"] is not None):raise ValueError("Prior price mutation")
    if sum(x["response"]["estimateEur"] is not None for x in old)!=4029:raise ValueError("Old coverage")
    counts=collections.Counter(x["response"]["decision"] for x in rows)
    if counts!={PASS:4546,FEE:1698,SEM:545,MIX:156,DATE:3}:raise ValueError("Current coverage")
    if any(x["response"]["publicationEligible"] or x["response"]["diagnosticOnly"] is not True for x in rows):raise ValueError("Publication")
    raw,rr=load(root/"refined",pin["refined"],pin["refinedExports"],pin["refinedReportSha256"],"g6-refined-report.json")
    offers=read_csv(raw["g6-refined-offers.csv.gz"]);registry={};weights=collections.Counter()
    for o in offers:
        sig=o["tariff_signature"];payload=json.loads(o["raw_price_payload"])
        if signature(payload)!=sig or o["raw_verified"]!="True":raise ValueError("Raw signature")
        item=(payload,o["family"],o["g6_calculability"])
        if sig in registry and registry[sig]!=item:raise ValueError("Signature conflict")
        registry[sig]=item;weights[sig]+=1
    if len(offers)!=24115 or len(registry)!=262 or len({o["national_id"] for o in offers})!=24115 or len({o["source_id"] for o in offers})!=24115:raise ValueError("Identity coverage")
    verify(ROOT/"migration/v9/g6-candidate/pricing-engine.cjs",pin["candidateSha256"])
    prep={sig:prepare(raw,family,baseline==EST,sig) for sig,(raw,family,baseline) in registry.items()}
    fee_proofs={sig:congestion_evidence(raw) for sig,(raw,family,baseline) in registry.items()}
    inventory=[]
    for sig,(raw,family,_) in sorted(registry.items()):
        base,rr,_=prep[sig]
        positive=[dict(rule="base",component=k,rate=str(v)) for k,v in base.items() if k in ("time","parking") and v>0]
        for n,(types,lo,hi,w,threshold,rates) in enumerate(rr):
            positive.extend(dict(rule=n,component=k,rate=str(v),types=sorted(types),minDurationSeconds=threshold,clock=w,startDate=str(lo) if lo else None,endDate=str(hi) if hi else None) for k,v in rates.items() if k in ("time","parking") and v>0)
        if bool(positive)!=(fee_proofs[sig]!=PROOF):raise ValueError("Fee inventory proof")
        inventory.append(dict(signature=sig,family=family,identities=weights[sig],evidence=fee_proofs[sig],positiveTemporalComponents=positive,congestionExplicitlyIdentified=False))
    paired={}
    for i,x in enumerate(rows):
        k=normalized_key(x["request"],x["request"]["session"]["includeCongestionFees"])
        if k in paired:raise ValueError("Duplicate session")
        paired[k]=(i,x["response"])
    if len(paired)!=6948:raise ValueError("Pair coverage")
    details=[];hypotheses=[];reasons=collections.Counter()
    for i,x in enumerate(rows):
        q=x["request"];r=x["response"];decision=r["decision"];sig=q["tariff_signature"]
        if sig not in registry or r.get("congestionEvidence")!=fee_proofs[sig]:raise ValueError("Fee lineage")
        if r["estimateEur"] is not None:continue
        f=planner_session(q["session"]);possible,days=conservative_rates(prep[sig],f)
        qty=dict(energy=dec(f["energy"]),time=dec(f["charging"]),parking=dec(f["parking"]),flat=Decimal(1))
        conflicts={k:sorted(str(v) for v in possible[k]) for k in DIMS if qty[k]!=0 and len(possible[k])>1}
        d=dict(index=i,signature=sig,family=registry[sig][1],decision=decision,reason=decision,conflictingRates=conflicts,localDates=sorted(map(str,days)),publicationEligible=False)
        if decision==FEE:
            other_i,other=paired[normalized_key(q,True)]
            d["includedIndex"]=other_i;d["includedDecision"]=other["decision"]
            if other["estimateEur"] is None:d["reason"]="INCLUDED_QUOTE_UNRESOLVED"
            elif other["decision"] not in (PASS,ROUNDING):raise ValueError("Unproved included quote")
            elif any(dec(other["components"][k])!=0 for k in ("time","parking")):d["reason"]="POSITIVE_TEMPORAL_AMOUNT_UNCLASSIFIED"
            elif not zero_temporal(possible,f):d["reason"]="ZERO_RESULT_BUT_POSITIVE_RATE_POSSIBLE"
            else:
                d["reason"]="ARCHIVED_SESSION_ZERO_TEMPORAL_PROOF_CANDIDATE"
                hypotheses.append(dict(index=i,includedIndex=other_i,signature=sig,archivedEstimateEur=other["estimateEur"],potentialRates={k:sorted(str(v) for v in possible[k]) for k in ("time","parking")},durationMinutes=str(qty["time"]),parkingMinutes=str(qty["parking"]),diagnosticOnly=True,publicationEligible=False,quoteGateChanged=False))
        elif decision==DATE:
            dated=[(lo,hi) for types,lo,hi,w,t,rates in prep[sig][1] if "DATE_BASED" in types]
            if not dated:raise ValueError("Date rule missing")
            d["dateBounds"]=[dict(start=str(lo) if lo else None,end=str(hi) if hi else None) for lo,hi in dated]
            d["uncoveredDates"]=sorted(str(day) for day in days if not any((lo is None or day>=lo) and (hi is None or day<hi) for lo,hi in dated))
            d["reason"]="DATE_OUTSIDE_ARCHIVED_VALIDITY" if d["uncoveredDates"] else "DATE_MODEL_REVIEW"
        elif decision in (MIX,SEM):
            d["reason"]="MULTIPLE_REACHABLE_COMPONENT_RATES" if conflicts else "SEMANTIC_EVIDENCE_STILL_REQUIRED"
        else:raise ValueError("Unexpected refusal")
        reasons[d["reason"]]+=1;details.append(d)
    if len(details)!=2402 or len({d["index"] for d in details})!=2402 or sum(reasons.values())!=2402:raise ValueError("Residual coverage")
    if sum(x["response"]["estimateEur"] is not None for x in rows)!=4546:raise ValueError("Accepted coverage")
    if len(hypotheses)>198:raise ValueError("Unexpected candidate expansion")
    dest=root/"results";dest.mkdir()
    for name,value in (("residuals",details),("fee-inventory",inventory),("zero-temporal-candidates",hypotheses)):
        (dest/f"g66b5d-{name}.json.gz").write_bytes(gzip.compress(j(value).encode(),mtime=0))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,productionSha=pin["productionSha"],checks=len(rows),priorPricedPreserved=4546,priorRegressions=0,residualCount=len(details),reasons=dict(reasons),feeSignatureCount=sum(i["evidence"]!=PROOF for i in inventory),feeIdentityCount=sum(i["identities"] for i in inventory if i["evidence"]!=PROOF),residualSignatures={k:len({d["signature"] for d in details if d["decision"]==k}) for k in (FEE,SEM,MIX,DATE)},sessionZeroTemporalCandidates=len(hypotheses),candidateCoverageIfLaterApproved=4546+len(hypotheses),quoteGateChanged=False,pricesPromoted=0,supplierCalls=0,identityChanges=0,published=False,runtimeActivated=False,limitations=["Archived fields do not distinguish congestion from ordinary TIME/PARKING_TIME; no positive amount removed","Session-zero candidates are evidence only, not quotes or a new exclusion policy; external charges not proved","Rate sets deliberately over-approximate and never settle precedence; calendar gaps remain refused","No new provider call, browser integration, real other-lane replay or durable storage"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    (dest/"g66b5d-report.json").write_text(j(report));print("G66B5D "+j(report))
if __name__=="__main__":main()
