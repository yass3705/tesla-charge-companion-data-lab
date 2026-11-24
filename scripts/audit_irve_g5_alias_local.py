#!/usr/bin/env python3
"""Read-only G5 alias evidence audit. No new matching or price allocation."""
import collections as C
import json
import os
import pathlib
import re
import sqlite3
import sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import cached_connectors,signature,rows,table
from scripts.audit_irve_g5_nonexact_inventory import RULE,VALID,alias_scope,sk,j
from scripts.audit_electroverse_g5_real_matching import ident,norm,plug,mode,number,state,distance

def numeric(v):
    v=str(v or "").strip()
    return int(v) if re.fullmatch(r"[0-9]{1,3}",v) else None

def suffix_matches(target, ref, evidence):
    w=evidence.get("width")
    return (evidence.get("mode")=="strict_post_overlay_numeric_suffix_bijection"
        and type(w) is int and 1<=w<=3 and numeric(ref) is not None
        and len(target)>w and target[:-w]==evidence.get("prefix")
        and target[-w:].isdigit() and int(target[-w:])==numeric(ref))

def possible_bijections(ordinals, targets, owners):
    """Reproduce historical suffix search on an explicitly supplied universe."""
    if not ordinals or None in ordinals or len(set(ordinals))!=len(ordinals):return []
    result=set()
    for w in (1,2,3):
        groups=C.defaultdict(list)
        for t in set(targets):
            if len(t)>w and t[-w:].isdigit() and int(t[-w:]) in ordinals:
                groups[t[:-w]].append((int(t[-w:]),t))
        for g in groups.values():
            if len(g)==len(ordinals) and {a for a,b in g}==set(ordinals) and all(len(owners[b])==1 for a,b in g):
                result.add(tuple(sorted(g)))
    return sorted(result)

def row_status(nall, active, source, same_ref, observed, exact, evidence):
    if observed:return "OBSERVED_NONEXACT"
    if exact:return "EXACT_ALREADY_VALIDATED_PAIR"
    if not nall:return "TARGET_ABSENT_NATIONAL_STATIC"
    if not active:return "TARGET_OUTSIDE_ACTIVE_PROJECTION"
    if not source:return "SOURCE_LOCATION_EVSE_ABSENT"
    if not same_ref:return "SOURCE_REFERENCE_CHANGED_OR_MISSING"
    if not evidence:return "NO_EXPLICIT_EVIDENCE_FIELD"
    return "PRESENT_BUT_NOT_IN_NONEXACT_INVENTORY_REVIEW"

