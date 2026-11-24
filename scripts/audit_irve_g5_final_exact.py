#!/usr/bin/env python3
"""Final exact residual evidence audit; no identity merging or matching changes."""
import collections
import csv
import json
import os
import pathlib
import sqlite3
import sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import rows,pair,table,cached_connectors,signature,independent_unique
from scripts.audit_irve_g5_restriction_replay import classify,RECOGNIZED
from scripts.audit_electroverse_g5_real_matching import ident,plug,mode,number,distance
from scripts.france.build_france_irve_static_v9 import key,get,enabled,supported_connectors,coordinates

RULE="g5-fr-2026-11-24-v5-exact-independent-power-divergence"
def j(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def sk(s):return s["location_pk"],s["evse_pk"],s["connector_pk"]
def fingerprint(s):
    return j([s["plug_raw"],s["plug"],s["mode"],s["kw"],s["has_price"],s["tariff_signature"]])
def owner_class(groups,locs):
    if len(groups)==1:
        return "ONE_SOURCE_OWNER"
    locations={k[0] for k in groups};pks={k[1] for k in groups}
    fps=[tuple(sorted(fingerprint(s) for s in ss)) for ss in groups.values()]
    xy=[(locs[x]["lat"],locs[x]["lon"]) for x in locations]
    complete=all(a is not None and b is not None for a,b in xy)
    if len(locations)==1:
        return "SAME_LOCATION_DISTINCT_EVSE_PK_IDENTICAL_PAYLOAD" if len(set(fps))==1 else "SAME_LOCATION_DISTINCT_EVSE_PK_DIFFERENT_PAYLOAD"
    if complete and len(set(xy))==1:
        return "DISTINCT_LOCATIONS_SAME_COORDS_IDENTICAL_PAYLOAD" if len(set(fps))==1 else "DISTINCT_LOCATIONS_SAME_COORDS_DIFFERENT_PAYLOAD"
    if complete:
        return "DISTINCT_LOCATIONS_DIFFERENT_COORDS"
    return "DISTINCT_LOCATIONS_COORDINATES_MISSING"

def raw_status(s,raw):
    x=raw.get(sk(s))
    if x is None:return "MISSING_OR_DUPLICATE_RAW_CONNECTOR_KEY",None
    ref,c=x
    if (ident(ref)!=s["reference_normalized"] or plug(c.get("standard"))!=s["plug"] or mode(plug(c.get("standard")))!=s["mode"] or number(c.get("kilowatts"))!=s["kw"] or signature(c)!=s["tariff_signature"]):
        raise ValueError("Archived connector/ledger mismatch")
    return "VERIFIED",c

def technical_review(n,s,raw_rows,c):
    flags={f for rr in raw_rows for f,v in rr["plug_flags"].items() if enabled(v)}
    expected={plug(x) for rr in raw_rows for x in rr["supported_types"]}
    source_std=(c or {}).get("standard")
    name=source_std.get("name") if isinstance(source_std,dict) else source_std
    if name=="IEC_62196_T3C":
        return "TYPE3C_DECLARED_OUTSIDE_TCC_SCOPE" if any("type3" in f for f in flags) else "TYPE3C_NOT_DECLARED_IN_RAW_IRVE"
    if s["plug"]=="CHADEMO":
        return "CHADEMO_DECLARED_OUTSIDE_TCC_SCOPE" if any("chademo" in f for f in flags) else "CHADEMO_NOT_DECLARED_IN_RAW_IRVE"
    if s["plug"] is None:return "SOURCE_PLUG_UNVERIFIED"
    if s["plug"]!=n["plug"]:
        return "SOURCE_TYPE_EXISTS_ON_OTHER_IRVE_PROFILE" if s["plug"] in expected else "SOURCE_TYPE_NOT_DECLARED_ON_IRVE_PDC"
    if s["mode"]!=n["mode"]:return "CURRENT_CONTRADICTION_OR_MISSING"
    return "SAME_SUPPORTED_TYPE_AND_CURRENT"

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_v5_final_exact_investigation_only" or pin["ruleVersion"]!=RULE or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Unapproved scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    led=download(root/"v5",pin["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    rp=pin["residual"]
    res=download(root/"residual",rp,{"pairs.csv.gz":("residual-exact-pairs.csv.gz",),"report.json":("residual-exact-report.json",)})
    nat=download(root/"national",pin["national"],{"static.csv":("raw","france-irve","static.csv")})
    for path,sha in ((led["db.sqlite"],pin["sqliteSha256"]),(res["pairs.csv.gz"],rp["pairsSha256"]),(nat["static.csv"],pin["rawSha256"])):verify(path,sha)
    vp,rr=[json.loads(x.read_text()) for x in (led["report.json"],res["report.json"])]
    if (vp["ruleVersion"]!=RULE or vp["codeSha"]!=pin["ledger"]["codeSha"] or vp["sqliteSha256"]!=pin["sqliteSha256"] or vp["newValidated"]!=14968
        or vp["sourcePin"]["tariff"]!=pin["tariff"] or vp["sourcePin"]["nationalArtifact"]!=pin["national"]["artifact"]
        or rr["codeSha"]!=rp["codeSha"] or rr["sourcePin"]["ledger"]!=pin["ledger"] or rr["sourcePin"]["sqliteSha256"]!=pin["sqliteSha256"]
        or rr["exportSha256"]["residual-exact-pairs.csv.gz"]!=rp["pairsSha256"] or rr["referenceValidated"]!=14968
        or rr["pairAllocation"]["BOTH_UNMATCHED"]!=408 or rr["matchingRulesChanged"] is not False):raise ValueError("Source provenance mismatch")
    allr=rows(res["pairs.csv.gz"]);target=[x for x in allr if x["allocation"]=="BOTH_UNMATCHED"]
    if len(allr)!=7012 or len(target)!=408 or len({pair(x) for x in target})!=408 or len({pair(x)[0] for x in target})!=240:raise ValueError("Cohort mismatch")
    expected={"IDENTITY_OR_UNIQUENESS_REVIEW":277,"TECHNICAL_CONTRADICTION_REVIEW":90,"POWER_REVIEW_NO_RELAXATION":32,"NOMENCLATURE_REVIEW":5,"SCOPE_OR_OTHER_EVIDENCE_REVIEW":4}
    if dict(collections.Counter(x["review_priority"] for x in target))!=expected:raise ValueError("Priority mismatch")
    db=sqlite3.connect(led["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("SQLite integrity")
    meta={x["key"]:json.loads(x["value"]) for x in db.execute("SELECT * FROM metadata")}
    if meta["ruleVersion"]!=RULE or meta["codeSha"]!=vp["codeSha"] or meta["electroverseTariffArtifact"]!=pin["tariff"]["artifact"]:raise ValueError("Embedded provenance mismatch")
    valid=list(db.execute("SELECT national_id,source_id FROM candidate WHERE decision='MATCH_VALIDATED'"))
    vn={x[0] for x in valid};vs={x[1] for x in valid}
    if len(valid)!=14968 or len(vn)!=14968 or len(vs)!=14968:raise ValueError("Validated set mismatch")
    ns={};ss={};byref=collections.defaultdict(list);sref=collections.defaultdict(list);siblings=collections.defaultdict(list);owners=collections.defaultdict(set)
    for x in db.execute("SELECT * FROM national_connector"):
        n=dict(x);ns[n["id"]]=n;byref[n["evse_normalized"]].append(n)
    for x in db.execute("SELECT * FROM national_operational_scope"):
        owners[ident(x["evse_id"])].add((x["station_id"],x["evse_id"],x["state"],x["eligible"]))
    for x in db.execute("SELECT * FROM source_connector"):
        s=dict(x);ss[s["id"]]=s;sref[s["reference_normalized"]].append(s);siblings[(s["location_pk"],s["evse_pk"])].append(s)
    locs={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_location")}
    stations={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_station")}
    refs={ns[pair(x)[0]]["evse_normalized"] for x in target}
    # Include every owner and sibling, not just the 408 unoccupied pairs.
    wanted={sk(s) for ref in refs for s in sref[ref]}
    raw=cached_connectors(root/"tariff",pin["tariff"],meta["tariffManifestSha256"],wanted)
    verified={s["id"]:raw_status(s,raw) for ref in refs for s in sref[ref]}
    national_raw=collections.defaultdict(list)
    with nat["static.csv"].open(encoding="utf-8-sig",errors="replace",newline="") as f:
        sample=f.read(65536);f.seek(0)
        try:dialect=csv.Sniffer().sniff(sample,delimiters=",;\t|")
        except csv.Error:dialect=csv.excel
        reader=csv.DictReader(f,dialect=dialect)
        flags={key(x) for x in reader.fieldnames if key(x).startswith("prisetype") or key(x)=="priseautre"}
        if not {"prisetypeef","prisetype2","prisetypecomboccs"}<=flags:raise ValueError("Missing raw flags")
        for row in reader:
            x={key(k):v for k,v in row.items() if k}
            evse=get(x,"id_pdc_itinerance");ref=ident(evse)
            if ref not in refs:continue
            sid=get(x,"id_station_itinerance","id_station_local") or evse
            national_raw[ref].append(dict(station_id=sid,evse_id=evse,local_id=get(x,"id_pdc_local"),nominal_raw=get(x,"puissance_nominale","puissance"),
                plug_flags={k:x.get(k) for k in sorted(flags)},supported_types=supported_connectors(x),coords=coordinates(x)))
    groups=[];owner_rows=[];groups_by_ref={};groupcounts=collections.Counter()
    for ref in sorted(refs):
        sg=collections.defaultdict(list)
        for s in sref[ref]:sg[(s["location_pk"],s["evse_pk"])].append(s)
        status=owner_class(sg,locs);groupcounts[status]+=1
        coords=[]
        for (loc,epk),sr in sorted(sg.items()):
            l=locs[loc];owner_rows.append({"reference":ref,"location_pk":loc,"evse_pk":epk,"operator":l["operator_name"],"operator_id":l["operator_id"],"address":l["address"],"lat":l["lat"],"lon":l["lon"],"mapped_station":l["mapped_station"],
                "source_ids":j([s["id"] for s in sr]),"connectors":j([{k:s[k] for k in ("id","connector_pk","physical_reference","plug_raw","plug","mode","kw","tariff_signature","has_price","recent_fault")} | {"raw_status":verified[s["id"]][0],"already_validated":s["id"] in vs} for s in sr]),
                "payload_fingerprint":j(sorted(fingerprint(s) for s in sr))})
            if l["lat"] is not None and l["lon"] is not None:coords.append((l["lat"],l["lon"]))
        maxdist=max((distance(a,b) for a in coords for b in coords),default=None)
        rrn=national_raw[ref]
        if not rrn:raise ValueError("Missing raw national row")
        g={"reference":ref,"owner_class":status,"source_owner_count":len(sg),"source_location_count":len({x[0] for x in sg}),"source_evse_pk_count":len({x[1] for x in sg}),
            "national_station_owner_count":len({x[0] for x in owners[ref]}),"national_profile_count":len(byref[ref]),"source_connector_count":len(sref[ref]),
            "max_source_distance_m":maxdist,"source_raw_reference_variants":j(sorted({s["physical_reference"] for s in sref[ref]})),
            "national_raw_reference_variants":j(sorted({x["evse_id"] for x in rrn})),"national_scope":j(sorted(owners[ref])),
            "raw_national_rows":j(rrn),"identity_proof":"NOT_PROVEN_BY_PAYLOAD_SIMILARITY"}
        groups.append(g);groups_by_ref[ref]=g
    results=[];counts=collections.Counter();tech=collections.Counter();rawcounts=collections.Counter();c_counts=collections.Counter();potential=set();globalrefs=set()
    for x in target:
        n_id,s_id=pair(x);n,s=ns[n_id],ss[s_id];ref=n["evse_normalized"]
        if n_id in vn or s_id in vs or ref!=s["reference_normalized"] or ref!=x["evse_normalized"]:raise ValueError("Free pair mismatch")
        row=db.execute("SELECT c.decision,p.criteria,x.c_review,x.c_blockers FROM candidate c JOIN criterion_pattern p ON p.id=c.pattern_id JOIN v5_exact_replay x USING(national_id,source_id) WHERE c.national_id=? AND c.source_id=?",(n_id,s_id)).fetchone()
        criteria=json.loads(row["criteria"])["criteria"]
        if row["decision"]!=x["decision"] or criteria!=json.loads(x["v5_criteria"]) or row["c_review"]!=x["c_review"] or json.loads(row["c_blockers"])!=json.loads(x["c_blockers"]):raise ValueError("Residual decision changed")
        g=groups_by_ref[ref];status,c=verified[s_id]
        rrn=[v for v in national_raw[ref] if v["station_id"]==n["station_id"] and v["evse_id"]==n["evse_id"]]
        if not rrn:raise ValueError("Raw PDC row mismatch")
        t=technical_review(n,s,rrn,c);evidence,issues,*_=classify(c) if c is not None else ("RAW_UNVERIFIED",["RAW_UNVERIFIED"],[],[],[])
        independent=independent_unique(s,n,byref[ref],siblings[(s["location_pk"],s["evse_pk"])])
        global_unique=g["source_owner_count"]==1 and g["national_station_owner_count"]==1
        # A diagnostic only: no automatic new matches, no identity from homogeneity.
        blockers=[]
        if not global_unique:blockers.append("GLOBAL_OWNER_AMBIGUITY")
        if not independent:blockers.append("CONNECTOR_UNIQUENESS_NOT_PROVEN")
        if t!="SAME_SUPPORTED_TYPE_AND_CURRENT":blockers.append(t)
        if status!="VERIFIED":blockers.append(status)
        if not s["has_price"]:blockers.append("NO_PRICE_PAYLOAD")
        if s["recent_fault"]:blockers.append("RECENT_FAULT")
        if evidence not in (RECOGNIZED,"DIRECT_SIMPLE_NO_OBSERVED_POWER_CONDITION","DIRECT_FREE_NO_OBSERVED_POWER_CONDITION") or issues:blockers.append("TARIFF_SCHEMA_REVIEW")
        if any(v=="FAIL" for k,v in criteria.items() if k!="power"):blockers.append("OTHER_V5_CONTRADICTION")
        if criteria["power"]=="FAIL":blockers.append("POWER_RULE_REVIEW_REQUIRED")
        if not blockers:potential.add((n_id,s_id))
        if x["review_priority"]=="IDENTITY_OR_UNIQUENESS_REVIEW":globalrefs.add(ref)
        counts[(x["review_priority"],g["owner_class"])]+=1;tech[(x["review_priority"],t)]+=1;rawcounts[status]+=1;c_counts[(x["review_priority"],x["c_review"])]+=1
        results.append({**x,"owner_class":g["owner_class"],"source_owner_count":g["source_owner_count"],"national_station_owner_count":g["national_station_owner_count"],
            "global_unique":global_unique,"independent_connector_unique":independent,"source_raw_status":status,"tariff_schema":evidence,"tariff_schema_issues":j(issues),
            "technical_raw_review":t,"national_raw_rows":j(rrn),"national_station_coords":j([stations[n["station_id"]]["lat"],stations[n["station_id"]]["lon"]]),
            "source_location_coords":j([locs[s["location_pk"]]["lat"],locs[s["location_pk"]]["lon"]]),"additional_diagnostic_blockers":j(blockers),
            "disposition":"RETAIN_V5_NO_AUTOMATIC_CHANGE"})
    out=root/"results";out.mkdir()
    exports={"final-exact-pairs.csv.gz":results,"identity-groups.csv.gz":groups,"source-owners.csv.gz":owner_rows}
    for name,data in exports.items():write_csv(out/name,data,list(data[0]))
    report={"codeSha":os.environ.get("GITHUB_SHA"),"sourcePin":pin,"referenceValidated":14968,"reviewedPairs":len(results),"reviewedNationalProfiles":240,
        "distinctReferences":len(refs),"identityPriorityDistinctReferences":len(globalrefs),"ownerGroups":dict(groupcounts),
        "identityPriorityOwnerGroups":dict(collections.Counter(groups_by_ref[x]["owner_class"] for x in globalrefs)),
        "pairOwnerDiagnostics":table(counts,["priority","owner_class"]),"rawTechnicalDiagnostics":table(tech,["priority","diagnostic"]),
        "rawConnectorStatus":dict(rawcounts),"cReviewByPriority":table(c_counts,["priority","c_review"]),
        "powerAndScopeDetails":table(collections.Counter((x["review_priority"],x["c_review"],x["additional_diagnostic_blockers"]) for x in results if x["review_priority"] in ("POWER_REVIEW_NO_RELAXATION","SCOPE_OR_OTHER_EVIDENCE_REVIEW")),["priority","c_review","blockers"]),
        "pairsWithNoAdditionalDiagnosticBlocker":len(potential),"profilesWithNoAdditionalDiagnosticBlocker":len({n for n,s in potential}),
        "newMatches":0,"matchingRulesChanged":False,"supplierCalls":0,"pricesPromoted":0,"automaticPublication":False,
        "limitations":["Same coordinates or identical raw tariff/connector fingerprints do not prove a duplicate physical EVSE.",
            "Source owner ambiguity remains blocked; no automatic merging or reassignment.",
            "CHAdeMO and Type 3C deliberately outside current national TCC connector projection.",
            "No additional diagnostic blocker does not mean validated scope or G6 calculability.",
            "Archived data only; no current availability proven."]}
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"final-exact-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("G5_FINAL_EXACT "+j({k:v for k,v in report.items() if k!="sourcePin"}))
    db.close()
if __name__=="__main__":main()
