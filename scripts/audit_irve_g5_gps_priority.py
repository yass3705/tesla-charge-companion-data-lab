#!/usr/bin/env python3
"""Audit GPS priority cohort; never modify ledger or assign prices."""
import collections as C
import hashlib
import json
import os
import pathlib
import sqlite3
import sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import cached_connectors,signature,rows,table
from scripts.audit_irve_g5_restriction_replay import classify
from scripts.audit_irve_g5_nonexact_inventory import RULE,VALID,sk,j
from scripts.audit_irve_g5_address_gps import compatible
from scripts.audit_electroverse_g5_real_matching import ident,plug,mode,number,norm

def shortlist(x):
    c=json.loads(x["criteria"]);d=set(json.loads(x["diagnostic"]))
    return (x["allocation"]=="BOTH_UNMATCHED"
        and not d.intersection({"BIDIRECTIONAL_TECHNICAL_SCOPE_NOT_UNIQUE","GPS_SITE_NOT_UNIQUE","POSITIVE_TECHNICAL_PROOF_INCOMPLETE","NO_PRICE"})
        and c.get("country")!="FAIL" and c.get("operator")!="FAIL")

def priority(x,site):
    return shortlist(x) and json.loads(x["criteria"]).get("evse_uniqueness")=="PASS" and site["national_pdc_count"]==site["source_evse_count"]

def perfect(graph, excluded=None):
    # Maximum matching of equal-size group sets; missing metadata remain competitors.
    owner={}
    def visit(a,seen):
        for b in sorted(graph[a]):
            if (a,b)==excluded or b in seen:continue
            seen.add(b)
            if b not in owner or visit(owner[b],seen):
                owner[b]=a;return True
        return False
    for a in sorted(graph):
        if not visit(a,set()):return None
    return {a:b for b,a in owner.items()}

def group_graph(n,s):
    # A group is compatible only if all its connector profiles can be paired.
    graph={}
    for a,aa in n.items():
        graph[a]=set()
        for b,bb in s.items():
            if len(aa)!=len(bb):continue
            g={i:{k for k,y in enumerate(bb) if compatible(x,y)} for i,x in enumerate(aa)}
            if perfect(g) is not None:graph[a].add(b)
    return graph

def classify_site(n,s):
    if len(n)!=len(s) or not n:return "GROUP_COUNT_DIFFERS",{},set()
    g=group_graph(n,s);m=perfect(g)
    if m is None:return "NO_COMPLETE_TECHNICAL_BIJECTION",{},set()
    forced={(a,b) for a,b in m.items() if perfect(g,(a,b)) is None}
    return ("UNIQUE_TECHNICAL_BIJECTION" if len(forced)==len(m) else "MULTIPLE_TECHNICAL_BIJECTIONS"),m,forced

# Explicit ID fields only; never treat arbitrary numeric values or text mentions as a crosswalk.
ID_KEYS={"evseid","evseids","irveevseid","irveevseids","idpdcitinerance","targetpdc","pdcid","pdcids","officialevseid","sourceevseid","sourceevseids","physicalreference","physicalreferences","appId".lower(),"identitynormalized","externalid","externalids","connectorid","sourceconnectorid","officialconnectorid","sourceevsepk","sourcelocationpk","electroverseevsepk","electroverselocationpk"}
def explicit_ids(record):
    out={}
    for k,v in record.items():
        key="".join(ch for ch in k.lower() if ch.isalnum())
        if key not in ID_KEYS:continue
        vals=v if isinstance(v,list) else [v]
        vs={ident(x) for x in vals if isinstance(x,(str,int)) and not isinstance(x,bool) and x}
        if vs:out[k]=vs
    return out

def records(obj,path="$"):
    if isinstance(obj,dict):
        ids=explicit_ids(obj)
        if ids:yield path,ids,obj
        for k,v in obj.items():
            if isinstance(v,(dict,list)):yield from records(v,path+"."+k)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            if isinstance(v,(dict,list)):yield from records(v,path+"["+str(i)+"]")

