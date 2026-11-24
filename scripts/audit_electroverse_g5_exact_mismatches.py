#!/usr/bin/env python3
"""Read-only diagnostic of exact candidate pairs; no matching rules changed."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

TECH=("current","plug","power")
VALID="MATCH_VALIDATED"
REJECT="REJECTED_CONTRADICTION"

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()

def compatible(row):
    return all(row["criteria"][k]!="FAIL" for k in TECH)

def technical_pass(row):
    return all(row["criteria"][k]=="PASS" for k in TECH)

def disposition(rows):
    if any(r["decision"]==VALID for r in rows):
        return "HAS_VALIDATED_MATCH"
    if any(technical_pass(r) for r in rows):
        return "TECHNICALLY_CONCORDANT_BUT_UNVALIDATED"
    if any(compatible(r) for r in rows):
        return "NONCONTRADICTORY_WITH_MISSING_TECHNICAL_DATA"
    return "NO_TECHNICALLY_COMPATIBLE_EXACT_PAIR"

def group_disposition(groups):
    counts=collections.Counter(disposition(rows) for rows in groups)
    if not groups: raise ValueError("Empty identity group")
    if counts.get("HAS_VALIDATED_MATCH",0)==len(groups):
        label="ALL_PROFILES_VALIDATED"
    elif counts.get("HAS_VALIDATED_MATCH",0):
        label="PARTIALLY_VALIDATED"
    elif counts.get("NO_TECHNICALLY_COMPATIBLE_EXACT_PAIR",0)==len(groups):
        label="NO_COMPATIBLE_EXACT_PROFILE"
    else:
        label="NO_VALIDATED_MATCH_BUT_SOME_NONCONTRADICTORY"
    return label,dict(counts)

def power_band(delta):
    if delta is None:return "MISSING"
    if delta==0:return "0"
    if delta<=1:return "0-1"
    if delta<=5:return "1-5"
    if delta<=15:return "5-15"
    if delta<=30:return "15-30"
    if delta<=50:return "30-50"
    if delta<=100:return "50-100"
    return ">100"

def reason_combo(row):
    failed=[k for k,v in row["criteria"].items() if v=="FAIL"]
    return "+".join(failed) or "NONE"

def counter_table(counter):
    return [{"key":list(k) if isinstance(k,tuple) else k,"count":v}
            for k,v in sorted(counter.items(),key=lambda x:(-x[1],str(x[0])))]

def csv_write(path,rows,fields):
    with gzip.open(path,"wt",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",type=Path,required=True)
    p.add_argument("--summary",type=Path,required=True)
    p.add_argument("--pin",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    pin=json.loads(a.pin.read_text())
    source=json.loads(a.summary.read_text())
    digest=sha(a.db)
    if digest!=pin["sqliteSha256"] or digest!=source["sqliteSha256"]:
        raise ValueError("Pinned SQLite hash mismatch")
    if source["codeSha"]!=pin["codeSha"] or source["nationalArtifactProvenance"]["nationalArtifact"]!=pin["nationalArtifact"]:
        raise ValueError("Source lineage mismatch")
    if source["supplierCalls"]!=0 or source["automaticPublication"] is not False:
        raise ValueError("Unexpected source mode")
    db=sqlite3.connect(a.db.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("SQLite integrity error")
    metadata={r["key"]:json.loads(r["value"]) for r in db.execute("SELECT * FROM metadata")}
    for key in ("codeSha","ruleVersion","nationalArtifactProvenance","candidateComparisons","exactIdentityCandidatePairs","exactCandidateDisposition","nationalEvseIds"):
        if metadata[key]!=source[key]:raise ValueError("Embedded provenance mismatch "+key)
    rows=[]
    sql="""
    SELECT c.national_id,c.source_id,c.method,c.decision,c.first_blocker,c.details,
      c.prior_offer_ids,c.alias_files,p.criteria AS pattern,
      n.station_id,n.evse_id,n.evse_normalized,n.plug_raw AS national_plug_raw,
      n.plug AS national_plug,n.mode AS national_mode,n.kw AS national_kw,
      ns.operator AS national_operator,ns.name AS station_name,ns.address AS station_address,
      s.location_pk,s.evse_pk,s.connector_pk,s.physical_reference,s.reference_normalized,
      s.plug_raw AS source_plug_raw,s.plug AS source_plug,s.mode AS source_mode,s.kw AS source_kw,
      s.has_price,s.tariff_signature,s.technical_status,s.status_at,s.recent_fault,
      sl.operator_id AS source_operator_id,sl.operator_name AS source_operator_name
    FROM candidate c JOIN criterion_pattern p ON p.id=c.pattern_id
    JOIN national_connector n ON n.id=c.national_id
    JOIN national_station ns ON ns.id=n.station_id
    JOIN source_connector s ON s.id=c.source_id
    JOIN source_location sl ON sl.id=s.location_pk
    WHERE s.reference_normalized<>'' AND n.evse_normalized=s.reference_normalized
    ORDER BY c.source_id,c.national_id
    """
    for r in db.execute(sql):
        row=dict(r)
        pat=json.loads(row.pop("pattern"))
        row["criteria"]=pat["criteria"]
        row["blocking"]=pat["blocking"]
        row["missing"]=pat["missing"]
        row["not_evaluated"]=pat["not_evaluated"]
        row.update(json.loads(row.pop("details")))
        if not row["method"].startswith("exact+"):
            raise ValueError("Exact pair method inconsistent")
        rows.append(row)
    counts=collections.Counter(r["decision"] for r in rows)
    if len(rows)!=source["exactIdentityCandidatePairs"] or dict(counts)!=source["exactCandidateDisposition"]:
        raise ValueError("Exact pair reconciliation mismatch")
    if sum(technical_pass(r) for r in rows)!=source["exactPairsPassingPlugCurrentPower"]:
        raise ValueError("Technical count mismatch")
    src=collections.defaultdict(list); nat=collections.defaultdict(list)
    for r in rows:
        src[r["source_id"]].append(r);nat[r["national_id"]].append(r)
    src_disp={k:disposition(v) for k,v in src.items()}
    nat_disp={k:disposition(v) for k,v in nat.items()}
    source_evse=collections.defaultdict(list); national_evse=collections.defaultdict(list)
    source_groups=[];national_groups=[]
    for k,rr in src.items():
        r=rr[0]
        source_evse[(r["location_pk"],r["evse_pk"])].append(rr)
        source_groups.append({"source_id":k,"location_pk":r["location_pk"],"evse_pk":r["evse_pk"],
            "connector_pk":r["connector_pk"],"physical_reference":r["physical_reference"],
            "source_plug_raw":r["source_plug_raw"],"source_kw":r["source_kw"],"classification":src_disp[k],
            "candidate_pairs":len(rr),"validated_pairs":sum(x["decision"]==VALID for x in rr),
            "compatible_pairs":sum(compatible(x) for x in rr),
            "observed_national_profiles":json.dumps(sorted({(x["national_id"],x["national_plug"],x["national_kw"]) for x in rr},key=lambda y:y[0])),
            "all_fail_combinations":json.dumps(counter_table(collections.Counter(reason_combo(x) for x in rr)))})
    for k,rr in nat.items():
        r=rr[0]
        national_evse[(r["station_id"],r["evse_id"])].append(rr)
        national_groups.append({"national_id":k,"station_id":r["station_id"],"evse_id":r["evse_id"],
            "national_operator":r["national_operator"],"national_plug_raw":r["national_plug_raw"],"national_kw":r["national_kw"],
            "classification":nat_disp[k],"candidate_pairs":len(rr),"validated_pairs":sum(x["decision"]==VALID for x in rr),
            "compatible_pairs":sum(compatible(x) for x in rr),
            "observed_source_connectors":json.dumps(sorted({(x["source_id"],x["source_plug"],x["source_kw"]) for x in rr},key=lambda y:y[0])),
            "all_fail_combinations":json.dumps(counter_table(collections.Counter(reason_combo(x) for x in rr)))})
    pair_context=collections.Counter(); fail_criteria=collections.Counter(); combos=collections.Counter()
    power=collections.Counter(); power_examples=collections.Counter(); raw_plugs=collections.Counter()
    by_operator=collections.defaultdict(collections.Counter); pair_export=[]
    for r in rows:
        sc=src_disp[r["source_id"]];nc=nat_disp[r["national_id"]]
        if r["decision"]==REJECT:
            if sc=="HAS_VALIDATED_MATCH" and nc=="HAS_VALIDATED_MATCH": context="ALTERNATIVES_VALIDATED_BOTH_SIDES"
            elif sc=="HAS_VALIDATED_MATCH":context="SOURCE_CONNECTOR_HAS_OTHER_VALIDATED_PROFILE"
            elif nc=="HAS_VALIDATED_MATCH":context="NATIONAL_PROFILE_HAS_OTHER_VALIDATED_CONNECTOR"
            elif sc=="NO_TECHNICALLY_COMPATIBLE_EXACT_PAIR" and nc=="NO_TECHNICALLY_COMPATIBLE_EXACT_PAIR":context="NO_COMPATIBLE_EXACT_PAIR_EITHER_SIDE"
            else:context="OTHER_COMPATIBLE_OR_UNVERIFIED_ALTERNATIVE"
            pair_context[context]+=1
            combos[reason_combo(r)]+=1
            for k,v in r["criteria"].items():
                if v=="FAIL":fail_criteria[k]+=1
            if r["criteria"]["plug"]=="FAIL" or r["criteria"]["plug"]=="MISSING":
                raw_plugs[(r["national_plug_raw"],r["source_plug_raw"],r["criteria"]["plug"])]+=1
            if r["criteria"]["power"]=="FAIL":
                same=r["criteria"]["plug"]=="PASS" and r["criteria"]["current"]=="PASS"
                power[(r["national_mode"] or "MISSING","SAME_PLUG_CURRENT" if same else "OTHER_OR_UNKNOWN_PLUG_CURRENT",power_band(r.get("power_delta_kw")))]+=1
                if same:
                    power_examples[(r["national_operator"],r["national_plug"],r["national_kw"],r["source_kw"])]+=1
        else:context="NOT_CONTRADICTION"
        by_operator[r["national_operator"]]["pairs"]+=1
        by_operator[r["national_operator"]][r["decision"]]+=1
        if r["decision"]==REJECT:by_operator[r["national_operator"]][context]+=1
        exp={**r,"source_profile_disposition":sc,"national_profile_disposition":nc,"contradiction_context":context,
             "criteria_json":json.dumps(r["criteria"],sort_keys=True),"blocking_json":json.dumps(r["blocking"]),
             "missing_json":json.dumps(r["missing"]),"not_evaluated_json":json.dumps(r["not_evaluated"])}
        pair_export.append(exp)
    if sum(pair_context.values())!=counts[REJECT]:raise ValueError("Contradiction context reconciliation")
    def evse_rows(grouped,side):
        result=[]
        for key,groups in sorted(grouped.items()):
            label,detail=group_disposition(groups)
            result.append({"key1":key[0],"key2":key[1],"side":side,"classification":label,
                          "profile_count":len(groups),"profile_dispositions":json.dumps(detail,sort_keys=True)})
        return result
    se=evse_rows(source_evse,"Electroverse");ne=evse_rows(national_evse,"IRVE")
    by_source_op=collections.defaultdict(collections.Counter)
    for rr in src.values():
        r=rr[0]
        by_source_op[r["source_operator_id"]][src_disp[r["source_id"]]]+=1
    for row in national_groups:
        by_operator[row["national_operator"]]["national_profiles_"+row["classification"]]+=1
    pair_fields=["national_id","source_id","station_id","evse_id","national_operator","station_name","station_address",
        "location_pk","evse_pk","connector_pk","physical_reference","source_operator_id","source_operator_name",
        "national_plug_raw","source_plug_raw","national_plug","source_plug","national_mode","source_mode",
        "national_kw","source_kw","power_delta_kw","method","decision","first_blocker","contradiction_context",
        "source_profile_disposition","national_profile_disposition","criteria_json","blocking_json","missing_json","not_evaluated_json",
        "prior_offer_ids","alias_files","has_price","tariff_signature","technical_status","status_at","recent_fault"]
    csv_write(a.out/"exact-pairs.csv.gz",pair_export,pair_fields)
    csv_write(a.out/"source-connectors.csv.gz",source_groups,list(source_groups[0]))
    csv_write(a.out/"national-profiles.csv.gz",national_groups,list(national_groups[0]))
    csv_write(a.out/"source-evses.csv.gz",se,list(se[0]))
    csv_write(a.out/"national-evses.csv.gz",ne,list(ne[0]))
    report={"schemaVersion":1,"sourcePin":pin,"sourceRuleVersion":source["ruleVersion"],
        "exactPairs":len(rows),"exactPairDispositions":dict(counts),"technicalPassPairs":sum(technical_pass(r) for r in rows),
        "contradictionContexts":dict(pair_context),"contradictionCriteriaNonExclusive":dict(fail_criteria),
        "contradictionCombinations":dict(combos),"powerFailureBands":counter_table(power),
        "samePlugCurrentPowerFailureCombinations":counter_table(power_examples),
        "rawPlugFailureOrMissingCombinations":counter_table(raw_plugs),
        "sourceConnectorCount":len(src),"sourceConnectorDispositions":dict(collections.Counter(src_disp.values())),
        "nationalProfileCount":len(nat),"nationalProfileDispositions":dict(collections.Counter(nat_disp.values())),
        "sourceEvseCount":len(se),"sourceEvseDispositions":dict(collections.Counter(r["classification"] for r in se)),
        "nationalEvseCount":len(ne),"nationalEvseDispositions":dict(collections.Counter(r["classification"] for r in ne)),
        "byNationalOperator":dict(by_operator),"bySourceOperatorCode":dict(by_source_op),
        "limitations":["Exact candidate pairs only; all other matching methods remain outside this analysis.",
            "A validated alternative on one side is not proof that another connector/profile is valid or that all sockets at that EVSE are covered.",
            "No compatible exact profile is an unresolved discrepancy, not proof that either source is wrong.",
            "Source current may be derived from plug; IRVE nominal EVSE power may differ from individual connector ratings.",
            "Power bands are descriptive; DC <=15 kW is not an automatic acceptance rule.",
            "National operator is a national label; source operator code is not a verified CPO crosswalk."],
        "supplierCalls":0,"automaticPublication":False,"matchingRulesChanged":False}
    report["exportSha256"]={p.name:sha(p) for p in sorted(a.out.glob("*.csv.gz"))}
    (a.out/"exact-mismatch-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    brief={k:v for k,v in report.items() if k not in ("sourcePin","byNationalOperator","bySourceOperatorCode","samePlugCurrentPowerFailureCombinations","rawPlugFailureOrMissingCombinations","limitations")}
    brief["topNationalOperatorsByContradictions"]=sorted([{"operator":k,**v} for k,v in by_operator.items()],key=lambda x:-x.get(REJECT,0))[:15]
    brief["topSamePlugPowerCombinations"]=report["samePlugCurrentPowerFailureCombinations"][:20]
    brief["topRawPlugCombinations"]=report["rawPlugFailureOrMissingCombinations"][:20]
    db.close()
    print("G5_EXACT_MISMATCH_ANALYSIS "+json.dumps(brief,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