def addr_state(a,b):
    return state(norm(a),norm(b))

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_alias_local_evidence_review_only" or pin["ruleVersion"]!=RULE or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    base=download(root/"v5",pin["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    verify(base["db.sqlite"],pin["sqliteSha256"])
    rp=json.loads(base["report.json"].read_text())
    if rp["codeSha"]!=pin["ledger"]["codeSha"] or rp["ruleVersion"]!=RULE or rp["sourcePin"]["tariff"]!=pin["tariff"] or rp["newValidated"]!=14968:raise ValueError("Ledger provenance")
    prior=download(root/"inventory",pin["inventory"],{"registry.csv.gz":("alias-registry-inventory.csv.gz",),"pairs.csv.gz":("alias-candidates.csv.gz",),"report.json":("nonexact-report.json",)})
    for k,v in pin["inventoryExports"].items():verify(prior[k],v)
    ir=json.loads(prior["report.json"].read_text())
    if ir["codeSha"]!=pin["inventory"]["codeSha"] or ir["sourcePin"]["ledger"]!=pin["ledger"] or ir["aliasRegistryRows"]!=603 or ir["aliasPairs"]!=1918:raise ValueError("Inventory provenance")
    db=sqlite3.connect(base["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Integrity")
    meta={x["key"]:json.loads(x["value"]) for x in db.execute("SELECT * FROM metadata")}
    if meta["ruleVersion"]!=RULE or meta["codeSha"]!=rp["codeSha"]:raise ValueError("Metadata")
    ns={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_connector")}
    ss={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_connector")}
    sites={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_station")}
    locs={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_location")}
    nref=C.defaultdict(list);sref=C.defaultdict(set);sg=C.defaultdict(list);locgroups=C.defaultdict(set);owners=C.defaultdict(set);national_rows=C.defaultdict(list);sitepdcs=C.defaultdict(set)
    for n in ns.values():nref[n["evse_normalized"]].append(n)
    for n in db.execute("SELECT * FROM national_operational_scope"):
        k=ident(n["evse_id"]);owners[k].add((n["station_id"],n["evse_id"]));national_rows[k].append(dict(n));sitepdcs[n["station_id"]].add(k)
    for s in ss.values():
        g=(s["location_pk"],s["evse_pk"]);sg[g].append(s);locgroups[g[0]].add(g)
        if s["reference_normalized"]:sref[s["reference_normalized"]].add(g)
    valid={(x[0],x[1]) for x in db.execute("SELECT national_id,source_id FROM candidate WHERE decision=?",(VALID,))}
    vn={a for a,b in valid};vs={b for a,b in valid}
    if len(valid)!=14968 or len(vn)!=14968 or len(vs)!=14968:raise ValueError("Reference mismatch")
    anchors=C.defaultdict(set);reverse_anchors=C.defaultdict(set)
    for a,b in valid:
        loc=ss[b]["location_pk"];site=ns[a]["station_id"];anchors[loc].add(site);reverse_anchors[site].add(loc)
    reg=rows(prior["registry.csv.gz"]);pairs=rows(prior["pairs.csv.gz"])
    if len(reg)!=603 or len(pairs)!=1918:raise ValueError("Parent rows")
    review=pathlib.Path("data/platforms/electroverse/validated-mappings")
    archived={}
    for filename,sha in meta["aliasEvidenceSha256"].items():
        p=review/filename;verify(p,sha);archived[filename]=json.loads(p.read_text())["mappings"]
    opfile=review/"g5-operator-crosswalk-review.json";verify(opfile,meta["operatorRegistrySha256"])
    op=json.loads(opfile.read_text());approved={(str(x["supplierOperatorId"]),norm(x["nationalOperator"])) for x in op["approvedPairs"]}
    # Review the archived numeric proof report, not a newly reconstructed historical cache.
    histpath=pathlib.Path("reports/electroverse/numeric-residual-analysis.json")
    hist=json.loads(histpath.read_text()) if histpath.is_file() else {}
    histgroups=C.defaultdict(list)
    for group in hist.get("topSolvableGroups",[])+hist.get("ambiguousSamples",[]):histgroups[str(group["electroverseLocationPk"])].append(group)
    # Previously reviewed CPO sources are kept as separate documents, not new approvals.
    evidencepath=pathlib.Path("docs/v9-rebuild/evidence/electroverse-g5-operator-gps-20261123.md")
    cpo_sources={str(p):digest(p) for p in [opfile,evidencepath] if p.is_file()}
    seen=set();registry=[];regcounts=C.Counter();by_key=C.defaultdict(list);numeric_locs=set()
    for row in reg:
        f=row["file"];i=int(row["row_index"]);r=archived[f][i]
        if r!=json.loads(row["raw_mapping"]):raise ValueError("Historical mapping mismatch")
        if (f,i) in seen:raise ValueError("Duplicate registry row")
        seen.add((f,i))
        loc,epk=str(r.get("electroverseLocationPk") or ""),str(r.get("electroverseEvsePk") or "")
        ref=ident(r.get("physicalReference"));t=ident(r.get("targetPdc"));g=(loc,epk)
        ss0=sg[g];same=[s for s in ss0 if s["reference_normalized"]==ref]
        nn=nref[t];obs=row["observed_nonexact_candidate"].lower()=="true"
        ev=r.get("evidence");e=ev if isinstance(ev,dict) else {}
        exact=any((n["id"],s["id"]) in valid for n in nn for s in same)
        status=row_status(national_rows[t],nn,ss0,same,obs,exact,bool(ev))
        flags={"target_static":bool(national_rows[t]),"target_active":bool(nn),"source_evse_present":bool(ss0),"source_ref_present":bool(same),"evidence_field_present":bool(ev),"exact_pair_validated":exact,"target_any_validated":any(n["id"] in vn for n in nn),"source_any_validated":any(s["id"] in vs for s in ss0),"donor_fields":[k for k in r if "donor" in k.lower()]}
        entry={**row,"classification":status,"flags":j(flags),"national_scope":j(national_rows[t]),"current_source_ids":j([s["id"] for s in ss0]),"current_target_ids":j([n["id"] for n in nn]),"archived_evidence_mode":e.get("mode",ev if isinstance(ev,str) else ""),"archived_suffix_consistent":suffix_matches(t,r.get("physicalReference"),e)}
        registry.append(entry);regcounts[(f,status)]+=1
        by_key[(loc,epk,ref,t)].append((r,entry))
        if obs and f=="numeric-residual.json":numeric_locs.add(loc)
    if len(seen)!=sum(map(len,archived.values())) or sum(x["classification"]=="OBSERVED_NONEXACT" for x in registry)!=131:raise ValueError("Registry reconciliation")
    # Current residuals and all-location competitors are distinct from historical residual universe.
    locreview={};location_rows=[]
    for loc in sorted(numeric_locs):
        allgroups=locgroups[loc]
        grouprefs={g:{s["physical_reference"] for s in sg[g]} for g in allgroups}
        numericgroups={g: numeric(next(iter(v))) for g,v in grouprefs.items() if len(v)==1 and numeric(next(iter(v))) is not None}
        freegroups={g:v for g,v in numericgroups.items() if not any(s["id"] in vs for s in sg[g])}
        missinggroups=[g for g,v in grouprefs.items() if not any(v)]
        mapped=locs[loc]["mapped_station"]; anchor=sorted(anchors[loc])
        candidate_sites=set(anchor)|{n["station_id"] for (l,epk,ref,t),entries in by_key.items() if l==loc for n in nref[t]}
        if mapped in sites:candidate_sites.add(mapped)
        for sid in sorted(candidate_sites):
            all_targets=sitepdcs[sid];active_targets={t for t in all_targets if nref[t]}
            free_targets={t for t in active_targets if not any(n["id"] in vn for n in nref[t])}
            full=possible_bijections(list(numericgroups.values()),active_targets,owners)
            residual=possible_bijections(list(freegroups.values()),free_targets,owners)
            historical=histgroups[loc]
            o={"location_pk":loc,"station_id":sid,"mapped_station":mapped,"v5_anchor_stations":j(anchor),"v5_reverse_locations":j(sorted(reverse_anchors[sid])),"all_source_evse_count":len(allgroups),"numeric_source_evse_count":len(numericgroups),"free_numeric_source_evse_count":len(freegroups),"missing_reference_groups":j(sorted(missinggroups)),"all_source_groups":j([{"group":g,"refs":sorted(v)} for g,v in sorted(grouprefs.items())]),"numeric_ordinals":j(sorted(numericgroups.values())),"free_ordinals":j(sorted(freegroups.values())),"all_national_targets":j(sorted(all_targets)),"active_national_targets":j(sorted(active_targets)),"free_active_national_targets":j(sorted(free_targets)),"full_numeric_bijections":j(full),"v5_residual_bijections":j(residual),"historical_group_count":len(historical),"historical_groups":j(historical),"distance_m":distance((locs[loc]["lat"],locs[loc]["lon"]),(sites[sid]["lat"],sites[sid]["lon"])),"address_observation":addr_state(locs[loc]["address"],sites[sid]["address"])}
            locreview[(loc,sid)]=(o,full,residual,numericgroups,freegroups);location_rows.append(o)
    wanted={sk(s) for loc in numeric_locs for g in locgroups[loc] for s in sg[g] if s["connector_pk"]}
    raw=cached_connectors(root/"tariff",pin["tariff"],meta["tariffManifestSha256"],wanted)
    reviewed=[];blockers=C.Counter();classes=C.Counter()
    for row in pairs:
        n=ns[int(row["national_id"])];s=ss[int(row["source_id"])];loc=s["location_pk"];sid=n["station_id"];g=(loc,s["evse_pk"]);t=n["evse_normalized"]
        if n["id"] in vn or s["id"] in vs:raise ValueError("Unexpected occupied alias")
        matches=by_key[(loc,s["evse_pk"],s["reference_normalized"],t)]
        if not matches:raise ValueError("No archived alias")
        o,full,residual,numgroups,freegroups=locreview[(loc,sid)]
        evs=[r["evidence"] for r,_ in matches if isinstance(r.get("evidence"),dict)]
        suffix=any(suffix_matches(t,s["physical_reference"],e) for e in evs)
        ordinal=numeric(s["physical_reference"])
        local_owners={key for key,v in numgroups.items() if v==ordinal}
        global_count=len(sref[s["reference_normalized"]])
        pair_=(ordinal,t);full_unique=len(full)==1 and pair_ in full[0];residual_unique=len(residual)==1 and pair_ in residual[0]
        old_group_support=[]
        for h in histgroups[loc]:
            if str(h.get("irveStationId"))!=sid:continue
            if h.get("exactCandidateCount")!=1 or h.get("duplicateSourceOrdinals"):continue
            if not any(str(x.get("evsePk"))==g[1] and numeric(x.get("physicalReference"))==ordinal for x in h.get("ordinals",[])):continue
            if any(any(x.get("n")==ordinal and x.get("p")==t for x in c.get("targets",[])) for c in h.get("exactCandidates",[])):old_group_support.append(h)
        lhs,rhs=alias_scope(s,n,nref[t],sg[g])
        scope=lhs==[n["id"]] and rhs==[s["id"]]
        c=json.loads(row["criteria"]);reason=[]
        if not suffix:reason.append("HISTORICAL_SUFFIX_NOT_REPRODUCED")
        if not old_group_support:reason.append("HISTORICAL_RESIDUAL_UNIVERSE_NOT_REPRODUCED_FROM_SAVED_REPORT")
        if len(local_owners)!=1:reason.append("LOCAL_NUMERIC_REFERENCE_NOT_UNIQUE")
        if not full_unique:reason.append("FULL_CURRENT_NUMERIC_BIJECTION_NOT_UNIQUE")
        if not residual_unique:reason.append("V5_RESIDUAL_BIJECTION_NOT_UNIQUE")
        if len(owners[t])!=1:reason.append("NATIONAL_OWNER_NOT_UNIQUE")
        if not (anchors[loc]=={sid} and reverse_anchors[sid]=={loc}):reason.append("EXACT_V5_SITE_ANCHOR_NOT_UNIQUE")
        if o["missing_reference_groups"]!="[]":reason.append("MISSING_REFERENCE_COMPETITORS_PRESENT")
        if any(c.get(k)=="FAIL" for k in ("country","operator","plug","current","power")):reason.append("ORIGINAL_TECHNICAL_OR_OPERATOR_CONTRADICTION")
        if any(c.get(k)!="PASS" for k in ("plug","current","power")):reason.append("POSITIVE_TECHNICAL_PROOF_INCOMPLETE")
        if not scope:reason.append("BIDIRECTIONAL_CONNECTOR_SCOPE_UNPROVEN")
        if not s["has_price"]:reason.append("NO_PRICE_PAYLOAD")
        if s["recent_fault"]:reason.append("RECENT_HISTORICAL_FAULT")
        independent=(locs[loc]["operator_id"],norm(sites[sid]["operator"])) in approved
        if not independent:reason.append("INDEPENDENT_CPO_PROOF_NOT_ESTABLISHED")
        obs=raw.get(sk(s));raw_ok=False
        if obs:
            ref,conn=obs
            raw_ok=ident(ref)==s["reference_normalized"] and plug(conn.get("standard"))==s["plug"] and mode(plug(conn.get("standard")))==s["mode"] and number(conn.get("kilowatts"))==s["kw"] and signature(conn)==s["tariff_signature"]
        if not raw_ok:reason.append("RAW_CONNECTOR_NOT_VERIFIED")
        # Positive station anchor is not independent operator proof; no acceptance decision.
        label="LOCAL_IDENTITY_DIAGNOSTIC_ONLY" if suffix and len(local_owners)==1 and full_unique and len(owners[t])==1 else "LOCAL_IDENTITY_NOT_ESTABLISHED"
        classes[label]+=1
        for z in reason:blockers[z]+=1
        reviewed.append({**row,"historical_suffix_consistent":suffix,"historic_report_support":bool(old_group_support),"local_reference_owners":len(local_owners),"global_reference_owners":global_count,"full_current_bijection_unique":full_unique,"v5_residual_bijection_unique":residual_unique,"national_owner_count":len(owners[t]),"v5_site_anchor_unique":anchors[loc]=={sid} and reverse_anchors[sid]=={loc},"missing_reference_competitors":o["missing_reference_groups"],"independent_cpo_registry_pass":independent,"raw_connector_verified":raw_ok,"local_scope_national":j(lhs),"local_scope_source":j(rhs),"local_connector_scope_unique":scope,"diagnostic_class":label,"diagnostic_blockers":j(reason)})
    # Address availability versus literal equality. Count source sites, not candidate pairs.
    address_index=C.defaultdict(set)
    for sid,n in sites.items():
        if norm(n["address"]):address_index[norm(n["address"])].add(sid)
    addr=[];ac=C.Counter()
    for loc,s in locs.items():
        a=norm(s["address"]);mapped=sites.get(s["mapped_station"]);hits=address_index.get(a,set()) if a else set()
        status="SOURCE_ADDRESS_MISSING" if not a else "NO_EXACT_NORMALIZED_ADDRESS" if not hits else "UNIQUE_ADDRESS_CANDIDATE" if len(hits)==1 else "MULTIPLE_ADDRESS_CANDIDATES"
        ac[status]+=1
        addr.append({"location_pk":loc,"source_address":s["address"],"mapped_station":s["mapped_station"],"mapped_national_address":mapped["address"] if mapped else None,"mapped_address_observation":addr_state(s["address"],mapped["address"] if mapped else None),"exact_address_station_ids":j(sorted(hits)),"status":status})
    out=root/"results";out.mkdir()
    for name,data in [("alias-registry-reconciliation",registry),("numeric-local-pairs",reviewed),("numeric-site-universe",location_rows),("address-diagnostics",addr)]:
        write_csv(out/(name+".csv.gz"),data,list(data[0]))
    report={"codeSha":os.environ.get("GITHUB_SHA"),"sourcePin":pin,"referenceValidated":14968,"registryRows":len(registry),"registryObserved":131,"registryNotObserved":472,"registryClassification":table(regcounts,["file","classification"]),"numericPairs":len(reviewed),"numericLocations":len(numeric_locs),"siteUniverses":len(location_rows),"localClasses":dict(classes),"diagnosticBlockers":dict(blockers),"positiveDiagnostics":{k:sum(bool(x[k]) for x in reviewed) for k in ("historical_suffix_consistent","historic_report_support","full_current_bijection_unique","v5_residual_bijection_unique","v5_site_anchor_unique","independent_cpo_registry_pass","raw_connector_verified","local_connector_scope_unique")},"localReferenceUnique":sum(x["local_reference_owners"]==1 for x in reviewed),"addressSourceLocations":len(addr),"addressDiagnostics":dict(ac),"nationalSitesWithAddress":sum(bool(norm(x["address"])) for x in sites.values()),"historicReportSha256":digest(histpath) if histpath.is_file() else None,"cpoEvidenceSha256":cpo_sources,"approvedOperatorRegistryPairs":len(approved),"newMatches":0,"pricesPromoted":0,"supplierCalls":0,"matchingRulesChanged":False,"automaticPublication":False,"limitations":["Historical report only preserves sampled groups, not full historical universe; absence is not disproof.","Current full and v5-residual numeric universes are diagnostics, not original historical residual.","Exact v5 site anchors and provider label equality are not independent CPO proof.","No new alias, address or GPS candidate is promoted; no rule C extension or G6."]}
    report["exportSha256"]={p.name:digest(p) for p in out.glob("*.csv.gz")}
    (out/"alias-local-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("G5_ALIAS_LOCAL_REVIEW "+j({k:v for k,v in report.items() if k!="sourcePin"}))
    db.close()
if __name__=="__main__":main()
