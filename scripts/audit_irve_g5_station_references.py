#!/usr/bin/env python3
"""Compare entire station reference multisets; never assign matches or prices."""
import collections as C
import csv,gzip,json,os,pathlib,sqlite3,sys,zipfile
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import rows
from scripts.audit_irve_g5_nonexact_inventory import RULE,VALID,j
from scripts.audit_irve_g5_truncated import split_id,strict_reference
from scripts.audit_electroverse_g5_real_matching import ident
from scripts.france.build_france_irve_static_v9 import key,get

BLOCKERS={"PREFIX_RULE_NOT_INDEPENDENTLY_DOCUMENTED","CPO_PROOF_NOT_ESTABLISHED","TARIFF_SCOPE_NOT_VALIDATED"}
def cohort(x):
    return set(json.loads(x["diagnostics"]))==BLOCKERS
def fingerprint(refs):
    return tuple(sorted(refs))
def compare(national,source):
    # National raw owner IDs are deduplicated by exact raw string, not by suffix.
    # Missing and duplicate source groups cannot produce a positive result.
    n=C.Counter(split_id(x)[1] or "" for x in national)
    s=C.Counter(strict_reference(x) for x in source)
    missing=n.get("",0)+s.get("",0)
    dup=sum(v-1 for k,v in n.items() if k and v>1)+sum(v-1 for k,v in s.items() if k and v>1)
    a=n-s;b=s-n
    if not national or not source:status="EMPTY_SCOPE"
    elif missing:status="MISSING_OR_NONSTRUCTURED_REFERENCE"
    elif dup:status="DUPLICATE_REFERENCE_WITHIN_SITE"
    elif not a and not b:status="FULL_SHORT_REFERENCE_SET_EQUAL"
    else:status="REFERENCE_SET_DIFFERS"
    return status,dict(a),dict(b),missing,dup
