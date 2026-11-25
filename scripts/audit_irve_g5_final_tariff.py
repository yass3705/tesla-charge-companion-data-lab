#!/usr/bin/env python3
"""Offline tariff evidence only; does not calculate session prices or validate identity."""
import collections as C
import json,os,pathlib,sqlite3,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import rows,cached_connectors,signature
from scripts.audit_irve_g5_nonexact_inventory import RULE,VALID,j,sk
from scripts.audit_irve_g5_restriction_replay import classify,details
from scripts.audit_electroverse_g5_real_matching import ident,plug,mode,number
from scripts.audit_irve_g5_address_gps import compatible

BASE={"PREFIX_RULE_NOT_INDEPENDENTLY_DOCUMENTED","CPO_PROOF_NOT_ESTABLISHED","TARIFF_SCOPE_NOT_VALIDATED"}
def verified(s,obs):
    if obs is None:return False
    ref,c=obs
    return ident(ref)==s["reference_normalized"] and plug(c.get("standard"))==s["plug"] and number(c.get("kilowatts"))==s["kw"] and signature(c)==s["tariff_signature"]
def unique_scope(n,s,nn,ss):
    return sum(compatible(x,s) for x in nn)==1 and sum(compatible(n,x) for x in ss)==1 and compatible(n,s)
def homogeneity(values):
    if not values or any(not v for v in values):return "MISSING_OR_UNVERIFIED"
    return "SAME_RAW_SIGNATURE" if len(set(values))==1 else "DIFFERENT_RAW_SIGNATURES"
