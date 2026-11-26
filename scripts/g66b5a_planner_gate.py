"""G6.6b-5a: exact planner transport, conservative archived-fee proof.
Never infer congestion from parking/time or accept variable-rate energy allocation.
Fractional unrestricted and duration-only tariffs use Decimal envelope and pinned
historical engine, no change to legacy whole-second gate or raw signatures."""
import collections,json,re,subprocess
from datetime import datetime
from decimal import Decimal,ROUND_HALF_UP
from scripts.g66b3_quote_gate import ROOT,SCOPE,result
from scripts.audit_g6_fr_electroverse import parse_components,DIMENSIONS
from scripts.audit_irve_g5_power_scope import verify
from scripts.replay_g6_fr_simple import dec,j,Q
from scripts.evaluate_g6_fr_dynamic import DIMS,historical_rules
from scripts.unify_g6_fr_dynamic import PASS,engine_agrees

PROOF="NO_POSITIVE_TEMPORAL_COMPONENT_IN_ARCHIVED_SIGNATURE"
PLANNER_FIELDS=("protocol","startAt","timeZone","energy","durationMinutes","chargingMinutes","postChargeMinutes","includeCongestionFees","chargeTimeline")
STEP_FIELDS=("offsetMinutes","durationMinutes","energyKwh")
ALLOWED_FAMILIES={"NO_DECLARED_RESTRICTIONS","DURATION_BASED"}
def fixed(v):
    if not isinstance(v,str) or not re.fullmatch(r"[0-9]+\.[0-9]{6}",v):raise ValueError("PLANNER_DECIMAL_PRECISION")
    x=dec(v)
    if not x.is_finite() or x<0:raise ValueError("PLANNER_DECIMAL_INVALID")
    return x
def planner_session(s):
    if not isinstance(s,dict) or set(s)!=set(PLANNER_FIELDS) or s["protocol"]!="planner-v1" or s["timeZone"]!="Europe/Paris" or type(s["includeCongestionFees"]) is not bool:raise ValueError("PLANNER_FIELDS_INVALID")
    if not isinstance(s["startAt"],str) or not re.search(r"(?:Z|[+-]\d{2}:\d{2})$",s["startAt"]):raise ValueError("PLANNER_OFFSET_REQUIRED")
    at=datetime.fromisoformat(s["startAt"])
    if at.utcoffset() is None:raise ValueError("PLANNER_OFFSET_REQUIRED")
    duration,charging,parking,energy=(fixed(s[k]) for k in ("durationMinutes","chargingMinutes","postChargeMinutes","energy"))
    if not 0<duration<=10080 or abs(duration-charging-parking)>Q or (charging==0 and energy!=0):raise ValueError("PLANNER_DURATION_INVALID")
    steps=s["chargeTimeline"]
    if not isinstance(steps,list) or len(steps)>2048 or bool(steps)!=(charging>0):raise ValueError("PLANNER_TIMELINE_REQUIRED")
    previous=Decimal(0);last_offset=None;total=Decimal(0)
    for i,step in enumerate(steps):
        if not isinstance(step,dict) or set(step)!=set(STEP_FIELDS):raise ValueError("PLANNER_STEP_FIELDS")
        offset,length,e=(fixed(step[k]) for k in STEP_FIELDS)
        if length<=0 or (i==0 and offset!=0) or (last_offset is not None and offset<=last_offset) or abs(offset-previous)>Q:raise ValueError("PLANNER_TIMELINE_GAP_OR_OVERLAP")
        previous=offset+length;last_offset=offset;total+=e
    # Planner rounds each independently emitted six-decimal step and total.
    # This is solely a representation-coherence guard, not a price tolerance.
    # For the invariant-rate envelope only, use the authoritative session energy.
    if abs(previous-charging)>Q or abs(total-energy)>(len(steps)+1)*Q/2:raise ValueError("PLANNER_TIMELINE_TOTAL_MISMATCH")
    return dict(id="planner",startAt=s["startAt"],duration=str(duration),charging=str(charging),parking=str(parking),energy=str(energy))

def congestion_evidence(raw):
    """Prove absence only within the archived fields, not external network fees."""
    if not isinstance(raw,dict) or set(raw)!={"isChargingFree","priceComponents","complexPricingDetail"} or type(raw["isChargingFree"]) is not bool:return "UNKNOWN_RAW_SCHEMA"
    cx=raw["complexPricingDetail"]
    if not isinstance(cx,dict) or set(cx)!={"currency","restrictions"} or cx["currency"]!="EUR" or not isinstance(cx["restrictions"],list):return "UNKNOWN_RAW_SCHEMA"
    items=[raw["priceComponents"]]
    for r in cx["restrictions"]:
        if not isinstance(r,dict) or set(r)!={"dateRestrictions","durationRestrictions","priceComponents","restrictionTypes","timeRestrictions","weekdayRestrictions"}:return "UNKNOWN_RAW_SCHEMA"
        items.append(r["priceComponents"])
    temporal=False
    for i,components in enumerate(items):
        if not isinstance(components,list) or any(not isinstance(c,dict) or set(c)!={"__typename","formattedValue"} for c in components):return "UNKNOWN_RAW_SCHEMA"
        rates,errors=parse_components(components,"PROOF")
        if errors or (i==0 and set(rates)!={x[0] for x in DIMENSIONS.values()}):return "UNKNOWN_RAW_SCHEMA"
        temporal|=any(rates.get(k,Decimal(0))>0 for k in ("time","parking"))
    return "TEMPORAL_COMPONENT_NOT_CLASSIFIED_AS_CONGESTION" if temporal else PROOF

