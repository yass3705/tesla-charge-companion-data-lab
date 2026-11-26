"""G6.6b-5e isolated dynamic gate. No HTTP, supplier or publication.
New zero-temporal evidence applies only to the exact validated session and
archived components. Never infer absence of an external charge.
"""
import json,subprocess
from scripts.g66b5b_clock_gate import ClockPlannerGate,clock_quote
from scripts.audit_g66b5c_clock_review import mixed_quote
from scripts.audit_g66b5d_residual_evidence import conservative_rates,zero_temporal,FEE,MIX,DATE
from scripts.g66b5a_planner_gate import planner_session
from scripts.g66b3_quote_gate import ROOT,result
from scripts.audit_g6_fr_segment_rounding import explain,ROUNDING
from scripts.unify_g6_fr_dynamic import PASS,engine_agrees
from scripts.audit_irve_g5_power_scope import verify
from scripts.replay_g6_fr_simple import dec,j
ZERO="NO_POSITIVE_TEMPORAL_AMOUNT_PROVEN_FOR_EXACT_ARCHIVED_SESSION"
UNCLASSIFIED="TEMPORAL_COMPONENT_NOT_CLASSIFIED_AS_CONGESTION"
def zero_result(included,original,possible,f):
    """No new price calculation or subtraction: reuse the exact included
    calculation only when every applicable temporal rate is proved zero (or
    its phase has zero duration) and every result component agrees.
    """
    if original["decision"]!=FEE or original.get("congestionEvidence")!=UNCLASSIFIED:return None
    if not zero_temporal(possible,f):return None
    if included.get("decision") not in (PASS,ROUNDING) or included.get("estimateEur") is None:return None
    if included.get("publicationEligible") is not False or included.get("diagnosticOnly") is not True:return None
    if any(original.get(k)!=included.get(k) for k in ("scope","nationalId","lineage","congestionEvidence")):return None
    s=original["session"]
    if s.get("includeCongestionFees") is not False or included.get("session")!={**s,"includeCongestionFees":True}:return None
    parts=included.get("components")
    if not isinstance(parts,dict) or any(dec(parts[k])!=0 for k in ("time","parking")):return None
    return {**included,"session":s,"congestionEvidence":ZERO,"reason":"ARCHIVED_EXACT_SESSION_ZERO_TEMPORAL_COMPONENTS"}
class DynamicPlannerGate(ClockPlannerGate):
    def repaired(self,requests):
        """Recompute 5c logic on any valid session; no replay allow-list."""
        out,n=super().quote(requests);jobs={};pending={};models={}
        for i,(q,r) in enumerate(zip(requests,out)):
            if r["decision"] not in ("ENGINE_OR_ROUNDING_REVIEW",MIX,DATE):continue
            sig=q["tariff_signature"];family=self.legacy.registry[sig]["family"];s=q["session"]
            key=(sig,j(s))
            if key not in models:
                try:
                    f=planner_session(s)
                    if family=="DURATION_BASED+TIME_BASED":state,canonical,segmented,rules=mixed_quote(self.legacy.prepared[sig],s,f)
                    else:state,canonical,segmented,rules,_=clock_quote(self.legacy.prepared[sig],s,f,family)
                except (ValueError,TypeError,KeyError,ArithmeticError):canonical=None
                models[key]=(canonical,segmented) if canonical is not None else (None,None)
                if canonical is not None:jobs[key]=dict(signature=sig,session=s,rules=rules)
            if key in jobs:pending[i]=key
        if jobs:
            verify(self.legacy.engine,self.lineage["candidateSha256"])
            actual=json.loads(subprocess.run(["node",str(ROOT/"scripts/replay_g66b5c_clock_candidate.cjs"),str(self.legacy.engine)],input=j(list(jobs.values())),text=True,capture_output=True,check=True,timeout=420).stdout)
            if len(actual)!=len(jobs) or any(a["signature"]!=k[0] for k,a in zip(jobs,actual)):raise ValueError("Candidate ordering")
            resolved={}
            for key,a in zip(jobs,actual):
                canonical,segmented=models[key]
                if engine_agrees(canonical,a):resolved[key]=result(PASS,parts=canonical,canonical=canonical)
                elif segmented is not None and explain(canonical,segmented,a):resolved[key]=result(ROUNDING,parts=segmented,canonical=canonical,segmented=segmented)
            for i,key in pending.items():
                if key in resolved:out[i]={**out[i],**resolved[key]}
        return out,n+len(jobs)
    def quote(self,requests):
        out,n=self.repaired(requests)
        included=[];pending=[]
        for i,(q,r) in enumerate(zip(requests,out)):
            if r["decision"]!=FEE or r.get("congestionEvidence")!=UNCLASSIFIED:continue
            try:
                f=planner_session(q["session"])
                possible,_=conservative_rates(self.legacy.prepared[q["tariff_signature"]],f)
                if not zero_temporal(possible,f):continue
            except (ValueError,TypeError,KeyError,ArithmeticError):continue
            included.append({**q,"session":{**q["session"],"includeCongestionFees":True}})
            pending.append((i,possible,f))
        if included:
            quotes,m=self.repaired(included);n+=m
            if len(quotes)!=len(pending):raise ValueError("Included coverage")
            for (i,possible,f),inc in zip(pending,quotes):
                new=zero_result(inc,out[i],possible,f)
                if new is not None:out[i]=new
        return out,n
