#!/usr/bin/env python3
"""Audit archived tariff schema on exact identity candidates; no matching changes."""
import collections
import json
import os
import pathlib
import re
import sqlite3
import sys
from decimal import Decimal
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import (rows,pair,table,eligible,independent_unique,
    cached_connectors,signature,power_keys,tariff_gate,meaningful,VALID)
from scripts.audit_electroverse_g5_real_matching import ident,plug,mode,number,state,AC_TOLERANCE_RULE

TECH={"pk","kilowatts","speed","standard","__typename"}
PRICE={"isChargingFree","priceComponents","complexPricingDetail"}
TYPES={"ConsumptionRate","TimeRate","ParkingTimeRate","ConnectionFee","VAT"}
RESTRICTIONS={"dateRestrictions":{"startDate","endDate"},"timeRestrictions":{"startTime","endTime"},
    "durationRestrictions":{"minDurationSeconds","maxDurationSeconds"},"weekdayRestrictions":{"daysOfWeek"}}
# Only literal, documented vocabulary mappings; unfamiliar restrictionTypes stay held.
TYPE_MAP={"DATE":"dateRestrictions","DATE_RESTRICTION":"dateRestrictions","TIME":"timeRestrictions","TIME_RESTRICTION":"timeRestrictions",
    "DURATION":"durationRestrictions","DURATION_RESTRICTION":"durationRestrictions","WEEKDAY":"weekdayRestrictions","WEEKDAY_RESTRICTION":"weekdayRestrictions",
    "DAY_OF_WEEK":"weekdayRestrictions","DAY_OF_WEEK_RESTRICTION":"weekdayRestrictions"}
DAY={"MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"}
def walk(v,path="connector"):
    if isinstance(v,dict):
        for k,x in v.items():
            p=path+"."+k
            yield p,type(x).__name__
            yield from walk(x,p)
    elif isinstance(v,list):
        for x in v:yield from walk(x,path+"[]")
def shape(v,allowed,path,issues):
    if not isinstance(v,dict):
        issues.add("UNKNOWN_STRUCTURE:"+path);return False
    for k,x in v.items():
        if k not in allowed and meaningful(x):issues.add("UNKNOWN_FIELD:"+path+"."+k)
    return True
