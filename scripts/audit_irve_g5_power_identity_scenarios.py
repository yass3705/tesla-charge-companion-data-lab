#!/usr/bin/env python3
"""Scenario-only exact identity vs power divergence. No operational rule changes."""
import collections
import csv
import gzip
import hashlib
import json
import os
import pathlib
import sqlite3
import sys
import zipfile
from decimal import Decimal
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_electroverse_g5_real_matching import dump,ident,plug,mode,number,state,AC_TOLERANCE_RULE

VALID="MATCH_VALIDATED"
DC="DC_DELTA_REVIEW"
MULTI="MULTITYPE_SOURCE_ABOVE_NOMINAL_REVIEW"
SCENARIOS=("A_ABOVE","B_ABOVE_OR_LIMITED_BELOW","C_BOTH_DIRECTIONS")
def pair(r):
    return int(r["national_id"]),int(r["source_id"])
def rows(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def table(c,keys):
    return [dict(zip(keys,k if isinstance(k,tuple) else (k,)),count=v) for k,v in c.most_common()]
def eligible(s,n):
    # Missing plug/current cannot prove uniqueness; include as competing candidates.
    return state(s["plug"],n["plug"])!="FAIL" and state(s["mode"],n["mode"])!="FAIL"
def independent_unique(s,n,profiles,siblings):
    if not s["evse_pk"] or not s["connector_pk"] or not n["evse_normalized"] or s["reference_normalized"]!=n["evse_normalized"]:
        return False
    if state(s["plug"],n["plug"])!="PASS" or state(s["mode"],n["mode"])!="PASS":
        return False
    if len({x["connector_pk"] for x in siblings})!=len(siblings) or any(not x["connector_pk"] for x in siblings):
        return False
    a=[x["id"] for x in profiles if eligible(s,x)]
    b=[x["id"] for x in siblings if eligible(x,n)]
    return a==[n["id"]] and b==[s["id"]]
def scenario_flags(n,s):
    n,s=Decimal(str(n)),Decimal(str(s))
    if not n.is_finite() or not s.is_finite() or n<=0 or s<=0 or n==s:raise ValueError("Invalid divergence")
    d=s-n
    return {"A_ABOVE":d>0,"B_ABOVE_OR_LIMITED_BELOW":d>0 or (-d<=15 and -d*100<=10*n),"C_BOTH_DIRECTIONS":True}
def meaningful(v):
    return v not in (None,False,"",[],{})
def power_keys(v,path=""):
    found=[]
    if isinstance(v,dict):
        for k,x in v.items():
            p=path+"."+k if path else k
            low=k.lower().replace("_","")
            if any(t in low for t in ("power","kilowatt","kw","amper","voltage","current")) and meaningful(x):
                found.append(p)
            found.extend(power_keys(x,p))
    elif isinstance(v,list):
        for x in v:found.extend(power_keys(x,path+"[]"))
    return sorted(set(found))
def signature(c):
    return hashlib.sha256(dump({k:c.get(k) for k in ("isChargingFree","priceComponents","complexPricingDetail")}).encode()).hexdigest()
def tariff_gate(c):
    # Strict allow-list for a direct connector payload. Unknown/complex terms
    # remain review cases, even if no explicit power restriction is observed.
    fields={k:c.get(k) for k in ("isChargingFree","priceComponents","complexPricingDetail")}
    keys=power_keys(fields)
    if keys:return "EXPLICIT_POWER_OR_ELECTRICAL_CONDITION",keys
    # The connector's kW and standard are metadata, not price conditions.
    extra=[k for k,v in c.items() if k not in ("pk","kilowatts","standard","isChargingFree","priceComponents","complexPricingDetail","__typename") and meaningful(v)]
    if extra:return "UNKNOWN_CONNECTOR_FIELDS",sorted(extra)
    complex_=fields["complexPricingDetail"]
    if complex_ is not None:
        if not isinstance(complex_,dict):return "UNKNOWN_COMPLEX_STRUCTURE",[]
        if any(meaningful(v) for k,v in complex_.items() if k not in ("currency","restrictions","__typename")):
            return "UNKNOWN_COMPLEX_FIELDS",sorted(k for k,v in complex_.items() if k not in ("currency","restrictions","__typename") and meaningful(v))
        if meaningful(complex_.get("restrictions")):return "COMPLEX_RESTRICTIONS_REVIEW",[]
    comps=fields["priceComponents"]
    if comps is None:comps=[]
    if not isinstance(comps,list):return "UNKNOWN_COMPONENT_STRUCTURE",[]
    if fields["isChargingFree"] is True and not comps:return "DIRECT_SIMPLE_FREE",[]
    if not comps or fields["isChargingFree"] is True:return "MISSING_OR_CONFLICTING_PRICE",[]
    types=[]
    for comp in comps:
        if not isinstance(comp,dict):return "UNKNOWN_COMPONENT_STRUCTURE",[]
        extra=[k for k,v in comp.items() if k not in ("__typename","formattedValue") and meaningful(v)]
        if extra:return "UNKNOWN_COMPONENT_FIELDS",sorted(extra)
        typ=comp.get("__typename")
        if typ not in ("ConsumptionRate","TimeRate","ParkingTimeRate","ConnectionFee","VAT"):
            return "UNKNOWN_COMPONENT_TYPE",[str(typ)]
        if not isinstance(comp.get("formattedValue"),str) or not comp["formattedValue"].strip():
            return "MISSING_FORMATTED_RATE",[]
        # Free text can conceal a condition even without structured keys.
        low=comp["formattedValue"].lower()
        if any(x in low for x in ("kw ","kw)","kw-","kw+","kw<","kw>","kw/","power","puissance","up to","above","below","jusqu","supérieur","inférieur")) and "kwh" not in low:
            return "POTENTIAL_TEXT_POWER_CONDITION",[]
        types.append(typ)
    if not any(x!="VAT" for x in types):return "MISSING_OR_CONFLICTING_PRICE",[]
    if len(set(types))!=len(types):return "DUPLICATE_COMPONENT_REVIEW",[]
    if "TimeRate" in types or "ParkingTimeRate" in types:return "TIME_BASED_PRICE_REVIEW",[]
    return "DIRECT_SIMPLE_ENERGY_OR_FLAT",[]

def cached_connectors(root,pin,manifest_sha,wanted):
    # Existing helper validates run, artifact, ZIP SHA and extracts only manifest.
    result=download(root,pin,{"manifest.json":("data","electroverse","tariff_cache","manifest.json")})
    verify(result["manifest.json"],manifest_sha)
    manifest=json.loads(result["manifest.json"].read_text())
    if manifest["totalStations"]!=22818:raise ValueError("Unexpected tariff manifest count")
    found={};seenloc=set()
    with zipfile.ZipFile(root/"input.zip") as z:
        entries=z.namelist()
        for sh in manifest["shards"]:
            path=pathlib.PurePosixPath(sh["file"])
            if path.is_absolute() or ".." in path.parts:raise ValueError("Unsafe shard path")
            suffix="/data/electroverse/tariff_cache/"+str(path)
            matches=[p for p in entries if ("/"+p).endswith(suffix)]
            if len(matches)!=1:raise ValueError("Missing or duplicate tariff shard")
            doc=json.loads(z.read(matches[0]))
            if len(doc["stations"])!=sh["count"]:raise ValueError("Shard count mismatch")
            for loc,r in doc["stations"].items():
                if loc in seenloc or str(r.get("electroverseLocationPk"))!=loc:raise ValueError("Source location identity mismatch")
                seenloc.add(loc)
                for e in (r.get("tariff") or {}).get("evses") or []:
                    for c in e.get("connectors") or []:
                        k=(loc,str(e.get("pk") or ""),str(c.get("pk") or ""))
                        if k not in wanted:continue
                        if k in found:
                            found[k]=None  # ambiguous raw identity: quarantine rather than abort
                        else:
                            found[k]=(e.get("physicalReference"),c)
    if len(seenloc)!=manifest["totalStations"]:raise ValueError("Cache location coverage mismatch")
    return found

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if (pin["purpose"]!="offline_exact_power_identity_scenarios_only" or pin["supplierCalls"] is not False
        or pin["automaticPublication"] is not False or pin["limitedBelow"]!={"absoluteKw":15,"relativePctOfIrve":10}):
        raise ValueError("Unapproved scenario request")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    base=download(root/"base",pin["baseline"],{"db.sqlite":("g5-matching.sqlite",),"summary.json":("summary.json",)})
    v4=download(root/"v4",pin["v4"],{"pairs.csv.gz":("exact-ab.csv.gz",),"report.json":("ab-report.json",)})
    residual=download(root/"residual",pin["residual"],{"pairs.csv.gz":("residual-power-pairs.csv.gz",),"report.json":("residual-power-report.json",)})
    for p,k in [(base["db.sqlite"],"sqliteSha256"),(v4["pairs.csv.gz"],"v4PairsSha256"),(residual["pairs.csv.gz"],"residualPairsSha256")]:verify(p,pin[k])
    summary=json.loads(base["summary.json"].read_text());vr=json.loads(v4["report.json"].read_text());rr=json.loads(residual["report.json"].read_text())
    if (summary["sqliteSha256"]!=pin["sqliteSha256"] or summary["codeSha"]!=pin["baseline"]["codeSha"]
        or vr["codeSha"]!=pin["v4"]["codeSha"] or vr["ruleVersionB"]!=AC_TOLERANCE_RULE
        or vr["exportSha256"]!=pin["v4PairsSha256"] or vr["sourcePin"]["baseline"]!=pin["baseline"]
        or rr["codeSha"]!=pin["residual"]["codeSha"] or rr["sourcePin"]["v4"]!=pin["v4"]
        or rr["exportSha256"]["residual-power-pairs.csv.gz"]!=pin["residualPairsSha256"]
        or rr["referenceValidated"]!=13786 or rr["matchingRulesChanged"] is not False
        or summary["electroverseTariffArtifact"]!=pin["tariff"]["artifact"]):
        raise ValueError("Input lineage mismatch")
    prior=rows(v4["pairs.csv.gz"]); prior_by_pair={pair(r):r for r in prior}
    if len(prior)!=21980 or len(prior_by_pair)!=21980 or dict(collections.Counter(r["b_decision"] for r in prior))!=vr["b"]:
        raise ValueError("v4 cohort mismatch")
    valid={pair(r) for r in prior if r["b_decision"]==VALID}
    vn={x[0] for x in valid};vs={x[1] for x in valid}
    if len(valid)!=13786 or len(vn)!=len(valid) or len(vs)!=len(valid):raise ValueError("v4 uniqueness mismatch")
    db=sqlite3.connect(base["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("SQLite integrity mismatch")
    metadata={r["key"]:json.loads(r["value"]) for r in db.execute("SELECT * FROM metadata")}
    for k in ("codeSha","tariffManifestSha256","nationalArtifactProvenance","exactIdentityCandidatePairs"):
        if metadata[k]!=summary[k]:raise ValueError("Ledger provenance mismatch "+k)
    ns={};ps=collections.defaultdict(list)
    for row in db.execute("SELECT * FROM national_connector"):
        n=dict(row);ns[n["id"]]=n;ps[n["evse_normalized"]].append(n)
    ss={};siblings=collections.defaultdict(list)
    for row in db.execute("SELECT * FROM source_connector"):
        s=dict(row);ss[s["id"]]=s;siblings[(s["location_pk"],s["evse_pk"])].append(s)
    # Independent uniqueness on already validated pairs is reported separately;
    # existing v4 decisions are not rewritten by this exploratory audit.
    baseline_dependent=sum(not independent_unique(ss[s],ns[n],ps[ns[n]["evse_normalized"]],siblings[(ss[s]["location_pk"],ss[s]["evse_pk"])]) for n,s in valid)
    residual_rows=rows(residual["pairs.csv.gz"])
    if len(residual_rows)!=1317 or len({pair(r) for r in residual_rows})!=1317:raise ValueError("Residual cohort mismatch")
    if dict(collections.Counter(r["scope_diagnostic"] for r in residual_rows))!={DC:1254,MULTI:63}:raise ValueError("Residual count mismatch")
    def source_key(s):return s["location_pk"],s["evse_pk"],s["connector_pk"]
    wanted={source_key(ss[pair(r)[1]]) for r in residual_rows if ss[pair(r)[1]]["connector_pk"]}
    raw=cached_connectors(root/"tariff",pin["tariff"],summary["tariffManifestSha256"],wanted)
    counters=collections.Counter();operator=collections.Counter();reasons=collections.Counter();price_counts=collections.Counter()
    candidates={k:set() for k in SCENARIOS};simple={k:set() for k in SCENARIOS}
    output=[];ac_count=0;ac_independent=0;ac_simple=0
    for r in residual_rows:
        k=pair(r);n=ns[k[0]];s=ss[k[1]];v=prior_by_pair[k];c=json.loads(v["b_criteria"])
        if (v["b_decision"]!="REJECTED_CONTRADICTION" or c["power"]!="FAIL" or c["plug"]!="PASS" or c["current"]!="PASS"
            or Decimal(r["national_kw"])!=Decimal(str(n["kw"])) or Decimal(r["source_kw"])!=Decimal(str(s["kw"]))
            or r["station_id"]!=n["station_id"] or r["evse_id"]!=n["evse_id"]):
            raise ValueError("Residual/v4/ledger mismatch")
        blockers=[]
        if any(c.get(x)!="PASS" for x in ("station_identity","evse_identity","station_uniqueness","evse_uniqueness")):blockers.append("IDENTITY_OR_GLOBAL_UNIQUENESS")
        if any(c.get(x)=="FAIL" for x in ("country","operator","current","plug")):blockers.append("OTHER_CONTRADICTION")
        if not independent_unique(s,n,ps[n["evse_normalized"]],siblings[(s["location_pk"],s["evse_pk"])]):blockers.append("INDEPENDENT_CONNECTOR_UNIQUENESS_NOT_PROVEN")
        if k[0] in vn or k[1] in vs:blockers.append("V4_MATCH_ALREADY_EXISTS")
        if not s["has_price"]:blockers.append("MISSING_SOURCE_PRICE")
        observed=raw.get(source_key(s))
        if observed is None:
            price="ARCHIVED_CONNECTOR_NOT_FOUND";fields=[];blockers.append("RAW_CONNECTOR_NOT_PROVEN")
        else:
            ref,connector=observed
            if (ident(ref)!=s["reference_normalized"] or plug(connector.get("standard"))!=s["plug"]
                or mode(plug(connector.get("standard")))!=s["mode"] or number(connector.get("kilowatts"))!=s["kw"]
                or signature(connector)!=s["tariff_signature"]):
                raise ValueError("Archived connector differs from ledger")
            price,fields=tariff_gate(connector)
        if s["recent_fault"]:blockers.append("RECENT_FAULT_EXCLUSION")
        price_counts[(r["scope_diagnostic"],price)]+=1
        price_ok=price in ("DIRECT_SIMPLE_FREE","DIRECT_SIMPLE_ENERGY_OR_FLAT")
        flags=scenario_flags(n["kw"],s["kw"])
        row={**r,"independent_identity_scope":not blockers,"independent_blockers":json.dumps(blockers),
            "price_evidence":price,"price_condition_fields":json.dumps(fields),"source_signature_verified":observed is not None}
        if n["mode"]=="AC":
            # Separate diagnostic only, no implicit extension of v4.
            ac_count+=1
            if not blockers:ac_independent+=1
            if not blockers and price_ok:ac_simple+=1
            flags={x:False for x in SCENARIOS}
        for name,allowed in flags.items():
            if not allowed:
                row[name]="OUTSIDE_SCENARIO";continue
            counters[(name,"eligible_power_direction")]+=1
            if blockers:
                row[name]="BLOCKED_OTHER_EVIDENCE"
                for reason in blockers:reasons[(name,reason)]+=1
            else:
                candidates[name].add(k);counters[(name,"independent_identity_scope")]+=1
                if price_ok:
                    simple[name].add(k);row[name]="SIMPLE_PAYLOAD_CANDIDATE_NOT_PROMOTED"
                    operator[(name,r["national_operator"])]+=1
                else:
                    row[name]="TARIFF_REVIEW_REQUIRED";reasons[(name,price)]+=1
        output.append(row)
    if ac_count!=5:raise ValueError("AC separate cohort mismatch")
    for name in SCENARIOS:
        for group in (candidates[name],simple[name]):
            union=valid|group
            if valid&group or len({x[0] for x in union})!=len(union) or len({x[1] for x in union})!=len(union):
                raise ValueError("Scenario introduces duplicate or existing match")
    out=root/"results";out.mkdir()
    write_csv(out/"scenario-pairs.csv.gz",output,list(output[0]))
    report={"codeSha":os.environ.get("GITHUB_SHA"),"sourcePin":pin,"referenceValidated":len(valid),
        "baselineMatchesNotProvenIndependentOfPower":baseline_dependent,"residualPairs":len(output),"dcPairs":len(output)-ac_count,
        "scenarios":{k:{"directionEligible":counters[(k,"eligible_power_direction")],"independentIdentityScopeCandidates":len(candidates[k]),
            "simplePayloadCandidates":len(simple[k]),"tariffReviewRequired":len(candidates[k]-simple[k]),
            "projectedV4PlusSimpleCandidates":len(valid)+len(simple[k]),"existingMatchesReassigned":0,
            "distinctNationalPdcSimple":len({(ns[n]["station_id"],ns[n]["evse_id"]) for n,s in simple[k]})} for k in SCENARIOS},
        "acSeparateDiagnostic":{"pairs":ac_count,"independentIdentityScopeCandidates":ac_independent,"simplePayloadCandidates":ac_simple},
        "tariffEvidenceCounts":table(price_counts,["cohort","evidence"]),"blockingReasons":table(reasons,["scenario","reason"]),
        "simpleCandidatesByOperator":table(operator,["scenario","operator"]),"noDuplicateWithV4":True,
        "exportSha256":digest(out/"scenario-pairs.csv.gz"),"supplierCalls":0,"matchingRulesChanged":False,"pricesPromoted":0,
        "automaticPublication":False,"limitations":["Only the residual 1254 mono-type DC and 58 multi-type DC pairs; five AC separate diagnostic.",
            "B is cumulative A plus below nominal <=15 kW AND <=10% of IRVE, exploratory threshold not approved for implementation.",
            "New candidates must be unique even if power is ignored on both sides; existing v4 matches are preserved and not revalidated under a new policy.",
            "Simple direct payload without observed power conditions is not proof of actual tariff correctness, complete supplier schema or calculability; complex/time/unknown fields held.",
            "No ratings changed, no new matching validation or price publication."]}
    (out/"scenario-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("G5_POWER_IDENTITY_SCENARIOS "+json.dumps({k:v for k,v in report.items() if k not in ("sourcePin","simpleCandidatesByOperator")},ensure_ascii=False,sort_keys=True))
    print("G5_POWER_IDENTITY_TOP "+json.dumps(report["simpleCandidatesByOperator"][:30],ensure_ascii=False))
    db.close()
if __name__=="__main__":main()
