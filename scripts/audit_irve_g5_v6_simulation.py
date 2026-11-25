#!/usr/bin/env python3
"""V6 offline policy simulation. Immutable V5 ledger + explicit decisions, no serving."""
import collections as C
import json,math,os,pathlib,sqlite3,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import rows
from scripts.audit_irve_g5_nonexact_inventory import RULE,VALID,j,sk
from scripts.audit_irve_g5_station_references import compare
from scripts.audit_irve_g5_truncated import split_id,strict_reference
from scripts.audit_irve_g5_final_tariff import unique_scope
from scripts.audit_electroverse_g5_real_matching import ident,state,power_check,distance
VERSION="g5-fr-2026-11-25-v6-convergent-station-references"
BASE={"PREFIX_RULE_NOT_INDEPENDENTLY_DOCUMENTED","CPO_PROOF_NOT_ESTABLISHED","TARIFF_SCOPE_NOT_VALIDATED"}
def yes(v):return str(v).lower()=="true"
def keypair(r):return int(r["national_id"]),int(r["source_id"])
def hold_reasons(criteria):
    return ["V5_CONTRADICTION:"+k for k,v in sorted(criteria.items()) if v=="FAIL"]
def tariff_status(row):
    if not row or not yes(row["raw_verified"]) or row["scope"]!="DIRECT_CONNECTOR_EVIDENCE_ONLY":return "TARIFF_SCOPE_UNVERIFIED"
    if json.loads(row["additional_blockers"]) or not row["schema"].startswith("DIRECT_"):return "TARIFF_SCHEMA_REVIEW_G6"
    return "TARIFF_SCHEMA_RECOGNIZED_PENDING_G6"
def station_reasons(site,global_refs):
    out=[]
    if int(site["raw_pdc_count"])<2:out.append("SINGLE_EVSE_NO_ADDITIONAL_SET_EVIDENCE")
    ids=json.loads(site["raw_ids"]);groups=json.loads(site["source_groups"])
    if len(ids)!=int(site["raw_pdc_count"]) or len(groups)!=int(site["source_evse_count"]):out.append("STATION_SCOPE_COUNT_MISMATCH")
    status,*_=compare(ids,[ref for pk,ref in groups])
    if status!="FULL_SHORT_REFERENCE_SET_EQUAL":out.append(status)
    if not all(pk for pk,_ in groups) or len({pk for pk,_ in groups})!=len(groups):out.append("SOURCE_GROUP_ID_MISSING_OR_DUPLICATE")
    if json.loads(site["global_national_sites"])!=[site["station_id"]] or json.loads(site["global_source_sites"])!=[site["location_pk"]]:out.append("STATION_FINGERPRINT_NOT_BIDIRECTIONALLY_UNIQUE")
    n_by_tail=C.defaultdict(list)
    for ev in ids:n_by_tail[split_id(ev)[1]].append(ev)
    for pk,ref in groups:
        ref=strict_reference(ref);g=global_refs.get(ref)
        if not g or len(n_by_tail[ref])!=1 or g["status"]!="GLOBAL_STRUCTURAL_UNIQUENESS_ONLY" or json.loads(g["national_raw_owners"])!=[[site["station_id"],n_by_tail[ref][0]]] or json.loads(g["source_owners"])!=[[site["location_pk"],pk]] or json.loads(g["full_id_owners"]):
            out.append("SIBLING_REFERENCE_GLOBAL_COLLISION_OR_FULL_ID");break
    if yes(site["v5_other_station_anchor"]) or int(site["v5_reference_conflicts"]):out.append("V5_STATION_OR_REFERENCE_ANCHOR_CONFLICT")
    return sorted(set(out))
