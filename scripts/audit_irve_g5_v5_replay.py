#!/usr/bin/env python3
"""G5 v5 cumulative replay on pinned France ledger; no supplier or price publication."""
import collections
import json
import math
import os
import pathlib
import shutil
import sqlite3
import sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import rows,pair,table,independent_unique,cached_connectors,signature
from scripts.audit_irve_g5_restriction_replay import classify,RECOGNIZED
from scripts.audit_irve_g5_ac_1kw_ab import replay_pair
from scripts.audit_electroverse_g5_real_matching import (ident,plug,mode,number,decision_from_criteria,
    read_power_scope,AC_TOLERANCE_RULE,dump)
RULE="g5-fr-2026-11-24-v5-exact-independent-power-divergence"
REASON="EXACT_IDENTITY_POWER_DIVERGENCE_USER_APPROVED"
VALID="MATCH_VALIDATED"
CHANGED={"power","cardinality","tariff_scope","tariff_homogeneity"}
POSITIVE={"station_identity","station_uniqueness","evse_identity","evse_uniqueness","current","plug"}

def key(s):return s["location_pk"],s["evse_pk"],s["connector_pk"]
def blockers(v,n,s,profiles,siblings,global_unique,raw,occupied,scope):
    c=v["criteria"];reasons=[]
    if v["decision"]!="REJECTED_CONTRADICTION" or c["power"]!="FAIL":reasons.append("NOT_V4_POWER_CONTRADICTION")
    if any(c[k]!="PASS" for k in POSITIVE) or not global_unique:reasons.append("IDENTITY_OR_GLOBAL_UNIQUENESS")
    if any(c[k]=="FAIL" for k in c if k!="power"):reasons.append("OTHER_CONTRADICTION")
    if not independent_unique(s,n,profiles,siblings):reasons.append("INDEPENDENT_CONNECTOR_UNIQUENESS_NOT_PROVEN")
    if occupied:reasons.append("V4_MATCH_ALREADY_EXISTS")
    if not s["has_price"]:reasons.append("MISSING_SOURCE_PRICE")
    if s["recent_fault"]:reasons.append("RECENT_FAULT_EXCLUSION")
    a,b=n["kw"],s["kw"]
    if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>0 for x in (a,b)) or a==b:
        reasons.append("INVALID_POWER_DIVERGENCE")
    if not (n["mode"]=="DC" and scope in ("SINGLE_DECLARED_TYPE_NOMINAL_ONLY","MULTITYPE_PDC_INDIVIDUAL_POWER_UNPROVEN")
        or n["mode"]=="AC" and scope=="MULTITYPE_PDC_INDIVIDUAL_POWER_UNPROVEN" and a is not None and b is not None and b>a):
        reasons.append("OUTSIDE_APPROVED_POWER_SCOPE")
    if scope=="MULTITYPE_PDC_INDIVIDUAL_POWER_UNPROVEN" and a is not None and b is not None and b<=a:
        reasons.append("OUTSIDE_AUDITED_MULTITYPE_ABOVE_NOMINAL")
    if raw is None:reasons.append("RAW_CONNECTOR_NOT_PROVEN")
    else:
        ref,connector=raw
        if (ident(ref)!=s["reference_normalized"] or plug(connector.get("standard"))!=s["plug"]
            or mode(plug(connector.get("standard")))!=s["mode"] or number(connector.get("kilowatts"))!=s["kw"]
            or signature(connector)!=s["tariff_signature"]):reasons.append("RAW_CONNECTOR_MISMATCH")
        evidence,issues,*_=classify(connector)
        if evidence!=RECOGNIZED or issues:reasons.append("TARIFF_SCHEMA_OR_POWER_CONDITION_REVIEW")
    return reasons

def apply_c(v,reasons):
    if reasons:return v
    c=dict(v["criteria"])
    # Observed power FAIL is preserved separately. The power equivalence
    # criterion is not applicable to identity under this documented exception.
    c.update(power="NOT_APPLICABLE",cardinality="PASS",tariff_scope="PASS",tariff_homogeneity="NOT_APPLICABLE")
    out=decision_from_criteria(c)
    if out["decision"]!=VALID:raise ValueError("C leaves unresolved criteria")
    out.update(power_delta_kw=v["power_delta_kw"],power_justification=REASON)
    return out

