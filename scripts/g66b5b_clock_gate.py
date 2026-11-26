"""Clock/date extension of the isolated planner gate. No billing-certification claim.
Use actual piecewise planner energy. All previously plausible billing models
must agree; the pinned JS candidate independently selects rules and prices
its own segments. No fallback to uniform full-session energy."""
import collections,itertools,json,subprocess
from datetime import datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP
from scripts.g66b5a_planner_gate import PlannerGate,planner_session,PROOF
from scripts.g66b3_quote_gate import ROOT,SCOPE,result
from scripts.replay_g6_fr_simple import dec,j,Q
from scripts.replay_g6_fr_time_windows import ZONE,contains,rules_for
from scripts.replay_g6_fr_date_windows import snapshot,active,engine_rules
from scripts.refine_g6_fr_dynamic import FAMILIES
from scripts.evaluate_g6_fr_dynamic import DIMS
from scripts.unify_g6_fr_dynamic import PASS,engine_agrees
from scripts.audit_irve_g5_power_scope import verify
from scripts.audit_g6_fr_segment_rounding import explain,ROUNDING

MINUTE=60000000
def us(v):return int(dec(v)*MINUTE)
def quant(v):return v.quantize(Q,rounding=ROUND_HALF_UP)
def format_parts(parts):
    parts={k:quant(v) for k,v in parts.items()}
    return {**{k:str(v) for k,v in parts.items()},"total":str(sum(parts.values()))}
def start_us(at):
    delta=at-datetime(1970,1,1,tzinfo=timezone.utc)
    return (delta.days*86400+delta.seconds)*1000000+delta.microseconds
def timeline(s,f):
    """Use rounded cumulative offsets as interval boundaries; not a new curve.
    If aggregate energy or occupancy is not exact, don't allocate discrepancy."""
    c,p,t=map(us,(f["charging"],f["parking"],f["duration"]))
    if c+p!=t:raise ValueError("PLANNER_CLOCK_DURATION_RECONCILIATION_REQUIRED")
    steps=s["chargeTimeline"]
    offsets=[us(x["offsetMinutes"]) for x in steps]+[c]
    energies=[dec(x["energyKwh"]) for x in steps]
    if sum(energies,Decimal(0))!=dec(f["energy"]):raise ValueError("PLANNER_CLOCK_ENERGY_RECONCILIATION_REQUIRED")
    if any(b<=a for a,b in zip(offsets,offsets[1:])):raise ValueError("PLANNER_CLOCK_INTERVAL_INVALID")
    return [(a,b,e) for a,b,e in zip(offsets,offsets[1:],energies)],c,p,t

def spans(s,f):
    steps,c,p,t=timeline(s,f)
    at=datetime.fromisoformat(f["startAt"]).astimezone(timezone.utc)
    epoch=start_us(at);bounds={0,t,c}
    for a,b,e in steps:bounds.update((a,b))
    bounds.update(range(MINUTE-epoch%MINUTE,t,MINUTE))
    bs=sorted(bounds);out=[];i=0
    for a,b in zip(bs,bs[1:]):
        if b<=a:continue
        local=(at+timedelta(microseconds=a)).astimezone(ZONE)
        energy=Decimal(0)
        if a<c:
            while i<len(steps) and a>=steps[i][1]:i+=1
            if i>=len(steps) or not steps[i][0]<=a<b<=steps[i][1]:raise ValueError("Timeline interval missing")
            x,y,e=steps[i];energy=e*dec(b-a)/dec(y-x)
        out.append((a,b,local.date(),local.hour*60+local.minute,energy,dec(b-a)/MINUTE if a<c else Decimal(0),dec(b-a)/MINUTE if a>=c else Decimal(0)))
    return out