def gitblob(data):
    return hashlib.sha1(("blob "+str(len(data))+"\0").encode()+data).hexdigest()

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_g5_gps_priority_evidence_only" or pin["ruleVersion"]!=RULE or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    base=download(root/"v5",pin["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    verify(base["db.sqlite"],pin["sqliteSha256"])
    rp=json.loads(base["report.json"].read_text())
    if rp["codeSha"]!=pin["ledger"]["codeSha"] or rp["ruleVersion"]!=RULE or rp["sourcePin"]["tariff"]!=pin["tariff"] or rp["newValidated"]!=14968:raise ValueError("Ledger lineage")
    gps=download(root/"gps",pin["gps"],{"gps-pairs.csv.gz":("gps-pairs.csv.gz",),"gps-stations.csv.gz":("gps-stations.csv.gz",),"report.json":("address-gps-report.json",)})
    for name,sha in pin["gpsExports"].items():verify(gps[name],sha)
    gr=json.loads(gps["report.json"].read_text())
    if gr["codeSha"]!=pin["gps"]["codeSha"] or gr["sourcePin"]["ledger"]!=pin["ledger"] or gr["sourcePin"]["tariff"]!=pin["tariff"] or gr["referenceValidated"]!=14968 or gr["gpsPairs"]!=547654 or gr["freeGpsPairs"]!=519456:raise ValueError("GPS lineage")
    site_lookup={(x["location_pk"],x["station_id"]):x for x in rows(gps["gps-stations.csv.gz"])}
    selected=[];short=0;unique=0
    import gzip,csv
    with gzip.open(gps["gps-pairs.csv.gz"],"rt",encoding="utf-8",newline="") as f:
        for x in csv.DictReader(f):
            if not shortlist(x):continue
            short+=1;unique+=json.loads(x["criteria"]).get("evse_uniqueness")=="PASS"
            if priority(x,site_lookup[(x["location_pk"],x["station_id"])]):selected.append(x)
    if (short,unique,len(selected),sum(float(x["distance_m"])<=5 for x in selected))!=(3271,2033,987,435):raise ValueError("Priority cohort mismatch")
    db=sqlite3.connect(base["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Ledger integrity")
    meta={x["key"]:json.loads(x["value"]) for x in db.execute("SELECT * FROM metadata")}
    if meta["ruleVersion"]!=RULE or meta["codeSha"]!=rp["codeSha"]:raise ValueError("Metadata")
    valid={(x[0],x[1]) for x in db.execute("SELECT national_id,source_id FROM candidate WHERE decision=?",(VALID,))}
    vn={a for a,b in valid};vs={b for a,b in valid}
    if len(valid)!=14968 or len(vn)!=14968 or len(vs)!=14968:raise ValueError("Reference")
    ns={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_connector")}
    ss={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_connector")}
    locs={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_location")}
    sites={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_station")}
    byn=C.defaultdict(lambda:C.defaultdict(list));bys=C.defaultdict(lambda:C.defaultdict(list));refowners=C.defaultdict(set)
    for n in ns.values():byn[n["station_id"]][n["evse_id"]].append(n)
    for s in ss.values():
        bys[s["location_pk"]][s["evse_pk"]].append(s)
        if s["reference_normalized"]:refowners[s["reference_normalized"]].add((s["location_pk"],s["evse_pk"]))
    sitekeys={(x["location_pk"],x["station_id"]) for x in selected}
    wanted={sk(s) for loc,_ in sitekeys for g in bys[loc].values() for s in g if s["connector_pk"]}
    raw=cached_connectors(root/"tariff",pin["tariff"],meta["tariffManifestSha256"],wanted)
    # Archive indexes keyed by explicitly named identities. A CPO hit is corroboration only.
    target_ids={ns[int(x["national_id"])]["evse_normalized"] for x in selected}
    indices=C.defaultdict(list);archive_info={}
    for filename,expected in pin["evidenceBlobs"].items():
        data=pathlib.Path(filename).read_bytes()
        if gitblob(data)!=expected:raise ValueError("Evidence blob mismatch "+filename)
        doc=json.loads(data);nrec=0
        for path,ids,record in records(doc):
            nrec+=1
            union=set().union(*ids.values())
            for t in union&target_ids:
                indices[t].append((filename,path,ids,record))
        archive_info[filename]={"gitBlob":expected,"sha256":hashlib.sha256(data).hexdigest(),"explicitIdRecords":nrec}
    site_results={};site_rows=[]
    for loc,sid in sorted(sitekeys):
        n,s=byn[sid],bys[loc]
        status,m,forced=classify_site(n,s)
        # Complete source set, including occupied and missing competitor groups.
        known={(ns[a]["evse_id"],ss[b]["evse_pk"]) for a,b in valid if ns[a]["station_id"]==sid and ss[b]["location_pk"]==loc}
        conflicts=sum(a in m and m[a]!=b for a,b in known)
        missing=sum(not p for p in s)
        nprofiles=sum(map(len,n.values()));sprofiles=sum(map(len,s.values()))
        unique_signatures={tuple(sorted(y["tariff_signature"] for y in g)) for g in s.values()}
        site_results[(loc,sid)]=(status,m,forced,conflicts,missing)
        site_rows.append(dict(location_pk=loc,station_id=sid,national_operator=sites[sid]["operator"],status=status,national_groups=len(n),source_groups=len(s),national_profiles=nprofiles,source_profiles=sprofiles,forced_group_pairs=len(forced),existing_exact_anchor_groups=len(known),anchor_conflicts=conflicts,missing_source_group_ids=missing,source_group_tariff_signature_count=len(unique_signatures)))
    approved=json.loads(pathlib.Path("data/platforms/electroverse/validated-mappings/g5-operator-crosswalk-review.json").read_text())["approvedPairs"]
    verify(pathlib.Path("data/platforms/electroverse/validated-mappings/g5-operator-crosswalk-review.json"),meta["operatorRegistrySha256"])
    output=[];counts=C.Counter();byop=C.Counter()
    for x in selected:
        n,s=ns[int(x["national_id"])],ss[int(x["source_id"])]
        if n["id"] in vn or s["id"] in vs:raise ValueError("Occupied candidate")
        loc,sid=s["location_pk"],n["station_id"]
        status,m,forced,conflicts,missing=site_results[(loc,sid)]
        force=(n["evse_id"],s["evse_pk"]) in forced
        obs=raw.get(sk(s));raw_state="MISSING_OR_AMBIGUOUS";schema="NOT_EVALUATED";issues=[]
        if obs is not None:
            ref,conn=obs
            if ident(ref)!=s["reference_normalized"] or plug(conn.get("standard"))!=s["plug"] or mode(plug(conn.get("standard")))!=s["mode"] or number(conn.get("kilowatts"))!=s["kw"] or signature(conn)!=s["tariff_signature"]:raise ValueError("Raw connector mismatch")
            raw_state="VERIFIED";schema,issues,*_=classify(conn)
        records_found=[];bridge=False;app=False;pd=False
        for filename,path,ids,record in indices[n["evse_normalized"]]:
            # An ID in an archive is not itself a CPO or cross-system proof.
            ref=s["reference_normalized"]
            refkeys=[k for k,v in ids.items() if ref and ref in v and ref!=n["evse_normalized"]]
            if refkeys:bridge=True
            if filename.endswith("app-evidence-four-extra-exact-2026-10-11.json") and str(record.get("sourceLocationPk"))==loc and str(record.get("sourceEvsePk"))==s["evse_pk"] and ident(record.get("appId"))==n["evse_normalized"]:app=True
            if filename.endswith("powerdot_evse_technical_inventory.json") and ident(record.get("evseId"))==n["evse_normalized"] and number(record.get("powerKw"))==n["kw"] and n["plug"] in {plug(v) for v in record.get("plugs",[])}:pd=True
            records_found.append(dict(file=filename,path=path,matching_fields=sorted(k for k,v in ids.items() if n["evse_normalized"] in v),source_ref_fields=refkeys))
        diag=["INDEPENDENT_CPO_AND_EVSE_PROOF_REVIEW_REQUIRED","TARIFF_SCOPE_NOT_VALIDATED"]
        if not force:diag.append("FULL_SITE_GROUP_PAIR_NOT_FORCED")
        if conflicts:diag.append("EXISTING_EXACT_ANCHOR_CONFLICT")
        if missing:diag.append("MISSING_SOURCE_GROUP_ID")
        if raw_state!="VERIFIED":diag.append("RAW_CONNECTOR_UNVERIFIED")
        if not s["reference_normalized"]:diag.append("SOURCE_REFERENCE_MISSING")
        elif len(refowners[s["reference_normalized"]])!=1:diag.append("SOURCE_REFERENCE_OWNER_NOT_UNIQUE")
        if s["recent_fault"]:diag.append("RECENT_HISTORICAL_FAULT_REVIEW")
        for k,v in {"forced_group":force,"raw_verified":raw_state=="VERIFIED","archive_target_id_hit":bool(records_found),"archive_same_record_ref_hit_review_only":bridge,"app_identity_record_hit_review_only":app,"powerdot_technical_corroboration":pd,"site_anchor_conflict":bool(conflicts)}.items():
            if v:counts[k]+=1
        counts["schema:"+schema]+=1;byop[(sites[sid]["operator"],status)]+=1
        output.append(dict(national_id=n["id"],source_id=s["id"],station_id=sid,location_pk=loc,evse_id=n["evse_id"],source_evse_pk=s["evse_pk"],source_connector_pk=s["connector_pk"],source_reference=s["physical_reference"],source_reference_owners=len(refowners[s["reference_normalized"]]),operator=sites[sid]["operator"],supplier_operator_id=locs[loc]["operator_id"],distance_m=x["distance_m"],national_plug=n["plug"],source_plug=s["plug"],national_kw=n["kw"],source_kw=s["kw"],site_status=status,group_pair_forced=force,anchor_conflicts=conflicts,raw_state=raw_state,tariff_schema=schema,schema_issues=j(issues),archive_records=j(records_found),archive_ref_hit=bridge,app_record_hit=app,powerdot_technical_corroboration=pd,original_blockers=x["original_blockers"],diagnostics=j(diag)))
    out=root/"results";out.mkdir()
    write_csv(out/"priority-pairs.csv.gz",output,list(output[0]))
    write_csv(out/"priority-sites.csv.gz",site_rows,list(site_rows[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,referenceValidated=14968,shortlist=short,evseUnique=unique,priorityPairs=len(output),prioritySites=len(site_rows),distanceLe5=sum(float(x["distance_m"])<=5 for x in selected),siteDiagnostics=dict(C.Counter(x["status"] for x in site_rows)),pairDiagnostics=dict(counts),byOperator=table(byop,["operator","site_status"]),archiveEvidence=archive_info,approvedOperatorPairs=len(approved),newMatches=0,pricesPromoted=0,supplierCalls=0,matchingRulesChanged=False,automaticPublication=False,limitations=["Complete technical bijection is not physical identity","Archive ID and same-record reference hits are review leads only, not automatic CPO or EVSE proof","Current tariff schema classification is not G6 calculability","No new supplier data acquired"])
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"priority-report.json").write_text(j(report))
    print("G5_GPS_PRIORITY "+j(report))
if __name__=="__main__":main()
