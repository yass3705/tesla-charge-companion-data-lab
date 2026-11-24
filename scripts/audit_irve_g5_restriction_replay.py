#!/usr/bin/env python3
"""Offline G5 restriction replay, not a G6 evaluator or matching rule."""
import collections
import copy
import json
import pathlib
import re
import sys
from scripts import audit_irve_g5_tariff_schema as schema
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import rows,pair,table

ALIASES={"DURATION_BASED":"DURATION","TIME_BASED":"TIME"}
FIELDS={"durationRestrictions","timeRestrictions"}
RECOGNIZED="DIRECT_CONDITIONAL_NO_OBSERVED_POWER_CONDITION"

def clock(value, end=False):
    if not isinstance(value,str):return None
    m=re.fullmatch(r"(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?",value)
    if not m:return None
    h,minute,sec=map(int,(m[1],m[2],m[3] or "0"))
    if h>=24 or minute>=60 or sec>=60:return None
    # Exact integer/fraction comparison without floating point rounding.
    from decimal import Decimal
    return Decimal(h*3600+minute*60+sec)+Decimal("0."+ (m[4] or "0"))

def normalize(c):
    normalized=copy.deepcopy(c)
    cx=normalized.get("complexPricingDetail")
    issues=set(); detail=[]
    if not isinstance(cx,dict) or not isinstance(cx.get("restrictions"),list):
        return normalized,issues,detail
    for idx,r in enumerate(cx["restrictions"]):
        if not isinstance(r,dict):continue
        kinds=r.get("restrictionTypes")
        tokens=kinds if isinstance(kinds,list) else []
        mapped=[ALIASES.get(t,t) if isinstance(t,str) else t for t in tokens]
        if isinstance(kinds,list):r["restrictionTypes"]=mapped
        for field in sorted(FIELDS):
            declared=[t for t in mapped if isinstance(t,str) and schema.TYPE_MAP.get(t.upper())==field]
            v=r.get(field)
            if not declared and v is None:continue
            local=set(); notes=[]
            if len(declared)!=1:local.add("TYPE_FIELD_CARDINALITY")
            if not isinstance(v,dict):
                local.add("MISSING_OR_INVALID_FIELD")
            else:
                if any(k not in schema.RESTRICTIONS[field]|{"__typename"} and x is not None for k,x in v.items()):
                    local.add("UNKNOWN_RESTRICTION_FIELD")
                if field=="durationRestrictions":
                    lo,hi=v.get("minDurationSeconds"),v.get("maxDurationSeconds")
                    if lo is None and hi is None:local.add("MISSING_DURATION_BOUNDS")
                    for x in (lo,hi):
                        if x is not None and (type(x) is not int or x<0):
                            local.add("INVALID_DURATION_SECONDS")
                    if type(lo) is int and type(hi) is int and lo>=hi:local.add("NON_INCREASING_DURATION_BOUNDS")
                    notes.append("SECONDS; OPEN_BOUND_IF_NULL; G6_BOUNDARY_AND_BILLING_CLOCK_UNPROVEN")
                else:
                    lo,hi=clock(v.get("startTime")),clock(v.get("endTime"))
                    if lo is None or hi is None:local.add("INVALID_OR_MISSING_CLOCK_BOUND")
                    elif lo==hi:local.add("EQUAL_CLOCK_BOUNDS_AMBIGUOUS")
                    elif hi<lo:notes.append("OVERNIGHT_WINDOW; G6_WRAP_SEMANTICS_UNPROVEN")
                    else:notes.append("ASCENDING_CLOCK_WINDOW; G6_TIMEZONE_AND_BOUNDARIES_UNPROVEN")
            if not isinstance(kinds,list):local.add("INVALID_TYPE_LIST")
            detail.append({"index":idx,"field":field,"rawTypes":tokens,"normalizedTypes":mapped,
                "rawValue":v,"issues":sorted(local),"notes":notes})
            issues.update(field+":"+x for x in local)
    return normalized,issues,detail

def classify(c):
    normalized,extra,_=normalize(c)
    result,issues,dims,conds,_=schema.classify(normalized)
    raw=schema.classify(c)[4]
    issues=sorted(set(issues)|extra)
    if extra and result!="POWER_CONDITION_REVIEW":result="UNKNOWN_OR_CONFLICTING_SCHEMA_REVIEW"
    return result,issues,dims,conds,raw

def details(c):
    _,_,d=normalize(c)
    return {"restriction_diagnostics":json.dumps(d,ensure_ascii=False,sort_keys=True)}