def classify_mixed(national,source):
    # Distinct diagnostic, allowing exact full IDs alongside complete short IDs.
    # Never infer a prefix from site majority.
    if not national or len(national)!=len(source) or any(not strict_reference(x) for x in source):return False
    if len(set(map(strict_reference,source)))!=len(source):return False
    index=C.defaultdict(set)
    for ev in national:
        index[ident(ev)].add(ev)
        p,t=split_id(ev)
        if p:index[t].add(ev)
    hits=[index[strict_reference(s)] for s in source]
    return all(len(h)==1 for h in hits) and len(set(next(iter(h)) for h in hits))==len(national)
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g5_complete_station_reference_audit_only" or pin["ruleVersion"]!=RULE or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Scope")
    b=download(root/"v5",pin["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    verify(b["db.sqlite"],pin["sqliteSha256"]);rp=json.loads(b["report.json"].read_text())
    if rp["codeSha"]!=pin["ledger"]["codeSha"] or rp["ruleVersion"]!=RULE or rp["sourcePin"]["tariff"]!=pin["tariff"] or rp["newValidated"]!=14968:raise ValueError("Ledger lineage")
    old=download(root/"truncated",pin["truncated"],{"pairs.csv.gz":("global-unique-pairs.csv.gz",),"report.json":("truncated-report.json",)})
    verify(old["pairs.csv.gz"],pin["pairsSha256"]);tr=json.loads(old["report.json"].read_text())
    if tr["codeSha"]!=pin["truncated"]["codeSha"] or tr["sourcePin"]["ledger"]!=pin["ledger"] or tr["sourcePin"]["tariff"]!=pin["tariff"] or tr["sourcePin"]["national"]!=pin["national"]:raise ValueError("Truncated lineage")
    allpairs=rows(old["pairs.csv.gz"]);selected=[x for x in allpairs if cohort(x)]
    sites={(x["station_id"],x["location_pk"]) for x in selected}
    if len(allpairs)!=28432 or len(selected)!=9983 or len(sites)!=3439 or len({x[0] for x in sites})!=3439:raise ValueError("Cohort")
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
    raw=C.defaultdict(set);owners=C.defaultdict(set);full=C.defaultdict(set);rowcount=0
    with national["static.csv"].open(encoding="utf-8-sig",newline="") as f:
        sample=f.read(65536);f.seek(0)
        try:dialect=csv.Sniffer().sniff(sample,delimiters=",;\t|")
        except csv.Error:dialect=csv.excel
        for rr in csv.DictReader(f,dialect=dialect):
            rowcount+=1;row={key(k):v for k,v in rr.items() if k};ev=get(row,"id_pdc_itinerance");sid=get(row,"id_station_itinerance","id_station_local") or ev
            if not ev:raise ValueError("Unexpected missing PDC")
            raw[sid].add(ev);full[ident(ev)].add((sid,ev));p,t=split_id(ev)
            if p:owners[t].add((sid,ev))
    if rowcount!=181456 or sum(map(len,raw.values()))!=181412:raise ValueError("Raw scope")
    with gzip.open(national["all.json.gz"],"rt",encoding="utf-8") as f:static=json.load(f)
    projected=C.defaultdict(set);active=C.defaultdict(set)
    for st in static:
        for g in st[8]:projected[st[0]].update(g[6])
    for n in ns.values():active[n["station_id"]].add(n["evse_id"])
    if sum(map(len,projected.values()))!=174948 or sum(map(len,active.values()))!=101856:raise ValueError("National projection")
    if any(not v<=raw[k] for k,v in projected.items()) or any(not v<=projected[k] for k,v in active.items()):raise ValueError("National owner coverage")
    src=download(root/"tariff",pin["tariff"],{"manifest.json":("data","electroverse","tariff_cache","manifest.json")})
    verify(src["manifest.json"],meta["tariffManifestSha256"]);manifest=json.loads(src["manifest.json"].read_text())
    groups=C.defaultdict(list);sourceowners=C.defaultdict(set);seen=set();rawgroups=C.defaultdict(list)
    with zipfile.ZipFile(root/"tariff"/"input.zip") as z:
        names=z.namelist()
        for sh in manifest["shards"]:
            p=pathlib.PurePosixPath(sh["file"])
            if p.is_absolute() or ".." in p.parts:raise ValueError("Unsafe shard")
            hits=[n for n in names if ("/"+n).endswith("/data/electroverse/tariff_cache/"+str(p))]
            if len(hits)!=1:raise ValueError("Shard")
            d=json.loads(z.read(hits[0]))
            if len(d["stations"])!=sh["count"]:raise ValueError("Shard count")
            for loc,row in d["stations"].items():
                if loc in seen or str(row.get("electroverseLocationPk"))!=loc:raise ValueError("Location identity")
                seen.add(loc)
                for e in (row.get("tariff") or {}).get("evses") or []:
                    pk=str(e.get("pk") or "");ref=str(e.get("physicalReference") or "")
                    groups[loc].append((pk,ref));rawgroups[(loc,pk)].append(ident(ref))
                    if strict_reference(ref):sourceowners[strict_reference(ref)].add((loc,pk))
    if seen!=set(locs) or len(seen)!=22818 or len(rawgroups)!=93510:raise ValueError("Source coverage")
    if set(rawgroups)!={(s["location_pk"],s["evse_pk"]) for s in ss.values()}:raise ValueError("Source ledger groups")
    if any(s["reference_normalized"] not in rawgroups[(s["location_pk"],s["evse_pk"])] for s in ss.values()):raise ValueError("Source reference")
    # Global station fingerprints, including sites outside active projection.
    nf=C.defaultdict(set);sf=C.defaultdict(set)
    for sid,evs in raw.items():
        tails=[split_id(ev)[1] for ev in evs]
        if tails and all(tails) and len(set(tails))==len(tails):nf[fingerprint(tails)].add(sid)
    for loc,evs in groups.items():
        refs=[strict_reference(ref) for _,ref in evs]
        if refs and all(refs) and len(set(refs))==len(refs) and len({pk for pk,_ in evs})==len(evs) and all(pk for pk,_ in evs):sf[fingerprint(refs)].add(loc)
    anchorsN=C.defaultdict(set);anchorsS=C.defaultdict(set);anchors=C.defaultdict(list)
    for a,b in valid:
        n,s=ns[a],ss[b];sid,loc=n["station_id"],s["location_pk"]
        anchorsN[sid].add(loc);anchorsS[loc].add(sid);anchors[(sid,loc)].append((n["evse_id"],s["evse_pk"],s["physical_reference"]))
    pi=download(root/"pilot",pin["pilot"],{"identity-probe.json":("identity-probe.json",)})
    pilot=json.loads(pi["identity-probe.json"].read_text())
    if len(pilot["stations"])!=8 or len(pilot["requests"])!=10 or pilot["stopped"] is not None or any(x["status"]!=200 or x["errorCount"] for x in pilot["requests"]):raise ValueError("Pilot lineage")
    pilotrows=[];pilots={}
    for x in pilot["stations"]:
        t=x["target"];sid,loc=t["nationalStationId"],t["locationPk"]
        status,*_=compare(raw[sid],[e["physicalReference"] for e in x["evses"]])
        cache=fingerprint((pk,ident(ref)) for pk,ref in groups[loc])==fingerprint((str(e["pk"]),ident(e["physicalReference"])) for e in x["evses"])
        if x["hasNextPage"] is not False or x["status"]!="REFERENCE_OBSERVED":raise ValueError("Incomplete pilot")
        pilots[(sid,loc)]=x
        pilotrows.append(dict(station_id=sid,location_pk=loc,old_operator_id=t["expectedOperatorId"],observed_operator_pk=x["operator"]["pk"],observed_operator_name=x["operator"]["name"],reference_count=len(x["evses"]),raw_reference_status=status,cache_same_groups_and_references=cache))
    bysite=C.defaultdict(list)
    for x in selected:
        a,b=int(x["national_id"]),int(x["source_id"])
        if a in vn or b in vs or ns[a]["station_id"]!=x["station_id"] or ss[b]["location_pk"]!=x["location_pk"]:raise ValueError("Candidate identity")
        bysite[(x["station_id"],x["location_pk"])].append(x)
    site_rows=[];pair_rows=[];sc=C.Counter();pc=C.Counter();pref=C.Counter()
    for (sid,loc),xs in sorted(bysite.items()):
        evs=raw[sid];srcrows=groups[loc];refs=[r for _,r in srcrows]
        status,nonly,sonly,missing,dups=compare(evs,refs)
        static_status,*_=compare(projected[sid],refs);active_status,*_=compare(active[sid],refs)
        mixed=classify_mixed(evs,refs)
        fp=fingerprint(strict_reference(r) for r in refs)
        nsites=sorted(nf.get(fp,set()));ssites=sorted(sf.get(fp,set()))
        pks=[pk for pk,_ in srcrows];badpk=not all(pks) or len(set(pks))!=len(pks)
        sibling_collision=sum(len(owners.get(strict_reference(r),set()))!=1 or len(sourceowners.get(strict_reference(r),set()))!=1 or bool(full.get(strict_reference(r))) for r in refs)
        other_anchor=bool(anchorsN[sid]-{loc} or anchorsS[loc]-{sid})
        anchor_conflicts=sum(not (ident(ev)==ident(ref) or split_id(ev)[1]==strict_reference(ref)) for ev,pk,ref in anchors[(sid,loc)])
        diag=["PREFIX_RULE_NOT_INDEPENDENTLY_DOCUMENTED","CPO_PROOF_NOT_ESTABLISHED","TARIFF_SCOPE_NOT_VALIDATED"]
        if status!="FULL_SHORT_REFERENCE_SET_EQUAL":diag.append(status)
        if len(evs)<2:diag.append("SINGLE_EVSE_NO_ADDITIONAL_SET_EVIDENCE")
        if badpk:diag.append("SOURCE_GROUP_ID_MISSING_OR_DUPLICATE")
        if nsites!=[sid] or ssites!=[loc]:diag.append("STATION_FINGERPRINT_NOT_BIDIRECTIONALLY_UNIQUE")
        if sibling_collision:diag.append("SIBLING_REFERENCE_GLOBAL_COLLISION_OR_FULL_ID")
        if other_anchor or anchor_conflicts:diag.append("V5_STATION_OR_REFERENCE_ANCHOR_CONFLICT")
        high=set(diag)==BLOCKERS
        sc[status]+=1;pc[status]+=len(xs)
        if high:sc["STRICT_MULTI_EVSE_SITE_REVIEW"]+=1;pc["STRICT_MULTI_EVSE_SITE_REVIEW"]+=len(xs)
        if mixed:sc["MIXED_FULL_SHORT_EQUAL"]+=1;pc["MIXED_FULL_SHORT_EQUAL"]+=len(xs)
        if status=="FULL_SHORT_REFERENCE_SET_EQUAL" and len(evs)==1:sc["SINGLE_EVSE_EQUAL"]+=1;pc["SINGLE_EVSE_EQUAL"]+=len(xs)
        if high:
            for x in xs:pref[x["prefix"]]+=1
        site_rows.append(dict(station_id=sid,location_pk=loc,candidates=len(xs),raw_pdc_count=len(evs),static_pdc_count=len(projected[sid]),active_pdc_count=len(active[sid]),source_evse_count=len(refs),raw_status=status,static_status=static_status,active_status=active_status,mixed_full_short_equal=mixed,raw_ids=j(sorted(evs)),source_groups=j(sorted(srcrows)),national_only=j(nonly),source_only=j(sonly),missing=missing,duplicate_references=dups,global_national_sites=j(nsites),global_source_sites=j(ssites),sibling_collisions=sibling_collision,v5_anchor_count=len(anchors[(sid,loc)]),v5_other_station_anchor=other_anchor,v5_reference_conflicts=anchor_conflicts,pilot_observed=(sid,loc) in pilots,strict_multi_site_review=high,diagnostics=j(diag)))
        for x in xs:pair_rows.append(dict(**{k:x[k] for k in ("national_id","source_id","station_id","location_pk","evse_id","reference","prefix","operator","supplier_operator_id","distance_m")},raw_status=status,strict_multi_site_review=high,diagnostics=j(diag),original_diagnostics=x["diagnostics"]))
    if len(pair_rows)!=9983 or len(site_rows)!=3439:raise ValueError("Export coverage")
    out=root/"results";out.mkdir()
    for name,data in [("station-references.csv.gz",site_rows),("candidate-references.csv.gz",pair_rows),("pilot-reconciliation.csv.gz",pilotrows)]:write_csv(out/name,data,list(data[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,referenceValidated=14968,candidates=len(pair_rows),stations=len(site_rows),siteDiagnostics=dict(sc),pairDiagnostics=dict(pc),strictByPrefix=dict(pref),pilotStations=len(pilotrows),pilotReferences=sum(x["reference_count"] for x in pilotrows),pilotFullRawEqual=sum(x["raw_reference_status"]=="FULL_SHORT_REFERENCE_SET_EQUAL" for x in pilotrows),pilotCacheExact=sum(x["cache_same_groups_and_references"] for x in pilotrows),newMatches=0,pricesPromoted=0,supplierCalls=0,matchingRulesChanged=False,automaticPublication=False,limitations=["Cached EVSE sets are not current live availability","One-EVSE station adds no independent set evidence","Complete reference equality is corroboration, not proof of operator or tariff scope","Pilot observations limited to eight stations; no operator crosswalk extrapolation"])
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"station-reference-report.json").write_text(j(report));print("G5_STATION_REFERENCES "+j(report))
if __name__=="__main__":main()
