#!/usr/bin/env python3
"""Inspect residual exact power differences; no matching or price changes."""
import collections
import csv
import gzip
import json
import os
import pathlib
import sys
from decimal import Decimal
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.france.build_france_irve_static_v9 import number
from scripts.audit_electroverse_g5_real_matching import AC_TOLERANCE_RULE

DC="DC_DELTA_REVIEW"
MULTI="MULTITYPE_SOURCE_ABOVE_NOMINAL_REVIEW"
EXPECTED={DC:1254,MULTI:63}
VALID="MATCH_VALIDATED"

def band(value,limits,labels):
    return next((label for limit,label in zip(limits,labels) if value<=limit),labels[-1])

def metrics(n,s):
    n,s=Decimal(str(n)),Decimal(str(s))
    if not n.is_finite() or not s.is_finite() or n<=0 or s<=0 or n==s:
        raise ValueError("Expected positive different power values")
    delta=abs(s-n);relative=100*delta/n
    return {"delta_kw":str(delta),"delta_signed_kw":str(s-n),"relative_pct_of_irve":str(round(relative,6)),
        "absolute_band":band(delta,[5,15,30,50],["<=5","(5,15]","(15,30]","(30,50]",">50"]),
        "relative_band":band(relative,[5,10,20,50],["<=5%","(5,10]%","(10,20]%","(20,50]%",">50%"]),
        "direction":"SOURCE_ABOVE" if s>n else "SOURCE_BELOW",
        "within_dc_candidate_search_band":delta<=15}

def raw_observation(values,nominal):
    # Reproduce existing national numeric normalization, not proof of true rating.
    parsed=[number(x) for x in values]
    if not parsed or any(x is None or x<=0 for x in parsed):return "RAW_MISSING_OR_NONPOSITIVE",[]
    normalized=[round(x/1000 if x>1000 else x,1) for x in parsed]
    if len(set(normalized))!=1 or Decimal(str(normalized[0]))!=Decimal(str(nominal)):
        return "RAW_PROJECTION_DIFFERENT",normalized
    if any(x>1000 for x in parsed):return "RAW_UNIT_CONVERSION_REPRODUCED",normalized
    if any(x!=y for x,y in zip(parsed,normalized)):return "RAW_ONE_DECIMAL_ROUNDING_REPRODUCED",normalized
    return "RAW_NOMINAL_REPRODUCED",normalized

def rows(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))
def pair(row):
    return int(row["national_id"]),int(row["source_id"])
