#!/usr/bin/env python3
"""Read-only national reference reconstruction inventory. No matching rules or prices changed."""
import collections as C
import csv,gzip,hashlib,json,os,pathlib,re,sqlite3,sys,zipfile
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import rows,signature
from scripts.audit_irve_g5_nonexact_inventory import RULE,VALID,j,sk
from scripts.audit_irve_g5_gps_priority import records,gitblob
from scripts.audit_irve_g5_address_gps import compatible
from scripts.audit_electroverse_g5_real_matching import ident,plug,mode,number,distance,power_check,state
from scripts.france.build_france_irve_static_v9 import key,get

def split_id(value):
    # Structural hypothesis only: country (2), party (3), E, entire nonempty local ID.
    # No arbitrary suffix, digit padding, case beyond existing ident(), or dropping other chars.
    v=ident(value)
    m=re.fullmatch(r"([A-Z]{2}[A-Z0-9]{3}E)([A-Z0-9]+)",v)
    return m.groups() if m else (None,None)

def strict_reference(value):
    v=ident(value)
    return v if re.fullmatch(r"[A-Z0-9]+",v) else ""

def loose_suffix(a,b):
    # Reproduce earlier exploratory alphanumeric-only comparison, never for acceptance.
    a=re.sub("[^A-Z0-9]","",str(a or "").upper())
    b=re.sub("[^A-Z0-9]","",str(b or "").upper())
    return bool(b and a!=b and a.endswith(b))

def relation(target,source):
    p,tail=split_id(target)
    return "STRUCTURED_PREFIX_REMOVAL" if p and tail==strict_reference(source) and ident(target)!=ident(source) else "ARBITRARY_SUFFIX_ONLY" if loose_suffix(target,source) else "NO_SUFFIX"

