#!/usr/bin/env python3
"""Read-only diagnostics of unresolved exact v5 pairs and profiles."""
import collections
import json
import os
import pathlib
import sqlite3
import sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import table
from scripts.audit_electroverse_g5_real_matching import plug,mode,decision_from_criteria,ident

RULE="g5-fr-2026-11-24-v5-exact-independent-power-divergence"
VALID="MATCH_VALIDATED"
def j(value):return json.dumps(value,ensure_ascii=False,sort_keys=True)
def category(nmatch,smatch):
    if nmatch and smatch:return "BOTH_ALREADY_MATCHED"
    if nmatch:return "NATIONAL_ALREADY_MATCHED"
    if smatch:return "SOURCE_ALREADY_MATCHED"
    return "BOTH_UNMATCHED"

def diagnose(criteria,c_review,c_blockers,nmatch,smatch,source_price,recent_fault,raw_n,raw_s,nplug,splug):
    labels=[]
    if nmatch:labels.append("NATIONAL_PROFILE_ALREADY_VALIDATED")
    if smatch:labels.append("SOURCE_CONNECTOR_ALREADY_VALIDATED")
    if not source_price:labels.append("NO_PRICE_PAYLOAD")
    if recent_fault:labels.append("RECENT_HISTORICAL_FAULT")
    if nplug is None or splug is None:
        labels.append("PLUG_NOMENCLATURE_OR_VALUE_UNVERIFIED")
    elif nplug!=splug:labels.append("NORMALIZED_PLUG_CONTRADICTION")
    if criteria["current"]=="FAIL":labels.append("CURRENT_CONTRADICTION")
    if criteria["power"]=="FAIL":labels.append("POWER_CONTRADICTION_V5")
    if any(criteria[k]=="FAIL" for k in ("station_uniqueness","evse_uniqueness")):labels.append("GLOBAL_IDENTITY_AMBIGUITY")
    if any(criteria[k]=="FAIL" for k in ("station_identity","evse_identity","country","operator")):labels.append("OTHER_IDENTITY_CONTRADICTION")
    if any(criteria[k] in ("MISSING","NOT_EVALUATED") for k in ("cardinality","tariff_scope","tariff_homogeneity")):labels.append("SCOPE_OR_CARDINALITY_UNPROVEN")
    if c_review=="C_HELD":labels.append("C_AUDITED_HELD")
    elif c_review=="NOT_EVALUATED_OUTSIDE_AUDITED_COHORT":labels.append("C_NOT_EVALUATED")
    if nmatch:priority="ALTERNATIVE_ALREADY_RESOLVED"
    elif smatch:priority="SOURCE_OCCUPIED_NO_REASSIGNMENT"
    elif recent_fault:priority="TECHNICAL_EXCLUSION_REVIEW"
    elif not source_price:priority="NO_PRICE_PAYLOAD_IN_CACHE"
    elif "OTHER_IDENTITY_CONTRADICTION" in labels or "GLOBAL_IDENTITY_AMBIGUITY" in labels:priority="IDENTITY_OR_UNIQUENESS_REVIEW"
    elif "NORMALIZED_PLUG_CONTRADICTION" in labels or "CURRENT_CONTRADICTION" in labels:priority="TECHNICAL_CONTRADICTION_REVIEW"
    elif "PLUG_NOMENCLATURE_OR_VALUE_UNVERIFIED" in labels:priority="NOMENCLATURE_REVIEW"
    elif "POWER_CONTRADICTION_V5" in labels:priority="POWER_REVIEW_NO_RELAXATION"
    else:priority="SCOPE_OR_OTHER_EVIDENCE_REVIEW"
    return priority,labels

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_v5_residual_exact_diagnostics_only" or pin["ruleVersion"]!=RULE or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Wrong scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    src=download(root/"v5",pin["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    verify(src["db.sqlite"],pin["sqliteSha256"])
    pr=json.loads(src["report.json"].read_text())
    if (pr["codeSha"]!=pin["ledger"]["codeSha"] or pr["ruleVersion"]!=RULE or pr["sqliteSha256"]!=pin["sqliteSha256"]
        or pr["newValidated"]!=14968 or pr["exactPairs"]!=21980 or pr["nonExactUnchanged"]!=559998 or pr["supplierCalls"]!=0 or pr["pricesPromoted"]!=0 or pr["lost"]!=0 or pr["reassigned"]!=0):
        raise ValueError("V5 provenance mismatch")
    db=sqlite3.connect(src["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("SQLite integrity mismatch")
    meta={r["key"]:json.loads(r["value"]) for r in db.execute("SELECT * FROM metadata")}
    if any(meta[k]!=pr[k] for k in ("codeSha","ruleVersion","nationalDisposition","sourceDisposition")):raise ValueError("Metadata mismatch")
    all_decisions={r[0]:r[1] for r in db.execute("SELECT decision,count(*) FROM candidate GROUP BY decision")}
    if all_decisions!=pr["allCandidateDispositions"] or sum(all_decisions.values())!=581978:raise ValueError("All candidate mismatch")
    valid=list(db.execute("SELECT national_id,source_id FROM candidate WHERE decision=?",(VALID,)))
    vn={r[0]:r[1] for r in valid};vs={r[1]:r[0] for r in valid}
    if len(valid)!=14968 or len(vn)!=14968 or len(vs)!=14968:raise ValueError("Validated uniqueness mismatch")
    exact_counts={r[0]:r[1] for r in db.execute("SELECT v5_decision,count(*) FROM v5_exact_replay GROUP BY v5_decision")}
    if exact_counts!=pr["exactDispositions"] or sum(exact_counts.values())!=21980:raise ValueError("Exact disposition mismatch")
    query="""SELECT c.national_id,c.source_id,c.method,c.decision,c.first_blocker,c.details,p.criteria AS pattern,
       x.v4_decision,x.v5_decision,x.v5_criteria,x.observed_power_criterion,x.power_justification,x.c_review,x.c_blockers,x.tariff_schema,
       n.station_id,n.evse_id,n.evse_normalized,n.plug_raw AS national_plug_raw,n.plug AS national_plug,n.mode AS national_mode,n.kw AS national_kw,
       ns.name AS station_name,ns.address AS station_address,ns.operator AS national_operator,
       s.location_pk,s.evse_pk,s.connector_pk,s.physical_reference,s.reference_normalized,s.plug_raw AS source_plug_raw,
       s.plug AS source_plug,s.mode AS source_mode,s.kw AS source_kw,s.has_price,s.tariff_signature,s.recent_fault,s.technical_status,s.status_at,
       sl.operator_id AS source_operator_id,sl.operator_name AS source_operator
       FROM v5_exact_replay x JOIN candidate c USING(national_id,source_id)
       JOIN criterion_pattern p ON p.id=c.pattern_id JOIN national_connector n ON n.id=c.national_id
       JOIN national_station ns ON ns.id=n.station_id JOIN source_connector s ON s.id=c.source_id
       JOIN source_location sl ON sl.id=s.location_pk WHERE x.v5_decision<>? ORDER BY c.national_id,c.source_id"""
    pairs=[];by_profile=collections.defaultdict(list);by_source=collections.defaultdict(list)
    dispositions=collections.Counter();allocation=collections.Counter();reasons=collections.Counter();first=collections.Counter()
    operators=collections.Counter();nomenclature=collections.Counter();criteria_counts=collections.Counter();priorities=collections.Counter()
    for r in db.execute(query,(VALID,)):
        d=dict(r);n,s=d["national_id"],d["source_id"]
        if d["decision"]!=d["v5_decision"] or not d["method"].startswith("exact+") or d["evse_normalized"]!=d["reference_normalized"] or not d["evse_normalized"]:raise ValueError("Exact identity mismatch")
        pat=json.loads(d.pop("pattern"));c=pat["criteria"]
        recomputed=decision_from_criteria(c)
        if c!=json.loads(d["v5_criteria"]) or any(recomputed[k]!=pat[k] for k in ("blocking","missing","not_evaluated")) or recomputed["decision"]!=d["decision"] or recomputed["first_blocker"]!=d["first_blocker"]:raise ValueError("Decision vector mismatch")
        cat=category(n in vn,s in vs)
        priority,labels=diagnose(c,d["c_review"],json.loads(d["c_blockers"]),n in vn,s in vs,d["has_price"],d["recent_fault"],d["national_plug_raw"],d["source_plug_raw"],d["national_plug"],d["source_plug"])
        try:raw_s=json.loads(d["source_plug_raw"])
        except (TypeError,ValueError):raw_s=None
        if plug(d["national_plug_raw"])!=d["national_plug"] or plug(raw_s)!=d["source_plug"] or mode(d["source_plug"])!=d["source_mode"]:raise ValueError("Stored nomenclature mismatch")
        dispositions[d["decision"]]+=1;allocation[cat]+=1;priorities[(cat,priority)]+=1
        operators[(d["national_operator"],cat,priority)]+=1
        first[(cat,d["first_blocker"] or "NONE")]+=1
        for k,v in c.items():criteria_counts[(cat,k,v)]+=1
        for x in pat["blocking"]:reasons[(cat,x)]+=1
        nomenclature[(cat,d["national_plug_raw"],d["source_plug_raw"],d["national_plug"] or "MISSING",d["source_plug"] or "MISSING",c["plug"])]+=1
        d.update(allocation=cat,review_priority=priority,diagnostic_labels=j(labels),all_blockers=j(pat["blocking"]),
            missing_criteria=j(pat["missing"]),not_evaluated_criteria=j(pat["not_evaluated"]),validated_source_for_national=vn.get(n),validated_national_for_source=vs.get(s),
            power_delta_kw=abs(d["national_kw"]-d["source_kw"]) if d["national_kw"] is not None and d["source_kw"] is not None else None)
        pairs.append(d);by_profile[n].append(d);by_source[s].append(d)
    if len(pairs)!=7012 or len({(x["national_id"],x["source_id"]) for x in pairs})!=7012 or dict(dispositions)!={k:v for k,v in exact_counts.items() if k!=VALID}:raise ValueError("Residual pair count mismatch")
    profiles=[];profile_counts=collections.Counter();profile_operator=collections.Counter();profile_blockers=collections.Counter()
    for n,rr in sorted(by_profile.items()):
        d=rr[0];unoccupied=[x for x in rr if x["source_id"] not in vs]
        group="ALREADY_MATCHED" if n in vn else "UNMATCHED_ALL_EXACT_SOURCES_OCCUPIED" if not unoccupied else "UNMATCHED_HAS_UNOCCUPIED_EXACT_SOURCE"
        blockers=sorted({k for x in rr for k in json.loads(x["all_blockers"])})
        prio=sorted({x["review_priority"] for x in rr})
        profile_counts[group]+=1;profile_operator[(d["national_operator"],group)]+=1
        for k in blockers:profile_blockers[(group,k)]+=1
        profiles.append({**{k:d[k] for k in ("national_id","station_id","evse_id","national_operator","station_name","station_address","national_plug_raw","national_plug","national_mode","national_kw")},
            "group":group,"exact_residual_candidates":len(rr),"unoccupied_exact_sources":len(unoccupied),"validated_source_id":vn.get(n),
            "source_ids":j(sorted(x["source_id"] for x in rr)),"all_blockers_nonexclusive":j(blockers),"review_priorities":j(prio),
            "free_candidate_priorities":j(sorted({x["review_priority"] for x in unoccupied}))})
    sources=[];source_counts=collections.Counter()
    for s,rr in sorted(by_source.items()):
        d=rr[0];free=[x for x in rr if x["national_id"] not in vn]
        group="ALREADY_MATCHED" if s in vs else "UNMATCHED_ALL_EXACT_TARGETS_OCCUPIED" if not free else "UNMATCHED_HAS_UNOCCUPIED_EXACT_TARGET"
        source_counts[group]+=1
        sources.append({**{k:d[k] for k in ("source_id","location_pk","evse_pk","connector_pk","physical_reference","source_operator","source_operator_id","source_plug_raw","source_plug","source_mode","source_kw","has_price","recent_fault","tariff_signature")},
            "group":group,"exact_residual_candidates":len(rr),"unoccupied_exact_targets":len(free),"validated_national_id":vs.get(s),"national_ids":j(sorted(x["national_id"] for x in rr))})
    out=root/"results";out.mkdir()
    exports={"residual-exact-pairs.csv.gz":pairs,"residual-national-profiles.csv.gz":profiles,"residual-source-connectors.csv.gz":sources,
        "operator-review.csv.gz":table(operators,["operator","allocation","priority"]),
        "profile-operator.csv.gz":table(profile_operator,["operator","group"]),
        "profile-blockers.csv.gz":table(profile_blockers,["group","blocker"]),
        "criteria.csv.gz":table(criteria_counts,["allocation","criterion","status"]),
        "nomenclature.csv.gz":table(nomenclature,["allocation","national_raw","source_raw","national_normalized","source_normalized","plug_status"])}
    for name,data in exports.items():write_csv(out/name,data,list(data[0]))
    unresolved=[x for x in profiles if x["group"]!="ALREADY_MATCHED"]
    free=[x for x in profiles if x["group"]=="UNMATCHED_HAS_UNOCCUPIED_EXACT_SOURCE"]
    report={"codeSha":os.environ.get("GITHUB_SHA"),"sourcePin":pin,"referenceValidated":14968,"exactPairs":21980,"residualPairs":len(pairs),
        "residualDecisions":dict(dispositions),"pairAllocation":dict(allocation),"nationalProfileGroups":dict(profile_counts),"sourceConnectorGroups":dict(source_counts),
        "distinctResidualNationalProfiles":len(profiles),"distinctUnmatchedNationalProfiles":len(unresolved),
        "distinctUnmatchedPdc":len({(x["station_id"],x["evse_id"]) for x in unresolved}),"distinctUnmatchedStations":len({x["station_id"] for x in unresolved}),
        "unmatchedProfilesWithUnoccupiedExactSource":len(free),"unmatchedPdcWithUnoccupiedExactSource":len({(x["station_id"],x["evse_id"]) for x in free}),
        "pairPriorities":table(priorities,["allocation","priority"]),"firstBlockers":table(first,["allocation","reason"]),
        "allBlockersNonExclusive":table(reasons,["allocation","reason"]),"profileBlockersNonExclusive":exports["profile-blockers.csv.gz"],
        "topUnmatchedOperators":table(collections.Counter(x["national_operator"] for x in unresolved),["operator"])[:30],
        "nomenclatureRows":len(nomenclature),"nomenclatureMismatchExamples":[x for x in exports["nomenclature.csv.gz"] if x["allocation"]=="BOTH_UNMATCHED" and x["plug_status"]!="PASS"][:30],
        "newMatches":0,"matchingRulesChanged":False,"supplierCalls":0,"pricesPromoted":0,"automaticPublication":False,
        "limitations":["A pair is not a PDC; a profile may have several candidates and a PDC several profiles.",
            "Unoccupied source is not a validated match; occupied source is not reassigned.",
            "Priority labels are diagnostic, not normative; all criteria and original blockers retained.",
            "Normalized plug mismatches are not evidence of a vocabulary error; missing/raw variants need source review.",
            "No current availability or G6 price calculation proven."]}
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"residual-exact-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("G5_V5_RESIDUAL_EXACT "+json.dumps({k:v for k,v in report.items() if k not in ("sourcePin","nomenclatureMismatchExamples","topUnmatchedOperators")},sort_keys=True,ensure_ascii=False))
    print("G5_V5_RESIDUAL_NOMENCLATURE "+j(report["nomenclatureMismatchExamples"]))
    print("G5_V5_RESIDUAL_OPERATORS "+j(report["topUnmatchedOperators"]))
    db.close()
if __name__=="__main__":main()