def clock_quote(prepared,s,f,family):
    """Same model alternatives as G6.4c, now with actual segment energy.
    Historical start-date exclusive snapshot + dynamic clock is the JS reference."""
    if family not in FAMILIES:raise ValueError("Clock family")
    rows=spans(s,f)
    day0,m0=rows[0][2:4];_,_,compiled=prepared
    if family=="TIME_BASED":
        base,hist,_,windows=compiled
        variants=itertools.product(("base","historical"),(False,True),(False,True))
        def pick(v,day,m):
            seed,replace,locked=v; rates=base if seed=="base" else hist
            matches=[r for w,r in windows.items() if contains(w,m0 if locked else m)]
            if len(matches)>1:raise ValueError("Overlapping window")
            return rates if not matches else {**({k:Decimal(0) for k in DIMS} if replace else rates),**matches[0]}
        reference=rules_for(hist,windows)
        ref=("historical",False,False)
    else:
        base,rules=compiled
        if any(not any(active(r,d) for r in rules if r[0] is not None or r[1] is not None) for d in {x[2] for x in rows}):
            return "DATE_APPLICABILITY_REVIEW",None,None,None,{}
        variants=itertools.product(("snapshot","dynamic"),(False,True),(False,True),(False,True))
        cache={}
        def pick(v,day,m):
            mode,inclusive,replace,locked=v;d=day0 if mode=="snapshot" else day
            if (d,inclusive) not in cache:cache[d,inclusive]=snapshot(base,rules,d,inclusive)
            hist,windows=cache[d,inclusive]
            matches=[r for w,r in windows.items() if contains(w,m0 if locked else m)]
            if len(matches)>1:raise ValueError("Overlapping window")
            return hist if not matches else {**({k:Decimal(0) for k in DIMS} if replace else hist),**matches[0]}
        reference=engine_rules(*snapshot(base,rules,day0))
        ref=("snapshot",False,False,False)
    models={};segmented=None
    for v in variants:
        parts={k:Decimal(0) for k in DIMS}
        segments=[]
        for a,b,day,m,e,c,p in rows:
            rates=pick(v,day,m)
            qty={"energy":e,"time":c,"parking":p,"flat":Decimal(int(a==0))}
            current={k:qty[k]*rates[k] for k in DIMS}
            for k,value in current.items():parts[k]+=value
            if v==ref:
                # Match contiguous selected rule runs, including phase/curve
                # changes without rounding each little step.
                from scripts.audit_g6_fr_segment_rounding import select
                idx=select(reference,m)
                if segments and segments[-1][0]==idx:
                    for k,value in current.items():segments[-1][1][k]+=value
                else:segments.append((idx,current.copy()))
        models[j(v)]=format_parts(parts)
        if v==ref:
            sums={k:sum((quant(x[1][k]) for x in segments),Decimal(0)) for k in DIMS}
            segmented=format_parts(sums)
    if len({j(x) for x in models.values()})!=1:return "INCALCULABLE_SEMANTICS",None,None,None,models
    return "MODEL_AGREEMENT",next(iter(models.values())),segmented,reference,models

class ClockPlannerGate(PlannerGate):
    def quote(self,requests):
        verify(self.legacy.engine,self.lineage["candidateSha256"])
        base_indices=[];base_requests=[];out=[None]*len(requests)
        jobs={};pending={};oracles={}
        for i,r in enumerate(requests):
            # Delegate all legacy validation and non-clock behavior unchanged.
            if not isinstance(r,dict) or set(r)!=set(("country","channel","session",*SCOPE)) or r["country"]!="FR" or r["channel"]!="Electroverse" or any(not isinstance(r[k],str) for k in SCOPE):
                base_indices.append(i);base_requests.append(r);continue
            p=self.legacy.bound.get(r["nationalConnectorKey"])
            if p is None or any(r[k]!=p[k] for k in SCOPE):
                base_indices.append(i);base_requests.append(r);continue
            sig=p["tariff_signature"];family=self.legacy.registry[sig]["family"];proof=self.evidence[sig]
            if family not in FAMILIES or not isinstance(r["session"],dict) or (r["session"].get("includeCongestionFees") is False and proof!=PROOF):
                base_indices.append(i);base_requests.append(r);continue
            envelope=dict(scope={k:r[k] for k in SCOPE},session=r["session"],nationalId=p["national_id"],lineage=self.lineage,congestionEvidence=proof)
            try:f=planner_session(r["session"])
            except (ValueError,TypeError,KeyError,ArithmeticError) as ex:
                out[i]=dict(result("SESSION_REFUSED",str(ex)),**envelope);continue
            key=(sig,j(r["session"])) # all curve steps retained in the key
            if key not in oracles:
                try:state,canonical,segmented,rules,models=clock_quote(self.legacy.prepared[sig],r["session"],f,family)
                except (ValueError,TypeError,KeyError,ArithmeticError) as ex:
                    state,canonical,segmented,rules,models=str(ex),None,None,None,{}
                if canonical is None:oracles[key]=result(state,state)
                else:
                    jobs[key]=dict(signature=sig,session=r["session"],rules=rules)
                    oracles[key]=(canonical,segmented)
            pending[i]=(key,envelope)
        base,n=super().quote(base_requests)
        for i,q in zip(base_indices,base):out[i]=q
        if jobs:
            runner=ROOT/"scripts/replay_g66b5b_clock_candidate.cjs"
            actual=json.loads(subprocess.run(["node",str(runner),str(self.legacy.engine)],input=j(list(jobs.values())),text=True,capture_output=True,check=True,timeout=420).stdout)
            if len(actual)!=len(jobs):raise ValueError("Clock candidate coverage")
            for key,ref in zip(jobs,actual):
                if ref["signature"]!=key[0]:raise ValueError("Clock candidate order")
                canonical,segmented=oracles[key]
                if engine_agrees(canonical,ref):oracles[key]=result(PASS,parts=canonical,canonical=canonical)
                elif explain(canonical,segmented,ref):oracles[key]=result(ROUNDING,parts=segmented,canonical=canonical,segmented=segmented)
                else:oracles[key]=result("ENGINE_OR_ROUNDING_REVIEW","ENGINE_OR_ROUNDING_REVIEW")
        for i,(key,envelope) in pending.items():out[i]=dict(oracles[key],**envelope)
        if any(x is None for x in out):raise ValueError("Missing quote")
        return out,n+len(jobs)