def invariant_envelope(prepared,f,family):
    """Extension of established envelope to exact fractional minutes.
    Only unrestricted/duration-only families. No calendar/window shortcuts."""
    if family not in ALLOWED_FAMILIES:return "PLANNER_CLOCK_OR_CALENDAR_REVIEW",None
    base,rr,_=prepared;elapsed=dec(f["duration"])*60
    possible={k:{v} for k,v in base.items()}
    for types,lo,hi,w,threshold,rates in rr:
        if types-{"DURATION_BASED"} or lo is not None or hi is not None or w is not None:raise ValueError("Unproved tariff restrictions")
        if threshold>elapsed:continue
        for k,v in rates.items():possible[k].add(v)
        if types:
            for k in set(DIMS)-set(rates):possible[k].add(Decimal(0))
    qty=dict(energy=dec(f["energy"]),time=dec(f["charging"]),parking=dec(f["parking"]),flat=Decimal(1))
    if any(len(possible[k])!=1 and qty[k]!=0 for k in DIMS):return "INCALCULABLE_SEMANTICS",None
    parts={k:(min(possible[k])*qty[k]).quantize(Q,rounding=ROUND_HALF_UP) for k in DIMS}
    return "DIAGNOSTIC_RATE_AGREEMENT",{**{k:str(v) for k,v in parts.items()},"total":str(sum(parts.values()))}

class PlannerGate:
    def __init__(self,legacy,lineage):
        self.legacy=legacy;self.lineage=dict(lineage)
        self.evidence={sig:congestion_evidence(item["raw"]) for sig,item in legacy.registry.items()}
    def quote(self,requests):
        verify(self.legacy.engine,self.lineage["candidateSha256"])
        results=[];pending={};jobs={};oracles={}
        for i,r in enumerate(requests):
            if not isinstance(r,dict) or set(r)!=set(("country","channel","session",*SCOPE)) or r["country"]!="FR" or r["channel"]!="Electroverse" or any(not isinstance(r[k],str) for k in SCOPE):
                results.append(result("SCOPE_REFUSED","REQUEST_FIELDS_OR_COUNTRY_INVALID"));continue
            p=self.legacy.bound.get(r["nationalConnectorKey"])
            if p is None or any(r[k]!=p[k] for k in SCOPE):
                results.append(result("SCOPE_REFUSED","IDENTITY_OR_SIGNATURE_MISMATCH"));continue
            sig=p["tariff_signature"];proof=self.evidence[sig]
            envelope=dict(scope={k:r[k] for k in SCOPE},session=r["session"],nationalId=p["national_id"],lineage=self.lineage,congestionEvidence=proof)
            try:f=planner_session(r["session"])
            except (ValueError,TypeError,KeyError,ArithmeticError) as ex:
                results.append(dict(result("SESSION_REFUSED",str(ex)),**envelope));continue
            if not r["session"]["includeCongestionFees"] and proof!=PROOF:
                results.append(dict(result("CONGESTION_EXCLUSION_NOT_PROVEN","CONGESTION_EXCLUSION_NOT_PROVEN"),**envelope));continue
            family=self.legacy.registry[sig]["family"]
            # Exact timeline is part of every request/response; arithmetic sharing
            # is safe only when the invariant-rate envelope has been established.
            key=(sig,j(f))
            if key not in oracles:
                try:state,parts=invariant_envelope(self.legacy.prepared[sig],f,family)
                except (ValueError,TypeError,KeyError,ArithmeticError) as ex:state,parts="MODEL_REVIEW",None
                if parts is None:oracles[key]=result(state,state)
                else:
                    rules=historical_rules(self.legacy.prepared[sig],f,family)
                    jobs[key]=dict(signature=sig,fixture=f,rules=rules)
                    oracles[key]=parts
            pending[i]=(key,envelope);results.append(None)
        if jobs:
            runner=ROOT/"scripts/replay_g6_fr_combined_windows_engine.cjs"
            response=json.loads(subprocess.run(["node",str(runner),str(self.legacy.engine)],input=j(list(jobs.values())),text=True,capture_output=True,check=True,timeout=240).stdout)
            if len(response["results"])!=len(jobs) or len(response["guards"])!=4 or not all(response["guards"].values()):raise ValueError("Candidate guard failure")
            for key,actual in zip(jobs,response["results"]):
                if actual["signature"]!=key[0] or actual["scenario"]!="planner":raise ValueError("Candidate response ordering")
                parts=oracles[key]
                oracles[key]=result(PASS,parts=parts,canonical=parts) if engine_agrees(parts,actual) else result("ENGINE_OR_ROUNDING_REVIEW","ENGINE_OR_ROUNDING_REVIEW")
        for i,(key,envelope) in pending.items():results[i]=dict(oracles[key],**envelope)
        return results,len(jobs)