def validate_restriction(k,v,issues):
    if v is None:return False
    if not shape(v,RESTRICTIONS[k]|{"__typename"},k,issues):return False
    present=False
    for field in RESTRICTIONS[k]:
        x=v.get(field)
        if x is None or x=="":continue
        present=True
        if k=="dateRestrictions":
            if not isinstance(x,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?",x):issues.add("UNRECOGNIZED_DATE:"+field)
        elif k=="timeRestrictions":
            if not isinstance(x,str) or not re.fullmatch(r"\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?",x):issues.add("UNRECOGNIZED_TIME:"+field)
        elif k=="durationRestrictions":
            if isinstance(x,bool) or not isinstance(x,(int,float)) or x<0:issues.add("UNRECOGNIZED_DURATION:"+field)
        elif k=="weekdayRestrictions":
            if not isinstance(x,list) or any(not isinstance(d,str) or d not in DAY for d in x):issues.add("UNRECOGNIZED_WEEKDAY:"+field)
    return present
def classify(c):
    issues=set();dimensions=set();conditions=set();rt=set()
    shape(c,TECH|PRICE,"connector",issues)
    price={k:c.get(k) for k in PRICE}
    for k in power_keys(price):issues.add("POWER_OR_ELECTRICAL_CONDITION:"+k)
    def components(items,path):
        if items is None:return 0
        if not isinstance(items,list):issues.add("UNKNOWN_COMPONENT_STRUCTURE:"+path);return 0
        seen=collections.Counter()
        for x in items:
            if not shape(x,{"__typename","formattedValue"},path+"[]",issues):continue
            typ=x.get("__typename");seen[str(typ)]+=1
            if typ not in TYPES:issues.add("UNKNOWN_COMPONENT_TYPE:"+str(typ))
            else:dimensions.add(typ)
            value=x.get("formattedValue")
            if not isinstance(value,str) or not value.strip():issues.add("MISSING_FORMATTED_RATE:"+path);continue
            # kWh is a consumption unit, not a kW threshold. Unknown prose remains held.
            norm=re.sub(r"\bk\s*wh\b","ENERGY_UNIT",value.lower(),flags=re.I)
            if re.search(r"\b(?:kw|kilowatts?|power|puissance|voltage|amperes?|above|below|up to|jusqu|supérieur|inférieur)\b",norm,re.I):
                issues.add("POTENTIAL_TEXT_POWER_CONDITION:"+path)
            if not re.search(r"\d",value):issues.add("UNPARSEABLE_RATE:"+path)
        if any(v>1 for v in seen.values()):issues.add("DUPLICATE_COMPONENT:"+path)
        return sum(v for k,v in seen.items() if k!="VAT")
    total=components(c.get("priceComponents"),"priceComponents")
    cx=c.get("complexPricingDetail")
    if cx is not None and shape(cx,{"currency","restrictions","__typename"},"complexPricingDetail",issues):
        restrictions=cx.get("restrictions")
        if restrictions is not None and not isinstance(restrictions,list):issues.add("UNKNOWN_RESTRICTIONS_STRUCTURE")
        elif isinstance(restrictions,list):
            for r in restrictions:
                if not shape(r,set(RESTRICTIONS)|{"restrictionTypes","priceComponents","__typename"},"restriction",issues):continue
                active={k for k in RESTRICTIONS if validate_restriction(k,r.get(k),issues)}
                conditions.update(active)
                kinds=r.get("restrictionTypes")
                if kinds is not None:
                    if not isinstance(kinds,list):issues.add("UNKNOWN_RESTRICTION_TYPES_STRUCTURE")
                    else:
                        for t in kinds:
                            rt.add(str(t))
                            key=TYPE_MAP.get(str(t).upper())
                            if key is None:issues.add("UNKNOWN_RESTRICTION_TYPE:"+str(t))
                            elif key not in active:issues.add("RESTRICTION_TYPE_WITHOUT_VALUE:"+str(t))
                total+=components(r.get("priceComponents"),"restriction.priceComponents")
    free=c.get("isChargingFree")
    if free is not None and not isinstance(free,bool):issues.add("UNKNOWN_FREE_FLAG")
    if free is True and total:issues.add("FREE_WITH_PRICED_COMPONENTS_REVIEW")
    if free is not True and total==0:issues.add("MISSING_PRICE")
    if any(x.startswith(("POWER_OR_ELECTRICAL","POTENTIAL_TEXT_POWER")) for x in issues):result="POWER_CONDITION_REVIEW"
    elif issues:result="UNKNOWN_OR_CONFLICTING_SCHEMA_REVIEW"
    elif free is True:result="DIRECT_FREE_NO_OBSERVED_POWER_CONDITION"
    elif conditions or dimensions&{"TimeRate","ParkingTimeRate"}:result="DIRECT_CONDITIONAL_NO_OBSERVED_POWER_CONDITION"
    else:result="DIRECT_SIMPLE_NO_OBSERVED_POWER_CONDITION"
    return result,sorted(issues),sorted(dimensions),sorted(conditions),sorted(rt)
def source_key(s):return s["location_pk"],s["evse_pk"],s["connector_pk"]
def main(classifier=classify, details=None, emit=True):
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_tariff_schema_and_historical_uniqueness_audit" or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Unapproved scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    base=download(root/"base",pin["baseline"],{"db.sqlite":("g5-matching.sqlite",),"summary.json":("summary.json",)})
    v4=download(root/"v4",pin["v4"],{"pairs.csv.gz":("exact-ab.csv.gz",),"report.json":("ab-report.json",)})
    prev=download(root/"prev",pin["scenario"],{"pairs.csv.gz":("scenario-pairs.csv.gz",),"report.json":("scenario-report.json",)})
    for p,k in [(base["db.sqlite"],"sqliteSha256"),(v4["pairs.csv.gz"],"v4PairsSha256"),(prev["pairs.csv.gz"],"scenarioPairsSha256")]:verify(p,pin[k])
    sm=json.loads(base["summary.json"].read_text());vr=json.loads(v4["report.json"].read_text());pr=json.loads(prev["report.json"].read_text())
    if (sm["codeSha"]!=pin["baseline"]["codeSha"] or sm["sqliteSha256"]!=pin["sqliteSha256"] or sm["electroverseTariffArtifact"]!=pin["tariff"]["artifact"]
        or vr["codeSha"]!=pin["v4"]["codeSha"] or vr["ruleVersionB"]!=AC_TOLERANCE_RULE or vr["exportSha256"]!=pin["v4PairsSha256"]
        or pr["codeSha"]!=pin["scenario"]["codeSha"] or pr["exportSha256"]!=pin["scenarioPairsSha256"]
        or pr["sourcePin"]["baseline"]!=pin["baseline"] or pr["sourcePin"]["v4"]!=pin["v4"] or pr["sourcePin"]["tariff"]!=pin["tariff"]
        or pr["referenceValidated"]!=13786 or pr["baselineMatchesNotProvenIndependentOfPower"]!=30 or pr["matchingRulesChanged"] is not False):
        raise ValueError("Provenance mismatch")
    prior=rows(v4["pairs.csv.gz"]);v4map={pair(r):r for r in prior}
    valid={pair(r) for r in prior if r["b_decision"]==VALID}
    if len(prior)!=21980 or len(v4map)!=21980 or len(valid)!=13786 or any(len({p[i] for p in valid})!=len(valid) for i in (0,1)):raise ValueError("v4 mismatch")
    db=sqlite3.connect(base["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("SQLite integrity")
    ns={};ps=collections.defaultdict(list);ss={};siblings=collections.defaultdict(list)
    for r in db.execute("SELECT * FROM national_connector"):
        n=dict(r);ns[n["id"]]=n;ps[n["evse_normalized"]].append(n)
    for r in db.execute("SELECT * FROM source_connector"):
        s=dict(r);ss[s["id"]]=s;siblings[(s["location_pk"],s["evse_pk"])].append(s)
    def unique(n,s):return independent_unique(s,n,ps[n["evse_normalized"]],siblings[(s["location_pk"],s["evse_pk"])])
    historic=[k for k in sorted(valid) if not unique(ns[k[0]],ss[k[1]])]
    if len(historic)!=30:raise ValueError("Historical cohort mismatch")
    previous=rows(prev["pairs.csv.gz"])
    if len(previous)!=1317 or len({pair(r) for r in previous})!=1317:raise ValueError("Scenario cohort mismatch")
    targets={pair(r) for r in previous if r["independent_identity_scope"].lower()=="true"}
    if len(targets)!=1182 or any(len({p[i] for p in valid|targets})!=len(valid|targets) for i in (0,1)) or valid&targets:raise ValueError("Candidate cohort mismatch")
    raw=cached_connectors(root/"tariff",pin["tariff"],sm["tariffManifestSha256"],{source_key(ss[p[1]]) for p in {pair(r) for r in previous}|set(historic)})
    def verify_raw(s):
        x=raw.get(source_key(s))
        if x is None:return None
        ref,c=x
        if ident(ref)!=s["reference_normalized"] or plug(c.get("standard"))!=s["plug"] or number(c.get("kilowatts"))!=s["kw"] or signature(c)!=s["tariff_signature"]:
            raise ValueError("Archived connector mismatch")
        return c
    inventory=collections.Counter();extra=collections.Counter();outrows=[];outcounts=collections.Counter();reasons=collections.Counter();dimensions=collections.Counter();restrictions=collections.Counter();types=collections.Counter()
    for r in previous:
        k=pair(r);n,s=ns[k[0]],ss[k[1]]
        c=verify_raw(s)
        if c is None:raise ValueError("Missing previously verified raw connector")
        old,old_fields=tariff_gate(c)
        if old!=r["price_evidence"] or old_fields!=json.loads(r["price_condition_fields"]):raise ValueError("Old gate not reproduced")
        for key,typ in set(walk(c)):inventory[(key,typ)]+=1
        for field in old_fields:extra[field]+=1
        result,issues,dims,conds,rt=classifier(c)
        cohort="AC" if n["mode"]=="AC" else "DC"
        if k in targets:
            if not unique(n,s):raise ValueError("Identity independence changed")
            outcounts[(cohort,result)]+=1
            for x in issues:reasons[(cohort,x)]+=1
            for x in dims:dimensions[(cohort,x)]+=1
            for x in conds:restrictions[(cohort,x)]+=1
            for x in rt:types[(cohort,x)]+=1
        outrows.append({**r,"new_schema_evidence":result,"schema_issues":json.dumps(issues),"price_dimensions":json.dumps(dims),
            "recognized_restrictions":json.dumps(conds),"restriction_types_raw":json.dumps(rt),"speed_metadata":json.dumps(c.get("speed")),
            "connector_field_names":json.dumps(sorted(c)),"identity_candidate":k in targets,**(details(c) if details else {})})
    history=[];hc=collections.Counter()
    for k in historic:
        n,s=ns[k[0]],ss[k[1]]
        a=[x for x in ps[n["evse_normalized"]] if eligible(s,x)]
        b=[x for x in siblings[(s["location_pk"],s["evse_pk"])] if eligible(x,n)]
        issues=[]
        if state(s["plug"],n["plug"])!="PASS":issues.append("PLUG_NOT_POSITIVELY_PROVEN")
        if state(s["mode"],n["mode"])!="PASS":issues.append("CURRENT_NOT_POSITIVELY_PROVEN")
        if len(a)!=1:issues.append("NATIONAL_COMPETITOR_COUNT_NOT_ONE")
        if len(b)!=1:issues.append("SOURCE_COMPETITOR_COUNT_NOT_ONE")
        sib=siblings[(s["location_pk"],s["evse_pk"])]
        if any(not x["connector_pk"] for x in sib) or len({x["connector_pk"] for x in sib})!=len(sib):issues.append("MISSING_OR_DUPLICATE_CONNECTOR_PK")
        if not s["evse_pk"] or not s["connector_pk"] or not n["evse_normalized"] or s["reference_normalized"]!=n["evse_normalized"]:issues.append("EXACT_KEYS_NOT_PROVEN")
        if not issues:issues.append("OTHER_INDEPENDENCE_FAILURE")
        c=verify_raw(s);result=classifier(c)[0] if c is not None else "RAW_CONNECTOR_NOT_PROVEN"
        for x in issues:hc[x]+=1
        history.append({**v4map[k],"independent_reasons":json.dumps(issues),"national_competitors":json.dumps([{j:x.get(j) for j in ("id","station_id","evse_id","plug","mode","kw")} for x in a]),
            "source_competitors":json.dumps([{j:x.get(j) for j in ("id","connector_pk","plug","mode","kw","tariff_signature")} for x in b]),
            "schema_evidence":result,"review_disposition":"KEEP_V4_PENDING_INDEPENDENT_REVIEW"})
    if sum(outcounts.values())!=1182 or sum(v for (k,_),v in outcounts.items() if k=="DC")!=1177:raise ValueError("Output reconciliation")
    out=root/"results";out.mkdir()
    write_csv(out/"schema-pairs.csv.gz",outrows,list(outrows[0]))
    write_csv(out/"historical-independence-review.csv.gz",history,list(history[0]))
    inv=table(inventory,["path","type"]);write_csv(out/"field-inventory.csv.gz",inv,list(inv[0]))
    report={"codeSha":os.environ.get("GITHUB_SHA"),"sourcePin":pin,"referenceValidated":13786,"identityCandidates":1182,"allResidualPairs":1317,
        "oldGateReproduced":True,"oldUnknownFields":dict(extra),"inventory":inv,"candidateEvidence":table(outcounts,["current","evidence"]),
        "candidateIssuesNonExclusive":table(reasons,["current","issue"]),"candidateDimensions":table(dimensions,["current","dimension"]),
        "candidateRestrictions":table(restrictions,["current","restriction"]),"restrictionTypesObserved":table(types,["current","type"]),
        "historicalReviewed":30,"historicalIssuesNonExclusive":dict(hc),"historicalChanges":0,"newMatches":0,
        "matchingRulesChanged":False,"supplierCalls":0,"pricesPromoted":0,"automaticPublication":False,
        "limitations":["speed is documented collector technical metadata; raw values retained. Unknown nonempty fields remain held.",
            "Restriction vocabulary allow-list conservative; unknown tokens require review, not silently interpreted.",
            "No observed power condition is not full G6 price calculability or proof of tariff applicability across undocumented conditions.",
            "Date/time/duration/day and time-based price kept as separate conditional evidence, not automatically rejected or accepted.",
            "Historical 30 reviewed, no reassignment; actual availability not established."]}
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"schema-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    if emit:print("G5_TARIFF_SCHEMA "+json.dumps({k:v for k,v in report.items() if k not in ("sourcePin","inventory")},ensure_ascii=False,sort_keys=True))
    if emit:print("G5_TARIFF_SCHEMA_FIELDS "+json.dumps(inv,ensure_ascii=False))
    db.close()
if __name__=="__main__":main()
