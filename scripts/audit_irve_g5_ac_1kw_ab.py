#!/usr/bin/env python3
"""Cumulative v3 versus v4 exact replay with user-approved AC tolerance."""
import collections
import csv
import gzip
import json
import os
import pathlib
import sqlite3
import sys
from scripts.audit_irve_g5_power_scope import download,verify
from scripts.audit_electroverse_g5_real_matching import (
    read_power_scope,scoped_power_check,exact_scope_check,decision_from_criteria,POWER_SCOPE_RULE,AC_TOLERANCE_RULE,AC_TOLERANCE_KW)

VALID="MATCH_VALIDATED"
def replay_pair(src,dst,profiles,siblings,criteria,enabled,ac_tolerance=False):
    out=dict(criteria)
    out["power"],delta,reason=scoped_power_check(src,dst,enabled,ac_tolerance)
    if criteria["station_uniqueness"]=="PASS" and criteria["evse_uniqueness"]=="PASS":
        out["tariff_scope"],out["cardinality"],out["tariff_homogeneity"]=exact_scope_check(src,dst,profiles,siblings,enabled,ac_tolerance)
    r=decision_from_criteria(out)
    r["power_delta_kw"]=delta
    r["power_justification"]=reason
    return r

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_exact_ac_1kw_ab_only" or pin["acToleranceKw"]!=AC_TOLERANCE_KW or pin["expectedCohort"]!=929 or pin["providerCalls"] is not False or pin["automaticPublication"] is not False:
        raise ValueError("Unapproved audit scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    baseline=download(root/"baseline",pin["baseline"],{"db.sqlite":("g5-matching.sqlite",),"summary.json":("summary.json",)})
    scope=download(root/"scope",pin["scope"],{"pdc.csv.gz":("active-pdc-power-scope.csv.gz",),"scope.json":("power-scope-report.json",)})
    prior=download(root/"prior",pin["priorAB"],{"prior.csv.gz":("exact-ab.csv.gz",),"report.json":("ab-report.json",)})
    verify(prior["prior.csv.gz"],pin["priorCsvSha256"])
    prior_report=json.loads(prior["report.json"].read_text())
    if (prior_report["codeSha"]!=pin["priorAB"]["codeSha"] or prior_report["ruleVersionB"]!=POWER_SCOPE_RULE
        or prior_report["exportSha256"]!=pin["priorCsvSha256"] or prior_report["b"]["MATCH_VALIDATED"]!=12874
        or prior_report["sourcePin"]["baseline"]!=pin["baseline"] or prior_report["sourcePin"]["scope"]!=pin["scope"]):
        raise ValueError("Prior A/B lineage mismatch")
    with gzip.open(prior["prior.csv.gz"],"rt",encoding="utf-8",newline="") as f:
        prior_rows={}
        for row in csv.DictReader(f):
            pair=(int(row["national_id"]),int(row["source_id"]))
            if pair in prior_rows: raise ValueError("Duplicate prior pair")
            prior_rows[pair]=row
    if len(prior_rows)!=21980:raise ValueError("Prior cohort size mismatch")
    verify(baseline["db.sqlite"],pin["sqliteSha256"])
    summary=json.loads(baseline["summary.json"].read_text())
    scope_report=json.loads(scope["scope.json"].read_text())
    if (summary["sqliteSha256"]!=pin["sqliteSha256"] or summary["codeSha"]!=pin["baseline"]["codeSha"]
        or summary["nationalArtifactProvenance"]["nationalArtifact"]!=pin["nationalArtifact"]
        or scope_report["sourcePin"]["national"]["artifact"]!=pin["nationalArtifact"]
        or scope_report["sourcePin"]["exact"]["artifact"]!=14945123454
        or scope_report["exportSha256"]["active-pdc-power-scope.csv.gz"]!=pin["scopeCsvSha256"]
        or scope_report["rawProjectionReconciled"] is not True or scope_report["matchingRulesChanged"] is not False):
        raise ValueError("Source lineage mismatch")
    power_scope=read_power_scope(scope["pdc.csv.gz"],pin["scopeCsvSha256"],pin["nationalArtifact"])
    db=sqlite3.connect(baseline["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok": raise ValueError("Baseline SQLite integrity error")
    meta={r["key"]:json.loads(r["value"]) for r in db.execute("SELECT * FROM metadata")}
    for k in ("codeSha","ruleVersion","nationalArtifactProvenance","exactIdentityCandidatePairs","exactCandidateDisposition","candidateComparisons"):
        if meta[k]!=summary[k]:raise ValueError("Embedded baseline provenance mismatch "+k)
    targets={};profiles=collections.defaultdict(list)
    for r in db.execute("SELECT * FROM national_connector"):
        x=dict(r);x["power_scope"]=power_scope[(x["station_id"],x["evse_id"])]["scope"]
        targets[x["id"]]=x;profiles[x["evse_normalized"]].append(x)
    if len(targets)!=124918 or set(power_scope)!={(x["station_id"],x["evse_id"]) for x in targets.values()}:
        raise ValueError("National scope identities/count mismatch")
    sources={};siblings=collections.defaultdict(list)
    for r in db.execute("SELECT * FROM source_connector"):
        x=dict(r);x.update(pk=x["evse_pk"],connector=x["connector_pk"],price=bool(x["has_price"]))
        sources[x["id"]]=x;siblings[(x["location_pk"],x["evse_pk"])].append(x)
    counts_a=collections.Counter();counts_b=collections.Counter();transitions=collections.Counter()
    power_transitions=collections.Counter();scope_transitions=collections.Counter()
    old_pairs=set();new_pairs=set();outcomes=[];by_operator=collections.Counter();tolerated=0;cohort_outcomes=collections.Counter()
    for r in db.execute("""SELECT c.*,p.criteria AS pattern, ns.operator AS national_operator
        FROM candidate c JOIN criterion_pattern p ON p.id=c.pattern_id
        JOIN national_connector n ON n.id=c.national_id JOIN national_station ns ON ns.id=n.station_id
        JOIN source_connector s ON s.id=c.source_id
        WHERE s.reference_normalized<>'' AND n.evse_normalized=s.reference_normalized
        ORDER BY c.source_id,c.national_id"""):
        s=sources[r["source_id"]];n=targets[r["national_id"]]
        pat=json.loads(r["pattern"]);c=pat["criteria"]
        if not r["method"].startswith("exact+"): raise ValueError("Non-exact candidate in exact cohort")
        args=(s,n,profiles[n["evse_normalized"]],siblings[(s["location_pk"],s["evse_pk"])],c)
        legacy=replay_pair(*args,False)
        if any(legacy[k]!=pat[k] for k in ("criteria","blocking","missing","not_evaluated")) or legacy["decision"]!=r["decision"] or legacy["first_blocker"]!=r["first_blocker"]:
            raise ValueError("v2 replay differs from baseline")
        a=replay_pair(*args,True);b=replay_pair(*args,True,True)
        prev=prior_rows.pop((n["id"],s["id"]))
        if (a["criteria"]!=json.loads(prev["b_criteria"]) or a["blocking"]!=json.loads(prev["b_blockers"])
            or a["decision"]!=prev["b_decision"] or (a["first_blocker"] or "")!=prev["b_first_blocker"]
            or (a["power_justification"] or "")!=prev["power_reason_b"]):
            raise ValueError("A differs from prior v3 "+str((n["id"],s["id"])))
        changed={k for k in c if a["criteria"][k]!=b["criteria"][k]}
        if changed-{"power","tariff_scope","cardinality","tariff_homogeneity"}:raise ValueError("Unrelated criterion changed")
        if a["criteria"]["power"]!=b["criteria"]["power"]:
            if (a["criteria"]["power"]!="FAIL" or b["criteria"]["power"]!="PASS"
                or b["power_justification"]!="AC_1KW_TOLERANCE_USER_APPROVED"
                or n["power_scope"]!="SINGLE_DECLARED_TYPE_NOMINAL_ONLY" or n["mode"]!="AC" or s["mode"]!="AC"
                or c["current"]!="PASS" or c["plug"]!="PASS" or not 0<b["power_delta_kw"]<=1):
                raise ValueError("Unexpected power transition")
            tolerated+=1
            cohort_outcomes[b["decision"]]+=1
        counts_a[a["decision"]]+=1;counts_b[b["decision"]]+=1
        transitions[(a["decision"],b["decision"])]+=1
        power_transitions[(a["criteria"]["power"],b["criteria"]["power"])]+=1
        scope_transitions[(a["criteria"]["tariff_scope"],b["criteria"]["tariff_scope"])]+=1
        pair=(n["id"],s["id"])
        if a["decision"]==VALID:old_pairs.add(pair)
        if b["decision"]==VALID:
            if any(b["criteria"][k]!="PASS" for k in ("evse_identity","station_identity","evse_uniqueness","station_uniqueness","cardinality","tariff_scope")) or any(v=="FAIL" for v in b["criteria"].values()):
                raise ValueError("Invalid B acceptance")
            new_pairs.add(pair)
        if a["decision"]!=b["decision"]:by_operator[(r["national_operator"],a["decision"],b["decision"])]+=1
        outcomes.append({"national_id":n["id"],"source_id":s["id"],"station_id":n["station_id"],"evse_id":n["evse_id"],
            "location_pk":s["location_pk"],"evse_pk":s["evse_pk"],"connector_pk":s["connector_pk"],"operator":r["national_operator"],
            "national_plug":n["plug"],"source_plug":s["plug"],"national_nominal_kw":n["kw"],"individual_national_kw":None,
            "source_connector_kw":s["kw"],"power_scope":n["power_scope"],"power_reason_b":b["power_justification"],
            "power_delta_kw":b["power_delta_kw"],"applied_ac_tolerance_kw":AC_TOLERANCE_KW if b["power_justification"]=="AC_1KW_TOLERANCE_USER_APPROVED" else None,"a_decision":a["decision"],"b_decision":b["decision"],
            "a_criteria":json.dumps(a["criteria"],sort_keys=True),"b_criteria":json.dumps(b["criteria"],sort_keys=True),
            "a_blockers":json.dumps(a["blocking"]),"b_blockers":json.dumps(b["blocking"]),
            "a_first_blocker":a["first_blocker"],"b_first_blocker":b["first_blocker"],
            "changed_criteria":json.dumps(sorted(changed)),"source_has_price":s["has_price"]})
    if prior_rows or len(outcomes)!=21980 or dict(counts_a)!=prior_report["b"] or len(old_pairs)!=12874 or tolerated!=929:
        raise ValueError("A cohort mismatch")
    for i in (0,1):
        if len({p[i] for p in new_pairs})!=len(new_pairs):raise ValueError("B duplicate validated profile or connector")
    gained=new_pairs-old_pairs;lost=old_pairs-new_pairs
    if len(new_pairs)!=len(old_pairs)+len(gained)-len(lost):raise ValueError("B transition mismatch")
    nonexact=summary["candidateComparisons"]-len(outcomes)
    aggregate=collections.Counter(prior_report["allCandidateBProjectedDispositions"])
    aggregate.subtract(counts_a);aggregate.update(counts_b)
    if min(aggregate.values())<0 or sum(aggregate.values())!=summary["candidateComparisons"]:
        raise ValueError("Total dispositions mismatch")
    out=root/"results";out.mkdir()
    with gzip.open(out/"exact-ab.csv.gz","wt",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(outcomes[0]));w.writeheader();w.writerows(outcomes)
    def table(c):
        return [{"from":k[0],"to":k[1],"count":v} for k,v in sorted(c.items())]
    from scripts.audit_irve_g5_power_scope import digest
    result={"sourcePin":pin,"codeSha":os.environ.get("GITHUB_SHA"),"ruleVersionA":POWER_SCOPE_RULE,"ruleVersionB":AC_TOLERANCE_RULE,"acToleranceKw":AC_TOLERANCE_KW,"toleratedPairs":tolerated,"toleratedPairOutcomes":dict(cohort_outcomes),
        "exactPairs":len(outcomes),"nonExactPairsUnchangedByDesign":nonexact,"baselineReproduced":True,
        "a":dict(counts_a),"b":dict(counts_b),"allCandidateBProjectedDispositions":dict(aggregate),
        "decisionTransitions":table(transitions),"powerTransitions":table(power_transitions),"scopeTransitions":table(scope_transitions),
        "gainedPairs":len(gained),"lostPairs":len(lost),"retainedPairs":len(new_pairs&old_pairs),
        "gainedNationalProfiles":len({p[0] for p in gained}),"lostNationalProfiles":len({p[0] for p in lost}),
        "gainedNationalPdc":len({(targets[p[0]]["station_id"],targets[p[0]]["evse_id"]) for p in gained}),
        "lostNationalPdc":len({(targets[p[0]]["station_id"],targets[p[0]]["evse_id"]) for p in lost}),
        "changedByOperator":[{"operator":k[0],"from":k[1],"to":k[2],"count":v} for k,v in by_operator.most_common()],
        "noDuplicateBMatches":True,"exportSha256":digest(out/"exact-ab.csv.gz"),
        "supplierCalls":0,"automaticPublication":False,"pricesPromoted":0,
        "limitations":["Only exact candidate cohort replayed. Non-exact pairs unchanged by design, not newly validated.",
            "No individual national socket power inferred. AC exact mono-type same plug/current <=1 kW only; DC and multi-type above nominal not relaxed.",
            "Matching/scope validation is not price calculation or public promotion."] }
    (out/"ab-report.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("G5_AC_1KW_AB "+json.dumps({k:v for k,v in result.items() if k not in ("sourcePin","changedByOperator")},ensure_ascii=False,sort_keys=True))
    print("G5_AC_1KW_AB_OPERATORS "+json.dumps(result["changedByOperator"][:25],ensure_ascii=False))
    db.close()
if __name__=="__main__":main()
