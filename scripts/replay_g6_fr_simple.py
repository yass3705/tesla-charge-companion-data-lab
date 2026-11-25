#!/usr/bin/env python3
"""G6.2 independent Decimal oracle against exact pinned Production engine."""
import collections,csv,gzip,hashlib,json,os,pathlib,subprocess,sys
from decimal import Decimal,ROUND_HALF_UP
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature

VERSION="g6-fr-electroverse-2026-11-25-simple-replay-v1"
SIMPLE="SIMPLE_ENERGY_FLAT_ORACLE_CANDIDATE"
Q=Decimal("0.000001")
def j(v):return json.dumps(v,ensure_ascii=False,sort_keys=True)
def dec(s):return Decimal(str(s))
def git_blob(path):
    b=path.read_bytes()
    return hashlib.sha1(("blob "+str(len(b))+"\0").encode()+b).hexdigest()
def oracle(rates,energy):
    e=(dec(rates["energy"])*dec(energy)).quantize(Q,rounding=ROUND_HALF_UP)
    f=dec(rates["flat"]).quantize(Q,rounding=ROUND_HALF_UP)
    return dict(energy=str(e),flat=str(f),total=str(e+f))
def fixtures():
    return [
        dict(id="fraction_1Wh",energy="0.001",duration=1,charging=1,parking=0,startAt="2026-11-25T10:00:00Z"),
        dict(id="fraction_1_005kWh",energy="1.005",duration=20,charging=15,parking=5,startAt="2026-11-25T10:00:00Z"),
        dict(id="10kWh",energy="10",duration=60,charging=60,parking=0,startAt="2026-11-25T10:00:00Z"),
        dict(id="fraction_23_456kWh_midnight",energy="23.456",duration=90,charging=75,parking=15,startAt="2026-11-25T22:45:00Z"),
        dict(id="50kWh_spring_dst",energy="50",duration=120,charging=100,parking=20,startAt="2026-03-29T00:30:00Z"),
        dict(id="80kWh_autumn_dst",energy="80",duration=240,charging=210,parking=30,startAt="2026-10-25T00:30:00Z"),
    ]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_simple_engine_replay" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","identityChanges")):raise ValueError("Scope")
    a=download(root/"audit",pin["audit"],{"audit.csv.gz":("g6-tariff-audit.csv.gz",),"report.json":("g6-tariff-audit-report.json",)})
    verify(a["audit.csv.gz"],pin["auditCsvSha256"])
    ar=json.loads(a["report.json"].read_text())
    if ar["codeSha"]!=pin["audit"]["codeSha"] or ar["sourcePin"]!=pin["auditSourcePin"] or ar["identityPairs"]!=24115 or ar["rawVerified"]!=24115 or ar["uniqueRawSignatures"]!=262 or ar["auditStatuses"]!={SIMPLE:8876,"REVIEW_REQUIRED":15239} or ar["exportSha256"]["g6-tariff-audit.csv.gz"]!=pin["auditCsvSha256"] or ar["certifiedCalculable"]!=0:raise ValueError("Audit lineage")
    with gzip.open(a["audit.csv.gz"],"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115:raise ValueError("Identity coverage")
    groups=collections.defaultdict(list)
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262:raise ValueError("Signature count")
    simple={}
    for sig,rr in groups.items():
        if len({r["audit_status"] for r in rr})!=1 or len({r["raw_price_payload"] for r in rr})!=1:raise ValueError("Signature ambiguity")
        raw=json.loads(rr[0]["raw_price_payload"])
        if signature(raw)!=sig or any(r["raw_verified"].lower()!="true" for r in rr):raise ValueError("Raw evidence")
        if rr[0]["audit_status"]!=SIMPLE:continue
        d=inspect_tariff(raw)
        if d["audit_status"]!=SIMPLE or d["reasons"] or any(json.loads(r["base_rates"])!=d["base_rates"] or json.loads(r["reasons"]) or dec(r["fixture_10kwh_eur_unrounded"])!=dec(d["fixture_10kwh_eur_unrounded"]) for r in rr):raise ValueError("Simple gate did not reproduce")
        rates=d["base_rates"]
        if set(rates)!={"energy","flat","time","parking","vat"} or any(dec(rates[k])!=0 for k in ("time","parking","vat")) or dec(rates["energy"])<0 or dec(rates["flat"])<0 or dec(rates["energy"])+dec(rates["flat"])<=0:raise ValueError("Simple rate scope")
        simple[sig]=rates
    if len(simple)!=95 or sum(len(groups[k]) for k in simple)!=8876:raise ValueError("Simple cohort")
    requests=[dict(signature=sig,fixture=f,expected=oracle(rates,f["energy"]),rates=rates) for sig,rates in sorted(simple.items()) for f in fixtures()]
    engine=pathlib.Path(pin["engine"]["auditPath"])
    if git_blob(engine)!=pin["engine"]["gitBlob"]:raise ValueError("Engine bytes mismatch")
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_simple_engine.cjs")
    evaluated=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(evaluated["results"])!=len(requests) or set(evaluated["guards"])!={"missing_energy","negative_energy","unknown_fee","wrong_currency"} or not all(evaluated["guards"].values()):raise ValueError("Engine guard or coverage")
    cases=[];failed=set()
    for x,r in zip(requests,evaluated["results"]):
        if r["signature"]!=x["signature"] or r["scenario"]!=x["fixture"]["id"]:raise ValueError("Result ordering")
        try:good=r["complete"] is True and r["currency"]=="EUR" and all(dec(r[k])==dec(x["expected"][k]) for k in ("total","energy","flat"))
        except (ValueError,ArithmeticError):good=False
        if not good:failed.add(x["signature"])
        cases.append(dict(signature=x["signature"],scenario=x["fixture"]["id"],session=j(x["fixture"]),oracle=j(x["expected"]),engine_result=j(r),engine_pass=good))
    out=[]
    for row in rows:
        sig=row["tariff_signature"]
        status="SIMPLE_ENGINE_ORACLE_PASS" if sig in simple and sig not in failed else "SIMPLE_ENGINE_ORACLE_REVIEW" if sig in failed else "NOT_IN_SIMPLE_PHASE"
        out.append({**row,"g6_simple_replay":status,"g6_calculability":"ENGINE_ORACLE_PASS_ESTIMATE_ONLY" if status=="SIMPLE_ENGINE_ORACLE_PASS" else row["g6_calculability"]})
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-simple-engine-cases.csv.gz",cases,list(cases[0]))
    write_csv(dest/"g6-simple-offer-decisions.csv.gz",out,list(out[0]))
    counts=collections.Counter(x["g6_simple_replay"] for x in out)
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),simpleSignatures=len(simple),simpleOffers=8876,scenariosPerSignature=len(fixtures()),caseCount=len(cases),passedCases=sum(x["engine_pass"] for x in cases),passedSignatures=len(simple)-len(failed),failedSignatures=sorted(failed),offerDecisions=dict(counts),guards=evaluated["guards"],engineSha256=digest(engine),supplierCalls=0,pricesPromoted=0,identityChanges=0,automaticPublication=False,limitations=["Strict simple arithmetic estimates against unmodified Production engine; invoice rounding not proved","runtime-owned is a symlink to runtime-overrides, not a second engine","Other 15,239 offers unchanged; G6 global not passed","Engine snapshot is test-only, not serving runtime"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-simple-replay-report.json").write_text(j(report))
    print("G6_FR_SIMPLE_REPLAY "+j({k:v for k,v in report.items() if k!="sourcePin"}))
if __name__=="__main__":main()
