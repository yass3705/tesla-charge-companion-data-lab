#!/usr/bin/env python3
"""Approved offline V6 identity consolidation: preserve V5 tables, add decisions and effective views."""
import collections
import csv
import gzip
import json
import os
import pathlib
import shutil
import sqlite3
import sys

from scripts.audit_irve_g5_power_scope import download, verify, digest
from scripts.audit_irve_g5_v6_simulation import VERSION, RULE, VALID

ACCEPT="SIMULATED_V6_CONVERGENT_IDENTITY"
REJECT="NOT_VALIDATED"
RECOGNIZED="TARIFF_SCHEMA_RECOGNIZED_PENDING_G6"
REVIEW="TARIFF_SCHEMA_REVIEW_G6"
NONE="NO_TARIFF_ATTRIBUTION"

def rows(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))

def pair(row):
    return int(row["national_id"]),int(row["source_id"])

def csvrow(row):
    return {k:"" if v is None else str(v) for k,v in dict(row).items()}

def cohort(old, decisions, expected_old=14968, expected_candidates=9983, expected_new=9147):
    v5={pair(x) for x in old}
    all6={pair(x) for x in decisions}
    new=set()
    for row in decisions:
        k=pair(row)
        why=json.loads(row["decision_reasons"])
        if row["identity_decision"]==ACCEPT:
            if why or row["tariff_decision"] not in (RECOGNIZED,REVIEW):
                raise ValueError("Invalid accepted V6 decision")
            new.add(k)
        elif row["identity_decision"]!=REJECT or not why or row["tariff_decision"]!=NONE:
            raise ValueError("Invalid held V6 decision")
    union=v5|new
    if (len(old)!=expected_old or len(v5)!=expected_old or len(decisions)!=expected_candidates
        or len(all6)!=expected_candidates or len(new)!=expected_new or v5&new
        or len({n for n,s in union})!=len(union) or len({s for n,s in union})!=len(union)):
        raise ValueError("Cohort or bijection violation")
    return v5,new