def counts(counter,names):
    return [dict(zip(names,k if isinstance(k,tuple) else (k,)),count=v) for k,v in counter.most_common()]

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if (pin["purpose"]!="offline_dc_and_multitype_above_nominal_diagnostic" or pin["expected"]!=EXPECTED
        or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False):
        raise ValueError("Unapproved diagnostic scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    scope=download(root/"scope",pin["scope"],{"pairs.csv.gz":("exact-pair-power-scope.csv.gz",),"report.json":("power-scope-report.json",)})
    v4=download(root/"v4",pin["v4"],{"pairs.csv.gz":("exact-ab.csv.gz",),"report.json":("ab-report.json",)})
    verify(scope["pairs.csv.gz"],pin["scopePairsSha256"])
    verify(v4["pairs.csv.gz"],pin["v4PairsSha256"])
    sr=json.loads(scope["report.json"].read_text());vr=json.loads(v4["report.json"].read_text())
    if (sr["sourcePin"]["national"]["artifact"]!=pin["nationalArtifact"] or sr["rawProjectionReconciled"] is not True
        or sr["exportSha256"]["exact-pair-power-scope.csv.gz"]!=pin["scopePairsSha256"]
        or vr["sourcePin"]["nationalArtifact"]!=pin["nationalArtifact"] or vr["sourcePin"]["scope"]!=pin["scope"]
        or vr["exportSha256"]!=pin["v4PairsSha256"] or vr["codeSha"]!=pin["v4"]["codeSha"]
        or vr["ruleVersionB"]!=AC_TOLERANCE_RULE or vr["baselineReproduced"] is not True
        or vr["b"]["MATCH_VALIDATED"]!=13786 or vr["noDuplicateBMatches"] is not True):
        raise ValueError("Source lineage mismatch")
    old=rows(scope["pairs.csv.gz"]);latest=rows(v4["pairs.csv.gz"])
    lookup={pair(r):r for r in latest}
    if len(old)!=21980 or len(lookup)!=len(latest) or len(latest)!=21980 or {pair(r) for r in old}!=set(lookup):
        raise ValueError("Exact pair coverage mismatch")
    if dict(collections.Counter(r["b_decision"] for r in latest))!=vr["b"]:
        raise ValueError("v4 dispositions mismatch")
    valid_n={int(r["national_id"]) for r in latest if r["b_decision"]==VALID}
    valid_s={int(r["source_id"]) for r in latest if r["b_decision"]==VALID}
    if len(valid_n)!=13786 or len(valid_s)!=13786:raise ValueError("v4 uniqueness mismatch")
    cohort=collections.Counter();abs_b=collections.Counter();rel_b=collections.Counter();direction=collections.Counter()
    combinations=collections.Counter();op_b=collections.Counter();raw_b=collections.Counter();alt_b=collections.Counter()
    other_b=collections.Counter();current_b=collections.Counter();pdc=collections.defaultdict(set);source=collections.defaultdict(set);outrows=[]
    for r in old:
        label=r["scope_diagnostic"]
        if label not in EXPECTED:continue
        b=lookup[pair(r)]; c=json.loads(b["b_criteria"])
        if (c["power"]!="FAIL" or c["current"]!="PASS" or c["plug"]!="PASS" or b["b_decision"]!="REJECTED_CONTRADICTION"
            or r["station_id"]!=b["station_id"] or r["evse_id"]!=b["evse_id"] or r["power_scope"]!=b["power_scope"]
            or r["national_plug"]!=b["national_plug"] or r["source_plug"]!=b["source_plug"]
            or Decimal(r["national_kw"])!=Decimal(b["national_nominal_kw"]) or Decimal(r["source_kw"])!=Decimal(b["source_connector_kw"])):
            raise ValueError("Residual cohort does not match v4")
        if label==DC and (r["national_mode"]!="DC" or r["power_scope"]!="SINGLE_DECLARED_TYPE_NOMINAL_ONLY"):
            raise ValueError("Unexpected DC scope")
        met=metrics(r["national_kw"],r["source_kw"])
        if label==MULTI and (met["direction"]!="SOURCE_ABOVE" or r["power_scope"]!="MULTITYPE_PDC_INDIVIDUAL_POWER_UNPROVEN"):
            raise ValueError("Unexpected multitype scope")
        raw,normalized=raw_observation(json.loads(r["nominal_raw_values"]),r["national_kw"])
        alt=("BOTH_HAVE_OTHER_VALIDATED" if pair(r)[0] in valid_n and pair(r)[1] in valid_s else
            "NATIONAL_HAS_OTHER_VALIDATED" if pair(r)[0] in valid_n else
            "SOURCE_HAS_OTHER_VALIDATED" if pair(r)[1] in valid_s else "NEITHER_HAS_OTHER_VALIDATED")
        other=[k for k,v in c.items() if v=="FAIL" and k!="power"]
        cohort[label]+=1;abs_b[(label,met["absolute_band"])]+=1;rel_b[(label,met["relative_band"])]+=1
        direction[(label,met["direction"])]+=1;raw_b[(label,raw)]+=1;alt_b[(label,alt)]+=1
        current_b[(label,r["national_mode"],r["national_plug"])]+=1
        combinations[(label,r["national_operator"],r["national_plug"],r["national_kw"],r["source_kw"],met["absolute_band"])]+=1
        op_b[(label,r["national_operator"],met["absolute_band"])]+=1
        other_b[(label,"+".join(sorted(other)) or "NONE")]+=1
        pdc[label].add((r["station_id"],r["evse_id"]));source[label].add((r["location_pk"],r["evse_pk"],r["connector_pk"]))
        outrows.append({**r,**met,"raw_projection_observation":raw,"raw_normalized_kw_values":json.dumps(normalized),
            "v4_decision":b["b_decision"],"v4_criteria":b["b_criteria"],"v4_blockers":b["b_blockers"],
            "v4_first_blocker":b["b_first_blocker"],"other_validated_context":alt,
            "other_failed_criteria_v4":json.dumps(other),"rating_equivalence_proof":"NOT_ESTABLISHED_BY_ARCHIVED_VALUES",
            "review_disposition":"RETAIN_EXISTING_POWER_FAIL"})
    if dict(cohort)!=EXPECTED or any(sr["pairDiagnostics"][k]!=v for k,v in EXPECTED.items()):
        raise ValueError("Target cohort mismatch")
    out=root/"results";out.mkdir()
    write_csv(out/"residual-power-pairs.csv.gz",outrows,list(outrows[0]))
    combos=counts(combinations,["cohort","operator","plug","irve_kw","electroverse_kw","absolute_band"])
    operators=counts(op_b,["cohort","operator","absolute_band"])
    write_csv(out/"power-combinations.csv.gz",combos,list(combos[0]))
    result={"sourcePin":pin,"codeSha":os.environ.get("GITHUB_SHA"),"exactPairs":21980,"referenceValidated":13786,
        "cohorts":dict(cohort),"distinctNationalPdcByCohort":{k:len(v) for k,v in pdc.items()},
        "distinctSourceConnectorsByCohort":{k:len(v) for k,v in source.items()},
        "absoluteBands":counts(abs_b,["cohort","band"]),"relativeBands":counts(rel_b,["cohort","band"]),
        "directions":counts(direction,["cohort","direction"]),"currentAndPlug":counts(current_b,["cohort","current","plug"]),
        "rawProjectionObservations":counts(raw_b,["cohort","observation"]),
        "otherValidatedContexts":counts(alt_b,["cohort","context"]),"otherFailedCriteria":counts(other_b,["cohort","criteria"]),
        "combinations":combos,"operatorsByBand":operators,"ratingEquivalenceProvenPairs":0,
        "newMatches":0,"matchingRulesChanged":False,"supplierCalls":0,"automaticPublication":False,
        "limitations":["Relative denominator is IRVE nominal, not true socket rating.",
            "IRVE raw nominal strings from verified projection audit; Electroverse numerical kW from archived ledger, not original numeric text precision.",
            "Reproduced unit conversion or rounding is not proof that source ratings are equivalent.",
            "15 kW DC band is candidate search only, not automatic match acceptance. Multi-type above nominal remains unresolved contradiction.",
            "Only selected cohorts; no changed decisions, no independent provider corroboration."]}
    result["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"residual-power-report.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("G5_RESIDUAL_POWER "+json.dumps({k:v for k,v in result.items() if k not in ("sourcePin","combinations","operatorsByBand")},ensure_ascii=False,sort_keys=True))
    for k in EXPECTED:
        print("G5_RESIDUAL_POWER_TOP "+json.dumps({"cohort":k,"combinations":[x for x in combos if x["cohort"]==k][:20],"operatorsByBand":[x for x in operators if x["cohort"]==k][:20]},ensure_ascii=False))
if __name__=="__main__":main()
