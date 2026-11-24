#!/usr/bin/env python3
"""Inventory nonexact candidates and archived alias evidence, no promotion."""
import collections
import csv
import gzip
import json
import os
import pathlib
import sqlite3
import sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import table,cached_connectors,signature
from scripts.audit_irve_g5_restriction_replay import classify
from scripts.audit_electroverse_g5_real_matching import ident,norm,plug,mode,number,state,decision_from_criteria

RULE="g5-fr-2026-11-24-v5-exact-independent-power-divergence"
VALID="MATCH_VALIDATED"
def j(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def sk(s):return s["location_pk"],s["evse_pk"],s["connector_pk"]
def allocation(n,s):return "BOTH_ALREADY_MATCHED" if n and s else "NATIONAL_ALREADY_MATCHED" if n else "SOURCE_ALREADY_MATCHED" if s else "BOTH_UNMATCHED"
def evidence_class(method,aliases,prior,address=None,gps=None):
    if method.startswith("validated_alias+"):return "DOCUMENTED_ALIAS"
    if aliases:return "ALIAS_LEDGER_INCONSISTENCY"
    if method.startswith("address+") and address=="PASS":return "ADDRESS"
    if method.startswith("gps+") and gps=="PASS":return "GPS"
    if prior:return "HISTORICAL_OFFER_ONLY"
    return "OTHER_UNPROVEN_SITE"

def alias_scope(s,n,ns,ss):
    # Include missing attributes as possible competitors. No power relaxation.
    def compatible(a,b):
        return all(state(a[k],b[k])!="FAIL" for k in ("plug","mode")) and (a["kw"] is None or b["kw"] is None or a["kw"]>0 and b["kw"]>0 and round(a["kw"],1)==round(b["kw"],1))
    return ([x["id"] for x in ns if compatible(s,x)],[x["id"] for x in ss if compatible(x,n)])

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_v5_nonexact_alias_inventory_only" or pin["ruleVersion"]!=RULE or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Wrong scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    src=download(root/"v5",pin["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    verify(src["db.sqlite"],pin["sqliteSha256"])
    rp=json.loads(src["report.json"].read_text())
    if rp["codeSha"]!=pin["ledger"]["codeSha"] or rp["ruleVersion"]!=RULE or rp["sqliteSha256"]!=pin["sqliteSha256"] or rp["newValidated"]!=14968 or rp["nonExactUnchanged"]!=559998 or rp["sourcePin"]["tariff"]!=pin["tariff"]:raise ValueError("V5 provenance")
    db=sqlite3.connect(src["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("SQLite integrity")
    meta={x["key"]:json.loads(x["value"]) for x in db.execute("SELECT * FROM metadata")}
    if meta["ruleVersion"]!=RULE or meta["codeSha"]!=rp["codeSha"]:raise ValueError("Metadata provenance")
    valid=list(db.execute("SELECT national_id,source_id FROM candidate WHERE decision=?",(VALID,)))
    vn={x[0] for x in valid};vs={x[1] for x in valid}
    if len(valid)!=14968 or len(vn)!=14968 or len(vs)!=14968:raise ValueError("V5 validated mismatch")
    ns={};ss={};nref=collections.defaultdict(list);sref=collections.defaultdict(list);sg=collections.defaultdict(list);owners=collections.defaultdict(set)
    for x in db.execute("SELECT * FROM national_connector"):
        n=dict(x);ns[n["id"]]=n;nref[n["evse_normalized"]].append(n)
    for x in db.execute("SELECT * FROM national_operational_scope"):
        owners[ident(x["evse_id"])].add((x["station_id"],x["evse_id"],x["eligible"]))
    for x in db.execute("SELECT * FROM source_connector"):
        s=dict(x);ss[s["id"]]=s;sref[s["reference_normalized"]].append(s);sg[(s["location_pk"],s["evse_pk"])].append(s)
    locs={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_location")}
    stations={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_station")}
    review=pathlib.Path("data/platforms/electroverse/validated-mappings")
    alias_index=collections.defaultdict(list);registry_rows=[];registry_counts=collections.Counter()
    targets=collections.defaultdict(set);reverse=collections.defaultdict(set)
    for filename,sha in meta["aliasEvidenceSha256"].items():
        p=review/filename;verify(p,sha)
        doc=json.loads(p.read_text())
        for i,r in enumerate(doc.get("mappings",[])):
            loc,epk,ref,tgt=[str(r.get(k) or "") for k in ("electroverseLocationPk","electroverseEvsePk","physicalReference","targetPdc")]
            k=(loc,epk,ident(ref));target=ident(tgt)
            usable=bool(loc and epk and ref and tgt and r.get("evidence"))
            if usable:
                alias_index[(*k,target)].append((filename,i,r));targets[k].add(target);reverse[target].add(k)
            registry_rows.append({"file":filename,"row_index":i,"location_pk":loc,"evse_pk":epk,"reference":ref,"target_pdc":tgt,"evidence_present":usable,"raw_mapping":j(r)})
            registry_counts[(filename,"EVIDENCE_PRESENT" if usable else "NO_EXPLICIT_EVIDENCE_FIELD")]+=1
    opfile=review/"g5-operator-crosswalk-review.json";verify(opfile,meta["operatorRegistrySha256"])
    op=json.loads(opfile.read_text());approved={(str(x["supplierOperatorId"]),norm(x["nationalOperator"])) for x in op["approvedPairs"]}
    out=root/"results";out.mkdir()
    # Retain compact per-pair pointer and allocation; authoritative detail remains in the pinned ledger.
    patterns={x["id"]:json.loads(x["criteria"]) for x in db.execute("SELECT * FROM criterion_pattern")}
    summary=collections.Counter();decisions=collections.Counter();first=collections.Counter();blockers=collections.Counter()
    free_profiles=collections.defaultdict(set);free_sources=collections.defaultdict(set);free_stations=collections.defaultdict(set)
    alias_candidates=[];observed_registry=set();total=0;free=0
    sql="""SELECT c.* FROM candidate c LEFT JOIN v5_exact_replay x USING(national_id,source_id)
      WHERE x.national_id IS NULL ORDER BY c.national_id,c.source_id"""
    with gzip.open(out/"nonexact-inventory.csv.gz","wt",encoding="utf-8",newline="") as f:
        cols=["national_id","source_id","method","category","allocation","decision","first_blocker","pattern_id","alias_files","prior_offer_count","operator_criterion","address_observation","gps_observation","distance_m"]
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for row in db.execute(sql):
            n,s=ns[row["national_id"]],ss[row["source_id"]];a=allocation(n["id"] in vn,s["id"] in vs)
            if row["decision"]==VALID or row["method"].startswith("exact+") or s["reference_normalized"] and s["reference_normalized"]==n["evse_normalized"]:raise ValueError("Unexpected exact or validated row")
            af=json.loads(row["alias_files"]);prior=json.loads(row["prior_offer_ids"]);d=json.loads(row["details"]);pat=patterns[row["pattern_id"]];c=pat["criteria"]
            cat=evidence_class(row["method"],af,prior,d["address_observation"],d["gps_observation"])
            if cat=="ALIAS_LEDGER_INCONSISTENCY":raise ValueError("Alias method inconsistency")
            total+=1;summary[(cat,a)]+=1;decisions[(cat,row["decision"])]+=1
            if a=="BOTH_UNMATCHED":
                free+=1;free_profiles[cat].add(n["id"]);free_sources[cat].add(s["id"]);free_stations[cat].add(n["station_id"])
                first[(cat,row["first_blocker"] or "NONE")]+=1
                for z in pat["blocking"]:blockers[(cat,z)]+=1
            w.writerow(dict(national_id=n["id"],source_id=s["id"],method=row["method"],category=cat,allocation=a,decision=row["decision"],first_blocker=row["first_blocker"],pattern_id=row["pattern_id"],alias_files=row["alias_files"],prior_offer_count=len(prior),operator_criterion=c["operator"],address_observation=d["address_observation"],gps_observation=d["gps_observation"],distance_m=d["distance_m"]))
            if cat=="DOCUMENTED_ALIAS":
                k=(s["location_pk"],s["evse_pk"],s["reference_normalized"],n["evse_normalized"])
                evidence=alias_index[k]
                if not evidence or set(af)!={z[0] for z in evidence}:raise ValueError("Alias source/target/file mismatch")
                for name,i,_ in evidence:observed_registry.add((name,i))
                alias_candidates.append((dict(row),n,s,a,pat,d,evidence))
    if total!=559998:raise ValueError("Nonexact total mismatch")
    wanted={sk(x[2]) for x in alias_candidates}
    raw=cached_connectors(root/"tariff",pin["tariff"],meta["tariffManifestSha256"],wanted) if wanted else {}
    alias_rows=[];alias_stats=collections.Counter();alias_by_file=collections.Counter();alias_blockers=collections.Counter()
    for row,n,s,a,pat,d,evidence in alias_candidates:
        k=(s["location_pk"],s["evse_pk"],s["reference_normalized"]);target=n["evse_normalized"];c=pat["criteria"]
        res=decision_from_criteria(c)
        if res["decision"]!=row["decision"] or res["blocking"]!=pat["blocking"]:raise ValueError("Alias decision mismatch")
        reason=[]
        if a!="BOTH_UNMATCHED":reason.append("EXISTING_MATCH_NO_REASSIGNMENT")
        if len(targets[k])!=1 or len(reverse[target])!=1:reason.append("ALIAS_REGISTRY_NOT_BIJECTIVE")
        if len(owners[target])!=1:reason.append("NATIONAL_EVSE_OWNER_NOT_UNIQUE")
        if not s["reference_normalized"] or len({(x["location_pk"],x["evse_pk"]) for x in sref[s["reference_normalized"]]})!=1:reason.append("SOURCE_EVSE_OWNER_NOT_UNIQUE")
        if s["reference_normalized"] in nref:reason.append("SOURCE_HAS_EXACT_NATIONAL_REFERENCE")
        if (locs[s["location_pk"]]["operator_id"],norm(stations[n["station_id"]]["operator"])) not in approved:reason.append("INDEPENDENT_OPERATOR_PROOF_NOT_IN_REGISTRY")
        if any(c[x]=="FAIL" for x in ("country","operator","plug","current","power")):reason.append("TECHNICAL_OR_COUNTRY_OPERATOR_CONTRADICTION")
        if c["plug"]!="PASS" or c["current"]!="PASS" or c["power"]!="PASS":reason.append("POSITIVE_TECHNICAL_PROOF_INCOMPLETE")
        lhs,rhs=alias_scope(s,n,nref[target],sg[(s["location_pk"],s["evse_pk"])])
        if lhs!=[n["id"]] or rhs!=[s["id"]]:reason.append("BIDIRECTIONAL_CONNECTOR_SCOPE_UNPROVEN")
        if not s["has_price"]:reason.append("NO_PRICE_PAYLOAD")
        if s["recent_fault"]:reason.append("RECENT_HISTORICAL_FAULT")
        obs=raw.get(sk(s));tariff="RAW_UNVERIFIED";issues=[]
        if obs is None:reason.append("RAW_CONNECTOR_MISSING_OR_AMBIGUOUS")
        else:
            ref,conn=obs
            if ident(ref)!=s["reference_normalized"] or plug(conn.get("standard"))!=s["plug"] or mode(plug(conn.get("standard")))!=s["mode"] or number(conn.get("kilowatts"))!=s["kw"] or signature(conn)!=s["tariff_signature"]:raise ValueError("Alias raw signature mismatch")
            tariff,issues,*_=classify(conn)
        if any("donor" in key.lower() for _,_,ev in evidence for key in ev):reason.append("HISTORICAL_DONOR_EVIDENCE_REVIEW")
        for _,_,ev in evidence:
            station=ev.get("irveStationId") or (ev["evidence"].get("irveStationId") if isinstance(ev.get("evidence"),dict) else None)
            if station and station!=n["station_id"]:reason.append("DOCUMENTED_STATION_DIFFERS")
        reason=sorted(set(reason));status="NEEDS_EVIDENCE_REVIEW" if reason else "NO_ADDITIONAL_DIAGNOSTIC_BLOCKER_NOT_VALIDATED"
        alias_stats[(a,status)]+=1
        for z in reason:alias_blockers[(a,z)]+=1
        for name in {e[0] for e in evidence}:alias_by_file[(name,a)]+=1
        alias_rows.append({"national_id":n["id"],"source_id":s["id"],"station_id":n["station_id"],"evse_id":n["evse_id"],"location_pk":s["location_pk"],"evse_pk":s["evse_pk"],"connector_pk":s["connector_pk"],"physical_reference":s["physical_reference"],"allocation":a,"method":row["method"],"national_operator":stations[n["station_id"]]["operator"],"source_operator":locs[s["location_pk"]]["operator_name"],"source_operator_id":locs[s["location_pk"]]["operator_id"],"national_plug":n["plug"],"source_plug":s["plug"],"national_kw":n["kw"],"source_kw":s["kw"],"criteria":j(c),"original_blockers":j(pat["blocking"]),"additional_diagnostic_blockers":j(reason),"candidate_national_ids":j(lhs),"candidate_source_ids":j(rhs),"tariff_schema":tariff,"tariff_schema_issues":j(issues),"source_tariff_signature":s["tariff_signature"],"alias_evidence":j(evidence),"review_status":status})
    for z in registry_rows:z["observed_nonexact_candidate"]=(z["file"],z["row_index"]) in observed_registry
    write_csv(out/"alias-registry-inventory.csv.gz",registry_rows,list(registry_rows[0]))
    if alias_rows:write_csv(out/"alias-candidates.csv.gz",alias_rows,list(alias_rows[0]))
    report={"codeSha":os.environ.get("GITHUB_SHA"),"sourcePin":pin,"referenceValidated":14968,"nonExactPairs":total,"freePairs":free,
        "categories":table(summary,["category","allocation"]),"decisions":table(decisions,["category","decision"]),
        "freeDistinctProfilesByCategory":{k:len(v) for k,v in free_profiles.items()},"freeDistinctSourcesByCategory":{k:len(v) for k,v in free_sources.items()},"freeDistinctStationsByCategory":{k:len(v) for k,v in free_stations.items()},
        "freeDistinctProfiles":len(set().union(*free_profiles.values())),"freeDistinctSources":len(set().union(*free_sources.values())),
        "freeFirstBlockers":table(first,["category","reason"]),"freeAllBlockersNonExclusive":table(blockers,["category","reason"]),
        "aliasRegistryRows":len(registry_rows),"aliasRegistryEvidence":table(registry_counts,["file","status"]),"aliasRegistryRowsObserved":len(observed_registry),
        "aliasPairs":len(alias_rows),"aliasFreePairs":sum(x["allocation"]=="BOTH_UNMATCHED" for x in alias_rows),"aliasReview":table(alias_stats,["allocation","status"]),
        "aliasByFile":table(alias_by_file,["file","allocation"]),"aliasDiagnosticBlockers":table(alias_blockers,["allocation","reason"]),"approvedOperatorRegistryPairs":len(approved),
        "newMatches":0,"matchingRulesChanged":False,"supplierCalls":0,"pricesPromoted":0,"automaticPublication":False,
        "limitations":["Inventory of previously generated candidates, not discovery of new aliases or new geographic candidates.","Alias registry is historical evidence, not automatic proof of scope or operator.","Operator crosswalk absence is not proof of operator mismatch; other independent evidence may be reviewed subsequently.","Free candidates do not imply valid identity; category profile counts overlap.","No G6 calculation or publication."]}
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"nonexact-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("G5_NONEXACT_INVENTORY "+j({k:v for k,v in report.items() if k!="sourcePin"}))
    db.close()
if __name__=="__main__":main()