def main():
    p=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if p["purpose"]!="g5_final_station_and_tariff_evidence_only" or p["ruleVersion"]!=RULE or p["offlineSupplierCalls"] is not False or p["automaticPublication"] is not False:raise ValueError("Scope")
    b=download(root/"v5",p["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    verify(b["db.sqlite"],p["sqliteSha256"]);rp=json.loads(b["report.json"].read_text())
    if rp["codeSha"]!=p["ledger"]["codeSha"] or rp["ruleVersion"]!=RULE or rp["sourcePin"]["tariff"]!=p["tariff"] or rp["newValidated"]!=14968:raise ValueError("Ledger lineage")
    a=download(root/"station",p["stationAudit"],{"candidate-references.csv.gz":("candidate-references.csv.gz",),"station-references.csv.gz":("station-references.csv.gz",),"report.json":("station-reference-report.json",)})
    for f,h in p["exports"].items():verify(a[f],h)
    ar=json.loads(a["report.json"].read_text())
    if ar["codeSha"]!=p["stationAudit"]["codeSha"] or ar["sourcePin"]["ledger"]!=p["ledger"] or ar["sourcePin"]["tariff"]!=p["tariff"] or ar["sourcePin"]["pilot"]!=p["pilot"] or ar["referenceValidated"]!=14968:raise ValueError("Station lineage")
    candidates=rows(a["candidate-references.csv.gz"]);targets=[x for x in candidates if x["strict_multi_site_review"].lower()=="true"]
    sites={(x["station_id"],x["location_pk"]):x for x in rows(a["station-references.csv.gz"])}
    if len(candidates)!=9983 or len(targets)!=9147 or len(sites)!=3439 or len({(x["station_id"],x["location_pk"]) for x in targets})!=3058:raise ValueError("Cohort")
    db=sqlite3.connect(b["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Integrity")
    meta={x["key"]:json.loads(x["value"]) for x in db.execute("SELECT * FROM metadata")}
    if meta["ruleVersion"]!=RULE or meta["codeSha"]!=rp["codeSha"]:raise ValueError("Metadata")
    valid={(x[0],x[1]) for x in db.execute("SELECT national_id,source_id FROM candidate WHERE decision=?",(VALID,))}
    vn={a for a,b in valid};vs={b for a,b in valid}
    if len(valid)!=14968 or len(vn)!=14968 or len(vs)!=14968:raise ValueError("Reference")
    ns={x["id"]:dict(x) for x in db.execute("SELECT * FROM national_connector")}
    ss={x["id"]:dict(x) for x in db.execute("SELECT * FROM source_connector")}
    ng=C.defaultdict(list);sg=C.defaultdict(list);lg=C.defaultdict(list)
    for n in ns.values():ng[(n["station_id"],n["evse_id"])].append(n)
    for s in ss.values():sg[(s["location_pk"],s["evse_pk"])].append(s);lg[s["location_pk"]].append(s)
    ids={(int(x["national_id"]),int(x["source_id"])) for x in targets}
    if len(ids)!=9147 or len({a for a,b in ids})!=9147 or len({b for a,b in ids})!=9147 or any(a in vn or b in vs for a,b in ids):raise ValueError("Occupation")
    locations={ss[b]["location_pk"] for a,b in ids}
    wanted={sk(s) for l in locations for s in lg[l] if s["connector_pk"]}
    raw=cached_connectors(root/"tariff",p["tariff"],meta["tariffManifestSha256"],wanted)
    ok={s["id"]:verified(s,raw.get(sk(s))) for l in locations for s in lg[l]}
    signatures={s["id"]:s["tariff_signature"] if ok[s["id"]] else None for l in locations for s in lg[l]}
    out=[];stats=C.Counter();issues=C.Counter();siteout=[];byloc=C.defaultdict(list)
    for x in targets:
        n,s=ns[int(x["national_id"])],ss[int(x["source_id"])]
        site=sites[(x["station_id"],x["location_pk"])]
        if n["station_id"]!=x["station_id"] or s["location_pk"]!=x["location_pk"] or n["evse_id"]!=x["evse_id"] or ident(s["physical_reference"])!=x["reference"] or set(json.loads(x["diagnostics"]))!=BASE or site["strict_multi_site_review"].lower()!="true":raise ValueError("Candidate identity")
        nn=ng[(n["station_id"],n["evse_id"])];siblings=sg[(s["location_pk"],s["evse_pk"])]
        unique=unique_scope(n,s,nn,siblings) and all(y["connector_pk"] for y in siblings) and len({y["connector_pk"] for y in siblings})==len(siblings)
        sigs=[signatures[y["id"]] for y in siblings]
        sh=homogeneity(sigs);lh=homogeneity([signatures[y["id"]] for y in lg[s["location_pk"]]])
        schema="RAW_CONNECTOR_NOT_VERIFIED";err=[];dims=[];conds=[];types=[];rd="[]";payload=None
        if ok[s["id"]]:
            c=raw[sk(s)][1];schema,err,dims,conds,types=classify(c);rd=details(c)["restriction_diagnostics"];payload={k:c.get(k) for k in ("isChargingFree","priceComponents","complexPricingDetail")}
        blockers=[]
        if not ok[s["id"]]:blockers.append("RAW_CONNECTOR_NOT_VERIFIED")
        if not unique:blockers.append("CONNECTOR_SCOPE_NOT_UNIQUE")
        if not s["has_price"]:blockers.append("NO_PRICE")
        if not schema.startswith("DIRECT_"):blockers.append("SCHEMA_REVIEW_REQUIRED")
        # Different sibling signatures are not a blocker when the actual connector is uniquely identified.
        # Do not transfer any sibling or site-wide tariff.
        scope="DIRECT_CONNECTOR_EVIDENCE_ONLY" if ok[s["id"]] and unique and s["has_price"] else "SCOPE_REVIEW"
        row={**x,"source_evse_pk":s["evse_pk"],"source_connector_pk":s["connector_pk"],"national_plug":n["plug"],"source_plug":s["plug"],"national_kw":n["kw"],"source_kw":s["kw"],"raw_verified":ok[s["id"]],"scope":scope,"evse_signature_homogeneity":sh,"station_signature_homogeneity":lh,"tariff_signature":s["tariff_signature"],"schema":schema,"schema_issues":j(err),"dimensions":j(dims),"conditions":j(conds),"restriction_types":j(types),"restriction_diagnostics":rd,"raw_price_payload":j(payload),"additional_blockers":j(blockers),"identity_disposition":"NOT_VALIDATED"}
        out.append(row);byloc[(n["station_id"],s["location_pk"])].append(row)
        stats["schema:"+schema]+=1;stats["scope:"+scope]+=1;stats["evse:"+sh]+=1;stats["site:"+lh]+=1
        if not blockers:stats["SCHEMA_AND_CONNECTOR_SCOPE_REVIEW_PASS"]+=1
        for y in err:issues[y]+=1
        for y in blockers:stats[y]+=1
    for (sid,loc),rr in sorted(byloc.items()):
        siteout.append(dict(station_id=sid,location_pk=loc,candidates=len(rr),source_connector_count=len(lg[loc]),raw_verified_connectors=sum(ok[s["id"]] for s in lg[loc]),signature_homogeneity=homogeneity([signatures[s["id"]] for s in lg[loc]]),schema_scope_review_pass=sum(not json.loads(x["additional_blockers"]) for x in rr)))
    d=root/"results";d.mkdir()
    for name,rr in [("tariff-candidates.csv.gz",out),("tariff-stations.csv.gz",siteout)]:write_csv(d/name,rr,list(rr[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=p,referenceValidated=14968,candidates=len(out),stations=len(siteout),rawSiblingConnectors=len(ok),rawSiblingVerified=sum(ok.values()),diagnostics=dict(stats),schemaIssues=dict(issues),newMatches=0,pricesPromoted=0,supplierCalls=0,matchingRulesChanged=False,automaticPublication=False,limitations=["Connector-scoped raw tariff evidence is not EVSE identity","Unknown conditions including DATE_BASED are not normalized automatically","G6 calculation and billing semantics not validated","No tariff transfer between siblings"])
    report["exportSha256"]={f.name:digest(f) for f in d.glob("*.csv.gz")};(d/"tariff-evidence-report.json").write_text(j(report));print("G5_FINAL_TARIFF "+j(report))
if __name__=="__main__":main()