def exact_sql():
    return """SELECT c.*,p.criteria AS pattern FROM candidate c
        JOIN criterion_pattern p ON p.id=c.pattern_id
        JOIN national_connector n ON n.id=c.national_id JOIN source_connector s ON s.id=c.source_id
        WHERE s.reference_normalized<>'' AND n.evse_normalized=s.reference_normalized
        ORDER BY c.national_id,c.source_id"""

def count_query(db,sql):return {r[0]:r[1] for r in db.execute(sql)}
def assert_unique(pairs):
    if any(len({p[i] for p in pairs})!=len(pairs) for i in (0,1)):raise ValueError("Duplicate validated target or source")
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text())
    if pin["purpose"]!="offline_g5_v5_cumulative_exact_replay" or pin["ruleVersion"]!=RULE or pin["supplierCalls"] is not False or pin["automaticPublication"] is not False:raise ValueError("Unapproved scope")
    root=pathlib.Path(sys.argv[2]);root.mkdir()
    base=download(root/"base",pin["baseline"],{"db.sqlite":("g5-matching.sqlite",),"summary.json":("summary.json",)})
    v4=download(root/"v4",pin["v4"],{"pairs.csv.gz":("exact-ab.csv.gz",),"report.json":("ab-report.json",)})
    scope=download(root/"scope",pin["scope"],{"scope.csv.gz":("active-pdc-power-scope.csv.gz",),"report.json":("power-scope-report.json",)})
    rp=pin["restrictionReplay"]
    proof=download(root/"restriction",rp,{"pairs.csv.gz":("schema-pairs.csv.gz",),"candidates.csv.gz":("restriction-candidates.csv.gz",),"history.csv.gz":("historical-signature-review.csv.gz",),"report.json":("schema-report.json",)})
    for path,expected in [(base["db.sqlite"],pin["sqliteSha256"]),(v4["pairs.csv.gz"],pin["v4PairsSha256"]),(scope["scope.csv.gz"],pin["scopeCsvSha256"]),(proof["pairs.csv.gz"],rp["pairsSha256"]),(proof["candidates.csv.gz"],rp["candidatesSha256"]),(proof["history.csv.gz"],rp["historySha256"])]:verify(path,expected)
    sm,vr,sp,rr=[json.loads(x.read_text()) for x in (base["summary.json"],v4["report.json"],scope["report.json"],proof["report.json"])]
    if (sm["codeSha"]!=pin["baseline"]["codeSha"] or sm["sqliteSha256"]!=pin["sqliteSha256"] or sm["electroverseTariffArtifact"]!=pin["tariff"]["artifact"] or sm["nationalArtifactProvenance"]["nationalArtifact"]!=pin["nationalArtifact"]
        or vr["codeSha"]!=pin["v4"]["codeSha"] or vr["ruleVersionB"]!=AC_TOLERANCE_RULE or vr["exportSha256"]!=pin["v4PairsSha256"]
        or vr["sourcePin"]["baseline"]!=pin["baseline"] or vr["sourcePin"]["scope"]!=pin["scope"]
        or sp["sourcePin"]["national"]["artifact"]!=pin["nationalArtifact"] or sp["rawProjectionReconciled"] is not True
        or rr["codeSha"]!=rp["codeSha"] or rr["referenceValidated"]!=13786 or rr["newRecognized"]!=1182 or rr["lostRecognized"]!=0 or rr["newMatches"]!=0 or rr["pricesPromoted"]!=0
        or any(rr["sourcePin"][k]!=pin[k] for k in ("baseline","v4","tariff","scenario","sqliteSha256","v4PairsSha256","scenarioPairsSha256"))
        or any(rr["exportSha256"][f]!=rp[k] for f,k in (("schema-pairs.csv.gz","pairsSha256"),("restriction-candidates.csv.gz","candidatesSha256"),("historical-signature-review.csv.gz","historySha256")))):
        raise ValueError("Pinned provenance mismatch")
    power_scope=read_power_scope(scope["scope.csv.gz"],pin["scopeCsvSha256"],pin["nationalArtifact"])
    prior=rows(v4["pairs.csv.gz"]);vmap={pair(x):x for x in prior}
    residual=rows(proof["pairs.csv.gz"]);rmap={pair(x):x for x in residual}
    candidates=rows(proof["candidates.csv.gz"]);approved={pair(x):x for x in candidates}
    historical=rows(proof["history.csv.gz"]);hist={pair(x) for x in historical}
    old={k for k,x in vmap.items() if x["b_decision"]==VALID}
    if (len(prior)!=21980 or len(vmap)!=21980 or len(old)!=13786 or dict(collections.Counter(x["b_decision"] for x in prior))!=vr["b"]
        or len(residual)!=1317 or len(rmap)!=1317 or len(candidates)!=1182 or len(approved)!=1182
        or set(approved)!={k for k,x in rmap.items() if x["identity_candidate"].lower()=="true"}
        or len(historical)!=30 or len(hist)!=30 or not hist<=old or set(approved)&old):
        raise ValueError("Pinned cohort mismatch")
    assert_unique(old);assert_unique(old|set(approved))
    vn={x[0] for x in old};vs={x[1] for x in old}
    out=root/"results";out.mkdir()
    path=out/"g5-matching-v5.sqlite";shutil.copyfile(base["db.sqlite"],path)
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Baseline integrity")
    meta={r["key"]:json.loads(r["value"]) for r in db.execute("SELECT * FROM metadata")}
    for k in ("codeSha","ruleVersion","nationalArtifactProvenance","exactIdentityCandidatePairs","candidateComparisons","tariffManifestSha256"):
        if meta[k]!=sm[k]:raise ValueError("Baseline metadata mismatch "+k)
    db.execute("CREATE TABLE v5_parent_metadata AS SELECT * FROM metadata")
    ns={};profiles=collections.defaultdict(list);owners=collections.defaultdict(set)
    for r in db.execute("SELECT * FROM national_operational_scope"):
        owners[ident(r["evse_id"])].add(r["station_id"])
    for r in db.execute("SELECT * FROM national_connector"):
        n=dict(r);n["power_scope"]=power_scope[(n["station_id"],n["evse_id"])]["scope"]
        ns[n["id"]]=n;profiles[n["evse_normalized"]].append(n)
    ss={};siblings=collections.defaultdict(list);refowners=collections.defaultdict(set)
    for r in db.execute("SELECT * FROM source_connector"):
        s=dict(r);s.update(pk=s["evse_pk"],connector=s["connector_pk"],price=bool(s["has_price"]))
        ss[s["id"]]=s;siblings[(s["location_pk"],s["evse_pk"])].append(s)
        if s["reference_normalized"]:refowners[s["reference_normalized"]].add((s["location_pk"],s["evse_pk"]))
    raw=cached_connectors(root/"tariff",pin["tariff"],sm["tariffManifestSha256"],{key(ss[s]) for n,s in rmap})
    db.execute("""CREATE TABLE v5_exact_replay(national_id INTEGER,source_id INTEGER,v4_decision TEXT,v5_decision TEXT,
      v4_criteria TEXT,v5_criteria TEXT,observed_power_criterion TEXT,power_justification TEXT,c_review TEXT,
      c_blockers TEXT,tariff_schema TEXT,restriction_diagnostics TEXT,PRIMARY KEY(national_id,source_id)) WITHOUT ROWID""")
    patterns={r["criteria"]:r["id"] for r in db.execute("SELECT * FROM criterion_pattern")}
    nextid=max(patterns.values())+1
    updates=[];journal=[];transitions=collections.Counter();final=set();gained=set();seen=set();review_counts=collections.Counter();operator=collections.Counter()
    for r in list(db.execute(exact_sql())):
        k=(r["national_id"],r["source_id"]);seen.add(k);n,s=ns[k[0]],ss[k[1]]
        pat=json.loads(r["pattern"]);v=vmap[k]
        if not r["method"].startswith("exact+"):raise ValueError("Unexpected exact method")
        args=(s,n,profiles[n["evse_normalized"]],siblings[(s["location_pk"],s["evse_pk"])],pat["criteria"])
        legacy=replay_pair(*args,False)
        if any(legacy[x]!=pat[x] for x in ("criteria","blocking","missing","not_evaluated")) or legacy["decision"]!=r["decision"]:raise ValueError("v2 replay changed")
        before=replay_pair(*args,True,True)
        if (before["criteria"]!=json.loads(v["b_criteria"]) or before["blocking"]!=json.loads(v["b_blockers"]) or before["decision"]!=v["b_decision"]
            or (before["first_blocker"] or "")!=v["b_first_blocker"] or (before["power_justification"] or "")!=v["power_reason_b"]):raise ValueError("v4 replay changed")
        after=before;why=[];tariff=None;diag=None;status="NOT_EVALUATED_OUTSIDE_AUDITED_COHORT"
        if k in hist:status="KEEP_V4_HISTORICAL"
        if k in rmap:
            e=rmap[k];tariff=e["new_schema_evidence"];diag=e["restriction_diagnostics"]
            observed=raw.get(key(s))
            if observed is not None:
                cl=classify(observed[1])
                if cl[0]!=tariff or cl[1]!=json.loads(e["schema_issues"]):raise ValueError("Tariff evidence differs from restriction replay")
            why=blockers(before,n,s,profiles[n["evse_normalized"]],siblings[(s["location_pk"],s["evse_pk"])],
                len(owners[n["evse_normalized"]])==1 and len(refowners[s["reference_normalized"]])==1,
                observed,k[0] in vn or k[1] in vs,n["power_scope"])
            if k in approved:
                if why:raise ValueError("Approved C candidate fails replay: "+str(k)+" "+str(why))
                if tariff!=RECOGNIZED or json.loads(e["schema_issues"]):raise ValueError("Unrecognized tariff schema")
                after=apply_c(before,why);status="C_VALIDATED"
                gained.add(k);operator[v["operator"]]+=1
            else:
                # Do not expand beyond the approved audited candidates.
                why=sorted(set(why+json.loads(e["independent_blockers"])+["OUTSIDE_APPROVED_COHORT"]))
                status="C_HELD"
        if {x for x in before["criteria"] if before["criteria"][x]!=after["criteria"][x]}-CHANGED:raise ValueError("Unrelated criteria changed")
        if after["decision"]==VALID:final.add(k)
        transitions[(before["decision"],after["decision"])]+=1;review_counts[status]+=1
        pattern=dump({x:after[x] for x in ("criteria","blocking","missing","not_evaluated")})
        if pattern not in patterns:
            patterns[pattern]=nextid;db.execute("INSERT INTO criterion_pattern VALUES(?,?)",(nextid,pattern));nextid+=1
        d=json.loads(r["details"])
        d.update(power_justification=after["power_justification"],power_delta_kw=after["power_delta_kw"],
            scope_evidence="unique_exact_source_connector_independent_of_power" if status=="C_VALIDATED" else ("unique_exact_source_connector_to_national_profile" if after["criteria"]["tariff_scope"]=="PASS" else None),
            v5_c_review=status,v5_c_blockers=why,v5_observed_v4_power=before["criteria"]["power"])
        if status=="C_VALIDATED":
            d.update(v5_raw_signature=s["tariff_signature"],v5_tariff_schema=tariff,v5_g6_calculability="NOT_EVALUATED")
        updates.append((after["decision"],after["first_blocker"],dump(d),patterns[pattern],*k))
        journal.append(( *k,before["decision"],after["decision"],dump(before["criteria"]),dump(after["criteria"]),before["criteria"]["power"],after["power_justification"],status,dump(why),tariff,diag))
    if seen!=set(vmap) or gained!=set(approved) or old-final or final-old!=gained:raise ValueError("Cumulative replay mismatch")
    assert_unique(final)
    db.executemany("UPDATE candidate SET decision=?,first_blocker=?,details=?,pattern_id=? WHERE national_id=? AND source_id=?",updates)
    db.executemany("INSERT INTO v5_exact_replay VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",journal)
    # Full dispositions: non-exact candidates untouched, recompute profile/source aggregates.
    for name,col,empty in (("national_disposition","national_id","NO_CANDIDATE_IN_CACHED_SCOPE"),("source_disposition","source_id","NO_NATIONAL_CANDIDATE")):
        counts={r[0]:(r[1],r[2]) for r in db.execute(f"SELECT {col},count(*),sum(decision=?) FROM candidate GROUP BY {col}",(VALID,))}
        values=[]
        for r in db.execute(f"SELECT {col},candidate_count FROM {name}"):
            k=r[0];c,v=counts.get(k,(0,0))
            if c!=r[1]:raise ValueError("Candidate coverage changed")
            values.append((v,empty if not c else VALID if v else "CANDIDATES_UNRESOLVED",k))
        db.executemany(f"UPDATE {name} SET validated_count=?,result=? WHERE {col}=?",values)
    all_counts=count_query(db,"SELECT decision,count(*) FROM candidate GROUP BY decision")
    expected=collections.Counter(vr["allCandidateBProjectedDispositions"])
    for (a,b),n in transitions.items():expected[a]-=n;expected[b]+=n
    if dict(+expected)!=all_counts or sum(all_counts.values())!=sm["candidateComparisons"]:raise ValueError("Global disposition mismatch")
    observed={(r[0],r[1]) for r in db.execute("SELECT national_id,source_id FROM candidate WHERE decision=?",(VALID,))}
    if observed!=final:raise ValueError("Global validation differs")
    # Compare non-exact rows against immutable parent by full row equality.
    db.execute("ATTACH DATABASE ? AS original",(base["db.sqlite"].resolve().as_uri()+"?mode=ro",))
    neq=db.execute("""SELECT count(*) FROM candidate c JOIN original.candidate o USING(national_id,source_id)
        LEFT JOIN v5_exact_replay x USING(national_id,source_id) WHERE x.national_id IS NULL AND
        (c.method IS NOT o.method OR c.decision IS NOT o.decision OR c.first_blocker IS NOT o.first_blocker OR c.details IS NOT o.details OR c.prior_offer_ids IS NOT o.prior_offer_ids OR c.alias_files IS NOT o.alias_files OR c.pattern_id IS NOT o.pattern_id)""").fetchone()[0]
    if neq:raise ValueError("Non-exact rows changed")
    exact_counts=count_query(db,"SELECT v5_decision,count(*) FROM v5_exact_replay GROUP BY v5_decision")
    nd=count_query(db,"SELECT result,count(*) FROM national_disposition GROUP BY result");sd=count_query(db,"SELECT result,count(*) FROM source_disposition GROUP BY result")
    report={"ruleVersion":RULE,"codeSha":os.environ.get("GITHUB_SHA"),"sourcePin":pin,"referenceV4":len(old),"newValidated":len(final),"gained":len(gained),"lost":len(old-final),"reassigned":0,
        "newDC":sum(ns[n]["mode"]=="DC" for n,s in gained),"newAC":sum(ns[n]["mode"]=="AC" for n,s in gained),"distinctGainedPdc":len({(ns[n]["station_id"],ns[n]["evse_id"]) for n,s in gained}),
        "historicalRetained":len(hist&final),"exactPairs":len(seen),"nonExactUnchanged":sm["candidateComparisons"]-len(seen),"allCandidateDispositions":all_counts,
        "exactDispositions":exact_counts,"nationalDisposition":nd,"sourceDisposition":sd,"transitions":table(transitions,["v4","v5"]),
        "cReview":dict(review_counts),"gainedByOperator":dict(operator),"validatedWithRecentHistoricalFault":sum(ss[s]["recent_fault"] for n,s in final),
        "newWithRecentHistoricalFault":sum(ss[s]["recent_fault"] for n,s in gained),"noDuplicate":True,"supplierCalls":0,"pricesPromoted":0,"automaticPublication":False,
        "limitations":["Full pinned decision ledger, not a new collection or G6 calculation.", "Non-exact candidates retained, not revalidated.", "Observed v4 power FAIL retained separately; NOT_APPLICABLE only for identity criterion under approved rule C.", "Artifact expiry and Production generation binding still outstanding."]}
    # Update authoritative summary values; retain immutable parent metadata separately.
    updated=dict(sm)
    # Remove obsolete aggregate fields that describe the v2 decision vectors.
    for k in ("allBlockingCriteria","firstBlockingCriteria","missingCriteriaNonBlocking","exactPairsPassingPlugCurrentPower"):
        updated.pop(k,None)
    updated.update(ruleVersion=RULE,codeSha=report["codeSha"],candidateDisposition=all_counts,exactCandidateDisposition=exact_counts,
        exactScopeValidatedPairs=len(final),nationalDisposition=nd,sourceDisposition=sd,validatedPairsWithRecentHistoricalFault=report["validatedWithRecentHistoricalFault"],
        criterionPatternCount=len(patterns),v5Replay=report,mode="AUDIT_ONLY_NO_PRICE_PROMOTION")
    updated.pop("sqliteSha256",None)
    db.execute("DELETE FROM metadata");db.executemany("INSERT INTO metadata VALUES(?,?)",[(k,dump(v)) for k,v in updated.items()])
    db.commit()
    if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("v5 SQLite integrity")
    if db.execute("SELECT count(*) FROM candidate c LEFT JOIN criterion_pattern p ON p.id=c.pattern_id WHERE p.id IS NULL").fetchone()[0]:raise ValueError("Orphan pattern")
    db.close()
    report["sqliteSha256"]=digest(path)
    (out/"v5-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("G5_V5_REPLAY "+json.dumps({k:v for k,v in report.items() if k not in ("sourcePin","gainedByOperator")},sort_keys=True))
if __name__=="__main__":main()