def install(db, old, decisions):
    db.executescript("""
    CREATE TABLE v6_decisions(
      national_id INTEGER NOT NULL,source_id INTEGER NOT NULL,
      simulated_identity TEXT NOT NULL,tariff_state TEXT NOT NULL,
      reasons TEXT NOT NULL, evidence_json TEXT NOT NULL,
      PRIMARY KEY(national_id,source_id)) WITHOUT ROWID;
    CREATE TABLE v6_identity_matches(
      national_id INTEGER PRIMARY KEY,source_id INTEGER NOT NULL UNIQUE,
      identity_rule TEXT NOT NULL,tariff_state TEXT NOT NULL);
    CREATE TABLE v6_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE VIEW v6_candidate_effective AS
      SELECT c.*,c.decision AS v5_decision,
        CASE WHEN m.national_id IS NOT NULL THEN 'MATCH_VALIDATED' ELSE c.decision END AS effective_identity_decision,
        m.identity_rule,m.tariff_state AS effective_tariff_state,
        d.simulated_identity,d.reasons AS v6_reasons,d.evidence_json AS v6_evidence_json
      FROM candidate c LEFT JOIN v6_decisions d USING(national_id,source_id)
      LEFT JOIN v6_identity_matches m USING(national_id,source_id);
    CREATE VIEW v6_national_disposition AS
      SELECT d.*,CASE WHEN m.national_id IS NULL THEN 0 ELSE 1 END AS v6_validated_count,
        CASE WHEN m.national_id IS NOT NULL THEN 'MATCH_VALIDATED' ELSE d.result END AS v6_result
      FROM national_disposition d LEFT JOIN v6_identity_matches m USING(national_id);
    CREATE VIEW v6_source_disposition AS
      SELECT d.*,CASE WHEN m.source_id IS NULL THEN 0 ELSE 1 END AS v6_validated_count,
        CASE WHEN m.source_id IS NOT NULL THEN 'MATCH_VALIDATED' ELSE d.result END AS v6_result
      FROM source_disposition d LEFT JOIN v6_identity_matches m USING(source_id);
    """)
    db.executemany("INSERT INTO v6_decisions VALUES(?,?,?,?,?,?)",[
        (*pair(x),x["identity_decision"],x["tariff_decision"],x["decision_reasons"],
         json.dumps(x,ensure_ascii=False,sort_keys=True)) for x in decisions])
    db.executemany("INSERT INTO v6_identity_matches VALUES(?,?,?,?)",[
        (*pair(x),RULE,"V5_PENDING_G6") for x in old]+[
        (*pair(x),VERSION,x["tariff_decision"]) for x in decisions if x["identity_decision"]==ACCEPT])

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if (pin["purpose"]!="offline_g5_v6_identity_consolidation" or pin["ruleVersion"]!=VERSION
        or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False
        or pin["identityOnly"] is not True):raise ValueError("Scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    base=download(root/"v5",pin["ledger"],{"db.sqlite":("g5-matching-v5.sqlite",),"report.json":("v5-report.json",)})
    sim=download(root/"simulation",pin["simulation"],{
        "v5-preserved.csv.gz":("v5-preserved.csv.gz",),
        "v6-simulation-decisions.csv.gz":("v6-simulation-decisions.csv.gz",),
        "report.json":("v6-simulation-report.json",)})
    verify(base["db.sqlite"],pin["sqliteSha256"])
    r=json.loads(sim["report.json"].read_text());b=json.loads(base["report.json"].read_text())
    if (r["codeSha"]!=pin["simulation"]["codeSha"] or r["ruleVersion"]!=VERSION
        or r["sourcePin"]!=pin["simulationSourcePin"] or r["sourcePin"]["ledger"]!=pin["ledger"]
        or r["sourcePin"]["sqliteSha256"]!=pin["sqliteSha256"]
        or r["exportSha256"]!=pin["exportSha256"] or r["simulationOnly"] is not True
        or r["simulatedUnionUniqueBothSides"] is not True or r["simulatedUnion"]!=24115
        or any(r[k]!=0 for k in ("supplierCalls","newMatches","pricesPromoted"))
        or r["automaticPublication"] is not False or b["newValidated"]!=14968
        or b["codeSha"]!=pin["ledger"]["codeSha"] or b["ruleVersion"]!=RULE
        or b["sqliteSha256"]!=pin["sqliteSha256"]):
        raise ValueError("Pinned lineage or simulation safety")
    for name,h in pin["exportSha256"].items():verify(sim[name],h)
    old=rows(sim["v5-preserved.csv.gz"]);decisions=rows(sim["v6-simulation-decisions.csv.gz"])
    v5,new=cohort(old,decisions)
    count=collections.Counter(x["identity_decision"] for x in decisions)
    count.update(x["tariff_decision"] for x in decisions)
    reasons=collections.Counter(y for x in decisions for y in json.loads(x["decision_reasons"]))
    if dict(count)!=r["decisions"] or dict(reasons)!=r["heldReasons"]:
        raise ValueError("Decision reconciliation")
    out=root/"results";out.mkdir()
    path=out/"g5-matching-v6.sqlite";shutil.copyfile(base["db.sqlite"],path)
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("V5 integrity")
    prior=[csvrow(x) for x in db.execute("SELECT c.*,p.criteria AS criterion_evidence FROM candidate c JOIN criterion_pattern p ON p.id=c.pattern_id WHERE c.decision=? ORDER BY c.national_id,c.source_id",(VALID,))]
    if prior!=old:raise ValueError("V5 export differs from parent")
    if db.execute("SELECT count(*) FROM candidate").fetchone()[0]!=581978:raise ValueError("Historical candidate coverage")
    for x in decisions:
        n,s=pair(x)
        z=db.execute("""SELECT c.decision,c.first_blocker,p.criteria,n.station_id,n.evse_id,
            s.location_pk,s.evse_pk,s.connector_pk,s.tariff_signature
            FROM candidate c JOIN criterion_pattern p ON p.id=c.pattern_id
            JOIN national_connector n ON n.id=c.national_id JOIN source_connector s ON s.id=c.source_id
            WHERE c.national_id=? AND c.source_id=?""",(n,s)).fetchone()
        if z is None or z["decision"]!=x["prior_decision"] or (z["first_blocker"] or "")!=x["prior_blocker"]:
            raise ValueError("Missing or changed prior decision")
        criteria=json.loads(z["criteria"])["criteria"]
        if criteria!=json.loads(x["prior_criteria"]):raise ValueError("Historical criteria differ")
        for key,field in (("station_id","station_id"),("evse_id","evse_id"),("location_pk","location_pk"),("evse_pk","source_evse_pk"),("connector_pk","source_connector_pk"),("tariff_signature","tariff_signature")):
            if ("" if z[key] is None else str(z[key]))!=x[field]:raise ValueError("Connector lineage")
        if (n,s) in new:
            if any(v=="FAIL" for v in criteria.values()) or x["strict_multi_site_review"].lower()!="true":
                raise ValueError("Accepted contradiction or missing strict scope")
            if not x["tariff_signature"]:raise ValueError("Missing individual signature")
    install(db,old,decisions)
    report={"ruleVersion":VERSION,"codeSha":os.environ.get("GITHUB_SHA"),"sourcePin":pin,
        "v5Preserved":len(v5),"v6ApprovedIdentities":len(new),"validatedIdentityPairs":len(v5|new),
        "v6Held":len(decisions)-len(new),"historicalCandidatesPreserved":581978,
        "identityUnionUniqueBothSides":True,"v6Reasons":dict(reasons),
        "v6TariffStates":dict(collections.Counter(x["tariff_decision"] for x in decisions)),
        "pricesPromoted":0,"supplierCalls":0,"automaticPublication":False,"identityOnly":True,
        "g6Calculability":"NOT_EVALUATED","parentTablesUnchanged":True,
        "limitations":["V5 base tables are preserved; use v6_candidate_effective and v6_identity_matches for consolidated identity decisions","No Production import, no price ranking, no publication","Proof retention beyond Actions expiry requires a separately retained authorized backup"]}
    for k,v in report.items():
        db.execute("INSERT INTO v6_metadata VALUES(?,?)",(k,json.dumps(v,ensure_ascii=False,sort_keys=True)))
    db.commit()
    # Compare every original table, both directions, with the pinned read-only V5 database.
    db.execute("ATTACH DATABASE ? AS parent",(base["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",))
    tables=[x[0] for x in db.execute("SELECT name FROM parent.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for name in tables:
        if not name.replace("_","").isalnum():raise ValueError("Unexpected table")
        if db.execute(f'SELECT 1 FROM (SELECT * FROM main."{name}" EXCEPT SELECT * FROM parent."{name}") LIMIT 1').fetchone() or db.execute(f'SELECT 1 FROM (SELECT * FROM parent."{name}" EXCEPT SELECT * FROM main."{name}") LIMIT 1').fetchone():
            raise ValueError("Parent table changed: "+name)
    actual={(x[0],x[1]) for x in db.execute("SELECT national_id,source_id FROM v6_identity_matches")}
    if actual!=v5|new or db.execute("SELECT count(*) FROM v6_candidate_effective").fetchone()[0]!=581978:
        raise ValueError("Effective identity coverage")
    for view in ("v6_national_disposition","v6_source_disposition"):
        if db.execute(f"SELECT sum(v6_validated_count) FROM {view}").fetchone()[0]!=24115:
            raise ValueError("Disposition coverage")
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("V6 integrity")
    db.close();verify(base["db.sqlite"],pin["sqliteSha256"])
    for name in ("v5-preserved.csv.gz","v6-simulation-decisions.csv.gz"):
        shutil.copyfile(sim[name],out/name)
    shutil.copyfile(sim["report.json"],out/"v6-simulation-report.json")
    report["sqliteSha256"]=digest(path)
    report["exportSha256"]={x.name:digest(x) for x in out.iterdir() if x.is_file()}
    (out/"v6-consolidation-report.json").write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("G5_V6_CONSOLIDATION "+json.dumps({k:v for k,v in report.items() if k!="sourcePin"},sort_keys=True))

if __name__=="__main__":main()