def collision(national,source,exact):
    if not national:return "NO_STRUCTURED_TARGET"
    if len(national)!=1:return "NATIONAL_MULTIPLE_RAW_OWNERS"
    if len(source)!=1:return "SOURCE_MULTIPLE_EVSE_OWNERS"
    if exact:return "SOURCE_ALREADY_HAS_FULL_NATIONAL_ID"
    return "GLOBAL_STRUCTURAL_UNIQUENESS_ONLY"

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_g5_truncated_reference_global_audit_only" or pin["ruleVersion"]!=RULE or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    b=download(root/"v5",pin["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    verify(b["db.sqlite"],pin["sqliteSha256"]);rp=json.loads(b["report.json"].read_text())
    if rp["codeSha"]!=pin["ledger"]["codeSha"] or rp["ruleVersion"]!=RULE or rp["sourcePin"]["tariff"]!=pin["tariff"] or rp["newValidated"]!=14968:raise ValueError("Ledger lineage")
    prior=download(root/"priority",pin["priority"],{"pairs.csv.gz":("priority-pairs.csv.gz",),"report.json":("priority-report.json",)})
    verify(prior["pairs.csv.gz"],pin["priorityPairsSha256"]);pr=json.loads(prior["report.json"].read_text())
    if pr["codeSha"]!=pin["priority"]["codeSha"] or pr["sourcePin"]["ledger"]!=pin["ledger"] or pr["sourcePin"]["tariff"]!=pin["tariff"] or pr["priorityPairs"]!=987:raise ValueError("Priority lineage")
    pp=rows(prior["pairs.csv.gz"]);forced=[x for x in pp if x["group_pair_forced"].lower()=="true"]
    old=[x for x in forced if loose_suffix(x["evse_id"],x["source_reference"])]
    if len(forced)!=659 or len(old)!=392:raise ValueError("Priority cohort")
    national=download(root/"national",pin["national"],{"static.csv":("raw","france-irve","static.csv"),"all.json.gz":("data","national","france-irve-static-v9","all.json.gz"),"dynamic.json.gz":("data","national","france-irve-dynamic-status-v9.json.gz")})
    for f,k in [("static.csv","rawSha256"),("all.json.gz","allSha256"),("dynamic.json.gz","dynamicSha256")]:verify(national[f],pin[k])
    db=sqlite3.connect(b["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Integrity")
    meta={x["key"]:json.loads(x["value"]) for x in db.execute("SELECT * FROM metadata")}
    if meta["ruleVersion"]!=RULE or meta["codeSha"]!=rp["codeSha"]:raise ValueError("Metadata")
    valid={(x[0],x[1]) for x in db.execute("SELECT national_id,source_id FROM candidate WHERE decision=?",(VALID,))}
    vn={a for a,b in valid};vs={b for a,b in valid}
    if len(valid)!=14968 or len(vn)!=14968 or len(vs)!=14968:raise ValueError("Reference")
    ns={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_connector")}
    ss={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_connector")}
    locs={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_location")}
    sites={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_station")}
    # Entire raw national file, including rows excluded from static projection, foreign IDs,
    # unsupported plugs, inactive IDs and owners with missing station identity.
    allowners=C.defaultdict(set);tails=C.defaultdict(set);rawrows=0;missing=0;prefixes=C.Counter()
    with national["static.csv"].open(encoding="utf-8-sig",errors="replace",newline="") as f:
        sample=f.read(65536);f.seek(0)
        try:dialect=csv.Sniffer().sniff(sample,delimiters=",;\t|")
        except csv.Error:dialect=csv.excel
        for rr in csv.DictReader(f,dialect=dialect):
            rawrows+=1;row={key(k):v for k,v in rr.items() if k}
            ev=get(row,"id_pdc_itinerance");sid=get(row,"id_station_itinerance","id_station_local") or ev
            if not ev:missing+=1;continue
            owner=(sid,ev);allowners[ident(ev)].add(owner)
            p,t=split_id(ev)
            if p:tails[t].add(owner);prefixes[p]+=1
    # Check projection independently, do not silently miss a national PDC.
    with gzip.open(national["all.json.gz"],"rt",encoding="utf-8") as f:static=json.load(f)
    projected={(st[0],p) for st in static for g in st[8] for p in g[6]}
    if any((sid,ev) not in allowners.get(ident(ev),set()) for sid,ev in projected):raise ValueError("Static owner absent from raw national file")
    activeowners={(n["station_id"],n["evse_id"]) for n in ns.values()}
    if not activeowners<=projected:raise ValueError("Active projection")
    byn=C.defaultdict(list);bys=C.defaultdict(list);sourceowners=C.defaultdict(set);sourcegroups=C.defaultdict(list)
    for n in ns.values():byn[(n["station_id"],n["evse_id"])].append(n)
    for s in ss.values():
        group=(s["location_pk"],s["evse_pk"]);sourcegroups[group].append(s)
        ref=strict_reference(s["physical_reference"])
        if ref:sourceowners[ref].add(group);bys[ref].append(s)
    # Reconcile the full cache, not only the GPS cohort, including EVSEs without connectors.
    src=download(root/"tariff",pin["tariff"],{"manifest.json":("data","electroverse","tariff_cache","manifest.json")})
    verify(src["manifest.json"],meta["tariffManifestSha256"]);manifest=json.loads(src["manifest.json"].read_text())
    rawgroups=C.defaultdict(list);rawcon={};seen=set()
    with zipfile.ZipFile(root/"tariff"/"input.zip") as z:
        names=z.namelist()
        for sh in manifest["shards"]:
            path=pathlib.PurePosixPath(sh["file"])
            if path.is_absolute() or ".." in path.parts:raise ValueError("Unsafe shard")
            hits=[p for p in names if ("/"+p).endswith("/data/electroverse/tariff_cache/"+str(path))]
            if len(hits)!=1:raise ValueError("Shard")
            d=json.loads(z.read(hits[0]))
            if len(d["stations"])!=sh["count"]:raise ValueError("Shard count")
            for loc,row in d["stations"].items():
                if loc in seen or str(row.get("electroverseLocationPk"))!=loc:raise ValueError("Location identity")
                seen.add(loc)
                for e in (row.get("tariff") or {}).get("evses") or []:
                    pk=str(e.get("pk") or "");ref=ident(e.get("physicalReference"));rawgroups[(loc,pk)].append(ref)
                    for c in e.get("connectors") or []:
                        k=(loc,pk,str(c.get("pk") or ""))
                        rawcon[k]=None if k in rawcon else (ref,plug(c.get("standard")),number(c.get("kilowatts")),signature(c))
    if seen!=set(locs) or set(rawgroups)!=set(sourcegroups):raise ValueError("Full source coverage")
    for s in ss.values():
        if s["reference_normalized"] not in rawgroups[(s["location_pk"],s["evse_pk"])]:raise ValueError("Raw reference mismatch")
    # Index independent archived records with explicit identifier fields; hits are not proof of crosswalk.
    targets={ident(ev) for ref in sourceowners for _,ev in tails.get(ref,())}
    evidence=C.defaultdict(list);archives={}
    for f,expected in pin["evidenceBlobs"].items():
        data=pathlib.Path(f).read_bytes()
        if gitblob(data)!=expected:raise ValueError("Evidence blob")
        archives[f]=hashlib.sha256(data).hexdigest()
        for path,ids,rec in records(json.loads(data)):
            union=set().union(*ids.values())
            for t in union&targets:evidence[t].append((f,path,union))
    opfile=pathlib.Path("data/platforms/electroverse/validated-mappings/g5-operator-crosswalk-review.json")
    verify(opfile,meta["operatorRegistrySha256"]);approved=json.loads(opfile.read_text())["approvedPairs"]
    if approved:raise ValueError("Re-review operator registry before applying diagnostic")
    out=root/"results";out.mkdir()
    refrows=[];pairrows=[];stat=C.Counter();priorrows=[];group_stats=C.Counter();operator_prefix=C.Counter()
    # Export all source references including no-hit and collisions; national owner list includes inactive.
    # No expansion of ambiguous cross-products; all owners explicitly retained in the reference export.
    def disposition(ref):
        return collision(tails.get(ref,set()),sourceowners.get(ref,set()),allowners.get(ref,set()))
    for ref,groups in sorted(sourceowners.items()):
        owners=tails.get(ref,set());status=disposition(ref);stat[status]+=1
        ac=owners&activeowners
        refrows.append(dict(reference=ref,source_owners=j(sorted(groups)),national_raw_owners=j(sorted(owners)),national_active_owners=j(sorted(ac)),full_id_owners=j(sorted(allowners.get(ref,set()))),status=status))
        for loc,pk in groups:
            group_stats[status]+=1
        if status!="GLOBAL_STRUCTURAL_UNIQUENESS_ONLY" or len(ac)!=1:continue
        sid,ev=next(iter(ac));loc,pk=next(iter(groups));nlist=byn[(sid,ev)];slist=sourcegroups[(loc,pk)]
        p,_=split_id(ev)
        operator_prefix[(locs[loc]["operator_id"],p,sites[sid]["operator"])]+=1
        for s in slist:
            for n in nlist:
                d=distance((locs[loc]["lat"],locs[loc]["lon"]),(sites[sid]["lat"],sites[sid]["lon"]))
                tech=[state(n["plug"],s["plug"]),state(n["mode"],s["mode"]),power_check(n["kw"],s["kw"],n["mode"])[0]]
                scope_n=sum(compatible(x,s) for x in nlist);scope_s=sum(compatible(n,x) for x in slist)
                raw=rawcon.get(sk(s));rawok=raw==(s["reference_normalized"],s["plug"],s["kw"],s["tariff_signature"])
                alloc="BOTH_UNMATCHED" if n["id"] not in vn and s["id"] not in vs else "OCCUPIED"
                ctry=locs[loc]["country"];diag=["PREFIX_RULE_NOT_INDEPENDENTLY_DOCUMENTED","CPO_PROOF_NOT_ESTABLISHED","TARIFF_SCOPE_NOT_VALIDATED"]
                if alloc!="BOTH_UNMATCHED":diag.append("NO_REASSIGNMENT")
                if d is None or d>10:diag.append("GPS_NOT_CONFIRMED_WITHIN_10M")
                if tech!=["PASS"]*3:diag.append("TECHNICAL_PROOF_INCOMPLETE_OR_CONTRADICTORY")
                if scope_n!=1 or scope_s!=1:diag.append("CONNECTOR_SCOPE_NOT_UNIQUE")
                if ctry and ctry!="FR":diag.append("COUNTRY_CONTRADICTION")
                if not rawok:diag.append("RAW_CONNECTOR_UNVERIFIED")
                if not s["has_price"]:diag.append("NO_PRICE")
                if s["recent_fault"]:diag.append("RECENT_FAULT_REVIEW")
                if len(rawgroups[(loc,pk)])!=1 or not pk:diag.append("SOURCE_GROUP_ID_NOT_UNIQUE")
                evd=evidence[ident(ev)];bridge=[(f,path) for f,path,ids in evd if ref in ids and ref!=ident(ev)]
                pairrows.append(dict(national_id=n["id"],source_id=s["id"],station_id=sid,location_pk=loc,evse_id=ev,reference=ref,prefix=p,operator=sites[sid]["operator"],supplier_operator_id=locs[loc]["operator_id"],distance_m=d,allocation=alloc,plug_state=tech[0],current_state=tech[1],power_state=tech[2],scope_n=scope_n,scope_s=scope_s,raw_verified=rawok,archive_target_records=j([(f,path) for f,path,_ in evd]),archive_same_record_reference_hits=j(bridge),diagnostics=j(diag)))
    for x in old:
        ref=strict_reference(x["source_reference"]);rel=relation(x["evse_id"],x["source_reference"])
        priorrows.append(dict(national_id=x["national_id"],source_id=x["source_id"],evse_id=x["evse_id"],reference=x["source_reference"],operator=x["operator"],relation=rel,global_status=disposition(ref),raw_owner_count=len(tails.get(ref,set())),source_owner_count=len(sourceowners.get(ref,set())),prefix=split_id(x["evse_id"])[0],tariff_schema=x["tariff_schema"]))
    if not refrows or not pairrows:raise ValueError("Unexpected empty diagnostic universe")
    write_csv(out/"global-references.csv.gz",refrows,list(refrows[0]))
    write_csv(out/"global-unique-pairs.csv.gz",pairrows,list(pairrows[0]))
    write_csv(out/"prior-392.csv.gz",priorrows,list(priorrows[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,referenceValidated=14968,rawNationalRows=rawrows,rawMissingPdc=missing,rawNationalNormalizedIds=len(allowners),rawNationalOwners=sum(map(len,allowners.values())),staticOwners=len(projected),activeOwners=len(activeowners),nationalStructuredTails=len(tails),sourceLocations=len(seen),sourceGroups=len(rawgroups),sourceConnectorRows=len(ss),sourceDistinctReferences=len(sourceowners),sourceMissingOrNonAlphanumericGroups=sum(not any(strict_reference(x["physical_reference"]) for x in g) for g in sourcegroups.values()),referenceStatus=dict(stat),sourceGroupStatus=dict(group_stats),prior392Relation=dict(C.Counter(x["relation"] for x in priorrows)),prior392GlobalStatus=dict(C.Counter(x["global_status"] for x in priorrows)),prior392Cross=dict(C.Counter(x["relation"]+"|"+x["global_status"] for x in priorrows)),globalUniqueActivePairs=len(pairrows),globalPairDiagnostics=dict(C.Counter(d for x in pairrows for d in json.loads(x["diagnostics"]))),globalFreePairs=sum(x["allocation"]=="BOTH_UNMATCHED" for x in pairrows),globalArchiveBridgeHits=sum(x["archive_same_record_reference_hits"]!="[]" for x in pairrows),globalByPrefix=dict(C.Counter(x["prefix"] for x in pairrows)),archiveSha256=archives,approvedOperatorPairs=0,newMatches=0,pricesPromoted=0,supplierCalls=0,matchingRulesChanged=False,automaticPublication=False,limitations=["Structural prefix parsing is a hypothesis, not documented provider semantics","Collisions include all raw national owners, including inactive; ambiguous references are exported with all owners, not expanded into Cartesian pairs","Archived same-record hits are leads, not proof of operator or identity","No new supplier data"])
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"truncated-report.json").write_text(j(report))
    print("G5_TRUNCATED "+j(report))
if __name__=="__main__":main()
