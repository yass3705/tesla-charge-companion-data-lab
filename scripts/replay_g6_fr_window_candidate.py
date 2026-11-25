#!/usr/bin/env python3
"""G6.3d bis: exact baseline and candidate replay from immutable evidence."""
import collections,csv,gzip,json,os,pathlib,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_g6_fr_electroverse import inspect_tariff
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import git_blob,j,dec
from scripts.replay_g6_fr_duration import compile_duration,DIMS
from scripts.replay_g6_fr_time_windows import compile_windows,rules_for

VERSION="g6-fr-electroverse-2026-11-25-window-candidate-v1"
def read_csv(p):
    with gzip.open(p,"rt",encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def load(root,pin,files):
    a=download(root,pin["prior"],{**{key:(name,) for key,name,sha in files},"report":(pin["prior"]["name"].replace("tcc-v9-g6-fr-electroverse-","").replace("-replay","")+"-report.json",)} if False else {**{key:(name,) for key,name,sha in files},"report":(REPORTS[pin["prior"]["name"]],)})
    for key,name,sha in files:verify(a[key],pin[sha])
    report=json.loads(a["report"].read_text())
    if report["codeSha"]!=pin["prior"]["codeSha"] or report["sourcePin"]!=pin["priorSourcePin"] or report["identityPairs"]!=24115 or report["engineSha256"]!=pin["engineSha256"]:raise ValueError("Prior lineage")
    return a,report
REPORTS={
 "tcc-v9-g6-fr-electroverse-time-windows-replay":"g6-time-window-report.json",
 "tcc-v9-g6-fr-electroverse-duration-semantics-replay":"g6-duration-semantics-report.json",
 "tcc-v9-g6-fr-electroverse-duration-replay":"g6-duration-replay-report.json",
 "tcc-v9-g6-fr-electroverse-free-replay":"g6-free-replay-report.json",
 "tcc-v9-g6-fr-electroverse-time-replay":"g6-time-replay-report.json",
 "tcc-v9-g6-fr-electroverse-simple-replay":"g6-simple-replay-report.json"}
def execute(engine,runner,req):
    return json.loads(subprocess.run(["node",str(pathlib.Path(__file__).with_name(runner)),str(engine.resolve())],input=j(req),text=True,capture_output=True,check=True).stdout)
def same_money(r,expected):
    return r["complete"] is True and r.get("currency","EUR")=="EUR" and all(r.get(k) is not None and dec(r[k])==dec(v) for k,v in expected.items())
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g6_fr_window_candidate" or pin["auditVersion"]!=VERSION or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    a,ar=load(root/"window",pin,[("decisions","g6-time-window-offer-decisions.csv.gz","decisionsSha256"),("cases","g6-time-window-cases.csv.gz","casesSha256")])
    if ar["caseCount"]!=684 or ar["passedCases"]!=668 or ar["cumulativeEstimatedOffers"]!=14517 or ar["timeWindowOffers"]!=1367:raise ValueError("Window baseline")
    rows=read_csv(a["decisions"]);groups={}
    for r in rows:
        s=r["tariff_signature"]
        if s in groups and groups[s]["raw_price_payload"]!=r["raw_price_payload"]:raise ValueError("Signature ambiguity")
        groups[s]=r
        if r["raw_verified"].lower()!="true":raise ValueError("Raw verification")
    if len(rows)!=24115 or len({r["national_id"] for r in rows})!=24115 or len({r["source_id"] for r in rows})!=24115 or len(groups)!=262:raise ValueError("Identity")
    raw={s:json.loads(r["raw_price_payload"]) for s,r in groups.items()}
    if any(signature(v)!=s for s,v in raw.items()):raise ValueError("Raw signature")
    baseline=pathlib.Path("migration/v9/g6-reference/pricing-engine.cjs");candidate=pathlib.Path("migration/v9/g6-candidate/pricing-engine.cjs")
    verify(baseline,pin["engineSha256"])
    if git_blob(baseline)!="02b9ec4c2e5e0e6a8258ca45dabb45ff5830672e":raise ValueError("Baseline")
    if digest(candidate)==digest(baseline):raise ValueError("No patch")
    prior=read_csv(a["cases"]);req=[]
    for x in prior:
        s=x["signature"];_,hist,_,windows=compile_windows(raw[s])
        req.append(dict(signature=s,fixture=json.loads(x["session"]),rules=rules_for(hist,windows),expected=json.loads(x["oracle"])))
    runner="replay_g6_fr_time_windows_engine.cjs"
    old=execute(baseline,runner,req);new=execute(candidate,runner,req)
    if len(old["results"])!=684 or len(new["results"])!=684 or old["guards"]!=new["guards"] or not all(new["guards"].values()):raise ValueError("Window guards")
    cases=[];counts=collections.defaultdict(collections.Counter)
    for x,oldr,newr in zip(prior,old["results"],new["results"]):
        if oldr!=json.loads(x["engine_result"]) or any(r["signature"]!=x["signature"] or r["scenario"]!=x["scenario"] for r in (oldr,newr)):raise ValueError("Baseline reproducibility")
        oldpass=x["engine_pass"].lower()=="true";good=same_money(newr,json.loads(x["oracle"]))
        agree=len({j(v) for v in json.loads(x["alternatives"]).values()})==1
        state="ENGINE_MISMATCH" if not good else "CONDITIONAL_ESTIMATE_AGREEMENT" if agree else "INCALCULABLE_SEMANTICS"
        counts[x["signature"]][state]+=1
        cases.append({**x,"candidate_result":j(newr),"candidate_pass":good,"candidate_decision":state,"regression":oldpass and not good})
    if sum(x["regression"] for x in cases) or not all(x["candidate_pass"] for x in cases):raise ValueError("Window candidate not clean")
    # Replay exact prior cases from each signed artifact against both engines.
    regressions=[];p=pin["priorSourcePin"]
    a2,r2=load(root/"semantics",p,[("cases","g6-duration-semantics-cases.csv.gz","casesSha256"),("delayed","g6-duration-delayed-alternatives.csv.gz","delayedSha256")])
    sf={(x["signature"],x["scenario"]):json.loads(x["session"]) for x in read_csv(a2["cases"])}
    dr=read_csv(a2["delayed"]);dq=[dict(signature=x["signature"],scenario=x["scenario"],fixture=sf[(x["signature"],x["scenario"])],component=x["component"],threshold=int(x["threshold_seconds"]),rate=x["rate"],expected=x["expected"]) for x in dr]
    run="replay_g6_fr_duration_semantics_engine.cjs"
    o=execute(baseline,run,dq);n=execute(candidate,run,dq)
    if o!=n or len(dr)!=984 or len(n["results"])!=984 or not n["missingComponentGuard"]:raise ValueError("Delayed regression")
    for x,res in zip(dr,n["results"]):
        if res!=json.loads(x["engine_result"]) or not res["complete"] or dec(res["total"])!=dec(x["expected"]):raise ValueError("Delayed regression oracle")
    regressions.append(dict(phase="duration_delayed",cases=984,passed=984,guards=1))
    p=p["priorSourcePin"]
    for phase,prefix,ncases,run in [
        ("duration","duration",822,"replay_g6_fr_duration_engine.cjs"),
        ("free","free",7,"replay_g6_fr_unrestricted_time_engine.cjs"),
        ("unrestricted_time","time",420,"replay_g6_fr_unrestricted_time_engine.cjs"),
        ("simple","simple",570,"replay_g6_fr_simple_engine.cjs")]:
        aa,rr=load(root/phase,p,[("cases","g6-"+prefix+"-engine-cases.csv.gz","casesSha256")]);cc=read_csv(aa["cases"]);qq=[]
        for x in cc:
            s=x["signature"]
            if phase=="duration":
                rates,bands,_,_=compile_duration(raw[s])
                rates={**{k:str(v) for k,v in rates.items()},"bands":[[DIMS[k],lo,hi,str(v)] for k,lo,hi,v in bands]}
            else:rates=inspect_tariff(raw[s])["base_rates"]
            qq.append(dict(signature=s,fixture=json.loads(x["session"]),rates=rates,expected=json.loads(x["oracle"])))
        o=execute(baseline,run,qq);n=execute(candidate,run,qq)
        if len(cc)!=ncases or len(n["results"])!=ncases or o!=n or not all(n["guards"].values()):raise ValueError("Regression "+phase)
        for x,res in zip(cc,n["results"]):
            if not same_money(res,json.loads(x["oracle"])) or x["engine_pass"].lower()!="true":raise ValueError("Regression oracle "+phase)
        regressions.append(dict(phase=phase,cases=ncases,passed=ncases,guards=len(n["guards"])))
        p=p["priorSourcePin"]
    out=[]
    for r in rows:
        c=counts.get(r["tariff_signature"])
        out.append({**r,"g6_time_window_candidate":"TECHNICAL_PASS_SEMANTICS_REVIEW" if c else "NOT_IN_WINDOW_CANDIDATE_PHASE","g6_time_window_candidate_scenarios":j(dict(c)) if c else ""})
    if sum(r["g6_calculability"]=="ENGINE_ORACLE_PASS_ESTIMATE_ONLY" for r in out)!=14517:raise ValueError("Prior estimates")
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g6-window-candidate-cases.csv.gz",cases,list(cases[0]))
    write_csv(dest/"g6-window-candidate-offer-decisions.csv.gz",out,list(out[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),auditVersion=VERSION,sourcePin=pin,identityPairs=len(out),windowOffers=1367,windowSignatures=len(counts),caseCount=len(cases),baselinePassed=668,candidatePassed=sum(x["candidate_pass"] for x in cases),fixedCases=sum(x["engine_pass"].lower()!="true" and x["candidate_pass"] for x in cases),regressions=regressions,scenarioDecisions=dict(collections.Counter(x["candidate_decision"] for x in cases)),guards=new["guards"],engineSha256=digest(baseline),candidateSha256=digest(candidate),candidateGitBlob=git_blob(candidate),cumulativeEstimatedOffers=14517,identityChanges=0,pricesPromoted=0,supplierCalls=0,automaticPublication=False,limitations=["Candidate only; scan actual UTC minute boundaries for plain clock-window rule selection (max 7 days), preserve session-start selection and leave date/weekday/holiday logic outside this patch","Archived arithmetic regression and prorated conditional models, not contractual confirmation or Production integration"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g6-window-candidate-report.json").write_text(j(report))
    print("G6_FR_WINDOW_CANDIDATE "+j({k:v for k,v in report.items() if k!="sourcePin"}))
if __name__=="__main__":main()