def compare(out, previous, pin):
    before=rows(previous["pairs.csv.gz"]);after=rows(out/"schema-pairs.csv.gz")
    bm={pair(r):r for r in before};am={pair(r):r for r in after}
    if len(before)!=1317 or len(after)!=1317 or len(bm)!=1317 or set(bm)!=set(am):
        raise ValueError("Residual cohort changed")
    transitions=collections.Counter();candidates=[];reasons=collections.Counter();notes=collections.Counter()
    for k,b in bm.items():
        a=am[k]
        if b["identity_candidate"]!=a["identity_candidate"]:raise ValueError("Identity candidate changed")
        if b["identity_candidate"].lower()!="true":continue
        old,new=b["new_schema_evidence"],a["new_schema_evidence"]
        transitions[old,new]+=1
        for x in json.loads(a["schema_issues"]):reasons[x]+=1
        for d in json.loads(a["restriction_diagnostics"]):
            for x in d["notes"]:notes[x]+=1
        candidates.append({**a,"previous_schema_evidence":old,"previous_schema_issues":b["schema_issues"]})
    old_rec=sum(n for (o,_),n in transitions.items() if o==RECOGNIZED)
    old_held=sum(n for (o,_),n in transitions.items() if o=="UNKNOWN_OR_CONFLICTING_SCHEMA_REVIEW")
    if len(candidates)!=1182 or old_rec!=711 or old_held!=471:raise ValueError("Previous candidate disposition mismatch")
    lost=sum(n for (o,v),n in transitions.items() if o==RECOGNIZED and v!=RECOGNIZED)
    gained=sum(n for (o,v),n in transitions.items() if o!=RECOGNIZED and v==RECOGNIZED)
    history=rows(out/"historical-independence-review.csv.gz");oldhist=rows(previous["history.csv.gz"])
    hm={pair(r):r for r in oldhist}
    if len(history)!=30 or len(hm)!=30 or {pair(r) for r in history}!=set(hm):raise ValueError("Historical cohort changed")
    signature_counts=collections.Counter();review=[]
    for h in history:
        prev=hm[pair(h)]
        for field in ("independent_reasons","national_competitors","source_competitors","review_disposition"):
            if json.loads(h[field])!=json.loads(prev[field]) if field!="review_disposition" else h[field]!=prev[field]:
                raise ValueError("Historical identity evidence changed")
        competitors=json.loads(h["source_competitors"])
        sigs=[x.get("tariff_signature") for x in competitors]
        status="MISSING_SIGNATURE" if not sigs or any(not x for x in sigs) else "SAME_RAW_SIGNATURE" if len(set(sigs))==1 else "DIFFERENT_RAW_SIGNATURES"
        signature_counts[status]+=1
        review.append({**h,"source_competitor_count":len(competitors),"signature_comparison":status,
                       "identity_disposition":"KEEP_V4_NO_REASSIGNMENT"})
    write_csv(out/"restriction-candidates.csv.gz",candidates,list(candidates[0]))
    write_csv(out/"historical-signature-review.csv.gz",review,list(review[0]))
    report=json.loads((out/"schema-report.json").read_text())
    report.update({"priorSchemaPin":pin,"previousRecognized":old_rec,"previousHeld":old_held,
        "newRecognized":old_rec-lost+gained,"gainedRecognized":gained,"lostRecognized":lost,
        "transitions":table(transitions,["before","after"]),"restrictionIssues":dict(reasons),
        "restrictionNotesNonExclusive":dict(notes),"historicalSignatureComparison":dict(signature_counts),
        "limitations":["Structural alias recognition only; no G6 calculation or tariff applicability proof.",
            "Clock values interpreted as wall-clock fields, no timezone, wrap or billing semantics assumed.",
            "Duration fields use seconds from explicit source keys; boundary inclusion and billing clock not inferred.",
            "Identical raw tariff signatures do not prove identity or authorize propagation.",
            "No match or price promoted, no provider calls, no normative change."]})
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"schema-report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print("G5_RESTRICTION_REPLAY "+json.dumps({k:v for k,v in report.items() if k not in ("sourcePin","inventory","priorSchemaPin")},sort_keys=True))
    if lost:print("G5_RESTRICTION_REGRESSION_REVIEW "+str(lost))

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    root=pathlib.Path(sys.argv[2])
    prior=pin["priorSchema"]
    schema.main(classifier=classify,details=details,emit=False)
    previous=download(root/"prior-schema",prior,{"pairs.csv.gz":("schema-pairs.csv.gz",),
        "history.csv.gz":("historical-independence-review.csv.gz",),"report.json":("schema-report.json",)})
    verify(previous["pairs.csv.gz"],prior["pairsSha256"])
    verify(previous["history.csv.gz"],prior["historySha256"])
    pr=json.loads(previous["report.json"].read_text())
    if pr["codeSha"]!=prior["codeSha"] or pr["referenceValidated"]!=13786 or pr["identityCandidates"]!=1182 or pr["newMatches"]!=0 or pr["pricesPromoted"]!=0 or pr["exportSha256"]["schema-pairs.csv.gz"]!=prior["pairsSha256"] or pr["exportSha256"]["historical-independence-review.csv.gz"]!=prior["historySha256"]:
        raise ValueError("Previous audit provenance mismatch")
    for key in ("baseline","v4","scenario","tariff","sqliteSha256","v4PairsSha256","scenarioPairsSha256"):
        if pr["sourcePin"][key]!=pin[key]:raise ValueError("Prior source mismatch: "+key)
    compare(root/"results",previous,prior)

if __name__=="__main__":main()