def main():
    p=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if p["purpose"]!="offline_g5_v6_simulation_only" or p["ruleVersion"]!=VERSION or p["parentRuleVersion"]!=RULE or p["simulationOnly"] is not True or p["supplierCalls"] is not False or p["automaticPublication"] is not False:raise ValueError("Scope")
    ledger_files=download(root/"v5",p["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    verify(ledger_files["db.sqlite"],p["sqliteSha256"]);rp=json.loads(ledger_files["report.json"].read_text())
    if rp["codeSha"]!=p["ledger"]["codeSha"] or rp["ruleVersion"]!=RULE or rp["sourcePin"]["tariff"]!=p["tariff"] or rp["newValidated"]!=14968:raise ValueError("Ledger lineage")
    a=download(root/"stations",p["stationAudit"],{"candidate-references.csv.gz":("candidate-references.csv.gz",),"station-references.csv.gz":("station-references.csv.gz",),"report.json":("station-reference-report.json",)})
    for f,h in p["stationExports"].items():verify(a[f],h)
    ar=json.loads(a["report.json"].read_text())
    if ar["codeSha"]!=p["stationAudit"]["codeSha"] or ar["sourcePin"]["ledger"]!=p["ledger"] or ar["sourcePin"]["tariff"]!=p["tariff"] or ar["sourcePin"]["truncated"]!=p["truncated"]:raise ValueError("Station lineage")
    g=download(root/"global",p["truncated"],{"refs.csv.gz":("global-references.csv.gz",),"report.json":("truncated-report.json",)})
    verify(g["refs.csv.gz"],p["globalReferencesSha256"]);gr=json.loads(g["report.json"].read_text())
    if gr["codeSha"]!=p["truncated"]["codeSha"] or gr["sourcePin"]["ledger"]!=p["ledger"] or gr["sourcePin"]["tariff"]!=p["tariff"]:raise ValueError("Global lineage")
    t=download(root/"tariff",p["finalTariff"],{"tariff-candidates.csv.gz":("tariff-candidates.csv.gz",),"tariff-stations.csv.gz":("tariff-stations.csv.gz",),"report.json":("tariff-evidence-report.json",)})
    for f,h in p["tariffExports"].items():verify(t[f],h)
    tr=json.loads(t["report.json"].read_text())
    if tr["codeSha"]!=p["finalTariff"]["codeSha"] or tr["sourcePin"]["stationAudit"]!=p["stationAudit"] or tr["sourcePin"]["ledger"]!=p["ledger"] or tr["sourcePin"]["tariff"]!=p["tariff"] or tr["referenceValidated"]!=14968:raise ValueError("Tariff lineage")
    e=download(root/"external",p["externalIdEvidence"],{"external-id-probe.json":("external-id-probe.json",)})
    er=json.loads(e["external-id-probe.json"].read_text())
    if er["scope"]!=tr["sourcePin"] or len(er["requests"])!=8 or len(er["stations"])!=8 or er["stopped"] is not None or any(r["status"]!=200 or r["errorCount"] for r in er["requests"]):raise ValueError("Pilot lineage")
    # The eight live observations do not constitute a general operator crosswalk.
    external={(x["target"]["nationalStationId"],x["target"]["locationPk"]):x for x in er["stations"]}
    cr=rows(a["candidate-references.csv.gz"]);sites={(x["station_id"],x["location_pk"]):x for x in rows(a["station-references.csv.gz"])}
    grr=rows(g["refs.csv.gz"]);refs={x["reference"]:x for x in grr}
    tar=rows(t["tariff-candidates.csv.gz"]);tm={keypair(x):x for x in tar}
    strict={keypair(x) for x in cr if yes(x["strict_multi_site_review"])}
    if len(cr)!=9983 or len({keypair(x) for x in cr})!=9983 or len(sites)!=3439 or len(grr)!=72269 or len(refs)!=72269 or len(tar)!=9147 or set(tm)!=strict or len(strict)!=9147:raise ValueError("Cohort")
    db=sqlite3.connect(ledger_files["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Integrity")
    meta={x["key"]:json.loads(x["value"]) for x in db.execute("SELECT * FROM metadata")}
    if meta["ruleVersion"]!=RULE or meta["codeSha"]!=rp["codeSha"]:raise ValueError("Metadata")
    ns={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_connector")}
    ss={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_connector")}
    nl={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_station")}
    sl={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_location")}
    op={x["evse_id"]:dict(x) for x in db.execute("SELECT * FROM national_operational_scope")}
    prior=[dict(x) for x in db.execute("SELECT c.*,p.criteria AS criterion_evidence FROM candidate c JOIN criterion_pattern p ON p.id=c.pattern_id WHERE c.decision=? ORDER BY c.national_id,c.source_id",(VALID,))]
    v5={keypair(x) for x in prior};vn={a for a,b in v5};vs={b for a,b in v5}
    if len(prior)!=14968 or len(v5)!=14968 or len(vn)!=14968 or len(vs)!=14968:raise ValueError("V5 uniqueness")
    ng=C.defaultdict(list);sg=C.defaultdict(list)
    for n in ns.values():ng[(n["station_id"],n["evse_id"])].append(n)
    for s in ss.values():sg[(s["location_pk"],s["evse_pk"])].append(s)
    st_reasons={k:station_reasons(site,refs) for k,site in sites.items()}
    out=[];added=set();stats=C.Counter();reasons=C.Counter();prefix=C.Counter()
    for x in cr:
        a,b=keypair(x);n,s=ns[a],ss[b];sid,loc=x["station_id"],x["location_pk"]
        if (n["station_id"],s["location_pk"],n["evse_id"])!=(sid,loc,x["evse_id"]) or strict_reference(s["physical_reference"])!=x["reference"]:raise ValueError("Candidate identity")
        prev=db.execute("SELECT c.decision,c.first_blocker,c.method,p.criteria FROM candidate c JOIN criterion_pattern p ON p.id=c.pattern_id WHERE national_id=? AND source_id=?",(a,b)).fetchone()
        criteria=json.loads(prev["criteria"])["criteria"] if prev else {}
        why=list(st_reasons[(sid,loc)])
        why+=hold_reasons(criteria)
        if not prev:why.append("PRIOR_LEDGER_PAIR_MISSING")
        if a in vn or b in vs:why.append("V5_ALLOCATION_OCCUPIED")
        pref,tail=split_id(n["evse_id"])
        if not pref or pref!=x["prefix"] or tail!=strict_reference(s["physical_reference"]) or ident(n["evse_id"])==ident(s["physical_reference"]):why.append("STRUCTURED_ID_NOT_PROVEN")
        g=refs.get(x["reference"])
        if not g or g["status"]!="GLOBAL_STRUCTURAL_UNIQUENESS_ONLY" or json.loads(g["national_raw_owners"])!=[[sid,n["evse_id"]]] or json.loads(g["source_owners"])!=[[loc,s["evse_pk"]]]:why.append("INDIVIDUAL_GLOBAL_UNIQUENESS_NOT_PROVEN")
        dist=distance((nl[sid]["lat"],nl[sid]["lon"]),(sl[loc]["lat"],sl[loc]["lon"]))
        if dist is None or not math.isfinite(dist) or dist>10:why.append("GPS_NOT_CONFIRMED_WITHIN_10M")
        if state(n["plug"],s["plug"])!="PASS":why.append("PLUG_NOT_PROVEN")
        if state(n["mode"],s["mode"])!="PASS":why.append("CURRENT_NOT_PROVEN")
        if power_check(n["kw"],s["kw"],n["mode"])[0]!="PASS":why.append("POWER_NOT_PROVEN")
        if not op.get(n["evse_id"],{}).get("eligible") or op[n["evse_id"]]["state"]!="en_service":why.append("NATIONAL_NOT_ACTIVE")
        if s["recent_fault"]:why.append("RECENT_FAULT_REVIEW")
        if sl[loc]["country"] and sl[loc]["country"]!="FR":why.append("COUNTRY_CONTRADICTION")
        siblings=sg[(loc,s["evse_pk"])]
        if not unique_scope(n,s,ng[(sid,n["evse_id"])],siblings) or not all(y["connector_pk"] for y in siblings) or len({y["connector_pk"] for y in siblings})!=len(siblings):why.append("CONNECTOR_SCOPE_NOT_UNIQUE")
        tx=tm.get((a,b));tariff=tariff_status(tx)
        if not tx:why.append("TARIFF_EVIDENCE_NOT_AUDITED")
        elif (tx["source_evse_pk"],tx["source_connector_pk"],tx["tariff_signature"])!=(s["evse_pk"],s["connector_pk"],s["tariff_signature"]):why.append("TARIFF_IDENTITY_MISMATCH")
        if tariff=="TARIFF_SCOPE_UNVERIFIED" or not s["has_price"]:why.append("TARIFF_SCOPE_NOT_PROVEN")
        # Missing operator evidence is explicitly permitted ONLY for this new conjunctive rule.
        # Any recorded FAIL, including operator, remains disqualifying.
        why=sorted(set(why));accepted=not why
        if accepted:added.add((a,b));prefix[pref]+=1
        identity="SIMULATED_V6_CONVERGENT_IDENTITY" if accepted else "NOT_VALIDATED"
        tariff_decision=tariff if accepted else "NO_TARIFF_ATTRIBUTION"
        stats[identity]+=1;stats[tariff_decision]+=1
        for reason in why:reasons[reason]+=1
        out.append(dict(**x,rule_version=VERSION,prior_decision=prev["decision"] if prev else "",prior_blocker=prev["first_blocker"] if prev else "",prior_criteria=j(criteria),operator_evidence=criteria.get("operator","NOT_EVALUATED"),country_evidence=criteria.get("country","NOT_EVALUATED"),recomputed_distance_m=dist,source_evse_pk=s["evse_pk"],source_connector_pk=s["connector_pk"],tariff_signature=s["tariff_signature"],identity_decision=identity,tariff_decision=tariff_decision,tariff_schema=tx["schema"] if tx else "",tariff_schema_issues=tx["schema_issues"] if tx else "[]",live_pilot_observation=(sid,loc) in external,decision_reasons=j(why)))
    union=v5|added
    if added&v5 or len({a for a,b in union})!=len(union) or len({b for a,b in union})!=len(union):raise ValueError("V6 union collision")
    # Preserve all V5 rows with original decisions/criteria, no mutation; separate V6 proposals.
    d=root/"results";d.mkdir()
    write_csv(d/"v5-preserved.csv.gz",prior,list(prior[0]))
    write_csv(d/"v6-simulation-decisions.csv.gz",out,list(out[0]))
    verify(ledger_files["db.sqlite"],p["sqliteSha256"])
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=p,ruleVersion=VERSION,referenceValidated=14968,v5Preserved=len(v5),candidateCount=len(out),simulatedNewIdentities=len(added),simulatedUnion=len(union),simulatedUnionUniqueBothSides=True,decisions=dict(stats),heldReasons=dict(reasons),simulatedByPrefix=dict(prefix),newMatches=0,pricesPromoted=0,supplierCalls=0,automaticPublication=False,simulationOnly=True,limitations=["Operator/prefix crosswalk not independently established; approved exception restricted to convergent multi-EVSE station rule","Eight live sites are corroboration, no extrapolation of operator codes","G6 calculability not assessed; schema-recognized is not calculable","Outside 9983-candidate cohort unchanged in immutable V5 ledger","No publication or Production import"])
    report["exportSha256"]={f.name:digest(f) for f in d.glob("*.csv.gz")};(d/"v6-simulation-report.json").write_text(j(report));print("G5_V6_SIMULATION "+j(report))
if __name__=="__main__":main()
