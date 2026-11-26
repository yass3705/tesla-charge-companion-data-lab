"""G6.6a: isolated Production-module boundary proof; no hosted deployment."""
import collections,hashlib,json,os,pathlib,sqlite3,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest,write_csv
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import j,dec
from scripts.evaluate_g6_fr_dynamic import prepare,historical_rules,fixtures
from scripts.refine_g6_fr_dynamic import FAMILIES
from scripts.consolidate_g6_fr_scenarios import read_csv,EST,REVIEW
from scripts.unify_g6_fr_dynamic import load,diagnose,engine_agrees,extra_fixtures,PASS
from scripts.audit_g6_fr_segment_rounding import segment_oracle,explain,ROUNDING
def blob(path):
    b=path.read_bytes();return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def identity_join(db,rows):
    pairs=[dict(x) for x in db.execute("""SELECT m.national_id,m.source_id,m.identity_rule,m.tariff_state,n.station_id,n.evse_id,n.plug AS national_plug,n.kw AS national_kw,n.mode AS national_mode
    FROM v6_identity_matches m JOIN national_connector n ON n.id=m.national_id ORDER BY m.national_id""")]
    key=lambda r:(str(r["national_id"]),str(r["source_id"]))
    index={key(r):r for r in pairs}
    if len(index)!=len(pairs) or len(index)!=len(rows) or {key(r) for r in rows}!=index.keys():raise ValueError("IRVE identity pair mismatch")
    out=[]
    for r in rows:
        v=index[key(r)]
        if any(str(v[k])!=r[k] for k in ("identity_rule","tariff_state","station_id","evse_id","national_plug","national_mode")) or dec(v["national_kw"])!=dec(r["national_kw"]):raise ValueError("IRVE field mismatch")
        out.append({k:r[k] for k in ("national_id","source_id","station_id","evse_id","national_plug","national_kw","national_mode","tariff_signature","g6_calculability")})
    return out
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66_runtime_boundary" or any(pin[k] is not False for k in ("supplierCalls","identityChanges","automaticPublication")):raise ValueError("Scope")
    a,ar=load(root/"rounding",pin["rounding"],pin["roundingExports"],pin["roundingReportSha256"],"g6-rounding-report.json")
    b,br=load(root/"refined",pin["refined"],pin["refinedExports"],pin["refinedReportSha256"],"g6-refined-report.json")
    if ar["explainedCases"]!=5 or ar["explainedOffers"]!=135 or ar["priorAgreementRegressions"]!=0:raise ValueError("Rounding scope")
    l=download(root/"ledger",pin["ledger"],{"db":("g5-matching-v6.sqlite",),"report":("v6-consolidation-report.json",)})
    verify(l["db"],pin["sqliteSha256"]);lr=json.loads(l["report"].read_text())
    if lr["codeSha"]!=pin["ledger"]["codeSha"] or lr["sqliteSha256"]!=pin["sqliteSha256"] or lr["validatedIdentityPairs"]!=24115 or lr["pricesPromoted"]!=0:raise ValueError("Ledger lineage")
    rows=read_csv(b["g6-refined-offers.csv.gz"]);db=sqlite3.connect(l["db"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row
    projected=identity_join(db,rows)
    total_national=db.execute("SELECT count(*) FROM national_connector").fetchone()[0]
    db.close();verify(l["db"],pin["sqliteSha256"])
    if len(projected)!=24115 or len({r["national_id"] for r in projected})!=24115 or len({r["source_id"] for r in projected})!=24115 or collections.Counter(r["g6_calculability"] for r in projected)!={EST:14517,REVIEW:9598}:raise ValueError("Projection")
    groups=collections.defaultdict(list)
    for r in rows:groups[r["tariff_signature"]].append(r)
    if len(groups)!=262:raise ValueError("Signatures")
    fxs=[f for f in list(fixtures())+list(extra_fixtures()) if f["id"] in ("short","overnight_partial")]
    c,p=2117,437
    fxs.append(dict(id="ui_new_mixed",startAt="2026-11-25T18:21:13Z",seconds=c+p,chargeSeconds=c,parkSeconds=p,energy="24.789",duration=str(dec(c+p)/60),charging=str(dec(c)/60),parking=str(dec(p)/60)))
    old={(r["signature"],r["scenario"]):r for r in read_csv(a["g6-rounding-signature-scenarios.csv.gz"])}
    if len(old)!=3144:raise ValueError("Historical cases")
    requests=[];quote_rows=[];indices=[]
    for sig,rr in sorted(groups.items()):
        r=rr[0];raw=json.loads(r["raw_price_payload"]);family=r["family"];baseline=r["g6_calculability"]==EST
        if signature(raw)!=sig or any(x["raw_verified"]!="True" or x["raw_price_payload"]!=r["raw_price_payload"] or x["family"]!=family or x["g6_calculability"]!=r["g6_calculability"] for x in rr):raise ValueError("Raw lineage")
        prepared=prepare(raw,family,baseline,sig)
        for f in fxs:
            state,parts,reason=diagnose(prepared,f,family,baseline)
            q=dict(signature=sig,scenario=f["id"],decision=state,reason=state if parts is None else "",estimate_eur="",oracle=j(parts) if parts else "",candidate="",segment_oracle="",publication_eligible=False)
            if parts is not None:
                try:rules=historical_rules(prepared,f,family)
                except (ValueError,KeyError,TypeError,ArithmeticError) as ex:q["decision"]="HISTORICAL_ENGINE_STRUCTURE_REVIEW";q["reason"]=str(ex)
                else:requests.append(dict(signature=sig,fixture=f,rules=rules));indices.append(len(quote_rows))
            quote_rows.append(q)
    engine=pathlib.Path("migration/v9/g6-candidate/pricing-engine.cjs");verify(engine,pin["candidateSha256"])
    runner=pathlib.Path(__file__).with_name("replay_g6_fr_combined_windows_engine.cjs")
    result=json.loads(subprocess.run(["node",str(runner),str(engine.resolve())],input=j(requests),text=True,capture_output=True,check=True).stdout)
    if len(result["results"])!=len(requests) or len(result["guards"])!=4 or not all(result["guards"].values()):raise ValueError("Candidate guards")
    for i,req,r in zip(indices,requests,result["results"]):
        q=quote_rows[i];parts=json.loads(q["oracle"]);q["candidate"]=j(r)
        if r["signature"]!=q["signature"] or r["scenario"]!=q["scenario"]:raise ValueError("Order")
        if engine_agrees(parts,r):q["decision"]=PASS;q["estimate_eur"]=parts["total"]
        else:
            q["decision"]="ENGINE_OR_ROUNDING_REVIEW";q["reason"]=q["decision"]
            if groups[q["signature"]][0]["family"] in FAMILIES:
                try:seg,_=segment_oracle(req["rules"],req["fixture"])
                except (ValueError,KeyError,TypeError,ArithmeticError):pass
                else:
                    q["segment_oracle"]=j(seg)
                    if explain(parts,seg,r):q["decision"]=ROUNDING;q["estimate_eur"]=seg["total"];q["reason"]=""
    regressions=[]
    for q in quote_rows:
        o=old.get((q["signature"],q["scenario"]))
        if o and (o["g65b_decision"]!=q["decision"] or o["g65b_estimate_eur"]!=q["estimate_eur"]):regressions.append(dict(signature=q["signature"],scenario=q["scenario"],old=o["g65b_decision"],new=q["decision"]))
    if regressions:raise ValueError("Runtime quote regression "+str(regressions[:5]))
    ref=pathlib.Path("migration/v9/g66-runtime-reference")
    if any(blob(ref/name)!=spec["sha"] for name,spec in pin["runtime"]["blobs"].items()):raise ValueError("Production module pin")
    payload=dict(projection=projected,fixtures=fxs,quotes=quote_rows,productionCommit=pin["runtime"]["commit"])
    payload_path=root/"input.json";payload_path.write_text(j(payload))
    run=subprocess.run(["node",str(pathlib.Path(__file__).with_name("test_g66_runtime_boundary.cjs")),str(ref.resolve()),str(payload_path.resolve())],capture_output=True,text=True)
    if run.returncode:raise RuntimeError("Runtime boundary: "+run.stderr[-4000:])
    runtime=json.loads(run.stdout)
    if runtime["identityPairs"]!=24115 or runtime["runtimeOfferChecks"]!=24115*len(fxs) or not all(runtime["guards"].values()):raise ValueError("Runtime boundary failure")
    dest=root/"results";dest.mkdir()
    write_csv(dest/"g66-runtime-identity-projection.csv.gz",projected,list(projected[0]))
    write_csv(dest/"g66-runtime-quotes.csv.gz",quote_rows,list(quote_rows[0]))
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,identityPairs=len(projected),nationalConnectorInventory=total_national,matchedStations=len({r["station_id"] for r in projected}),signatures=len(groups),baselineEstimations=14517,reviewOffers=9598,quoteRegressions=len(regressions),quoteCases=len(quote_rows),candidateComparisons=len(requests),runtime=runtime,identityChanges=0,supplierCalls=0,pricesPromoted=0,automaticPublication=False,limitations=["Actual pinned Production session/offer/pricing/bridge modules exercised in Node with isolated diagnostic hook, not browser or hosted preview","IRVE projection uses immutable G5 ledger, not fresh national acquisition or station crosswalk runtime audit","Direct/Electra and other-country control offers synthetic only; no live tariffs claimed","Python batch quote bound to exact effective session; runtime transport and browser integration remain separate","Zero-power identities retained but excluded from price ranking in this diagnostic"])
    report["exportSha256"]={p.name:digest(p) for p in dest.glob("*.csv.gz")}
    (dest/"g66-runtime-report.json").write_text(j(report))
    print("G66_RUNTIME_BOUNDARY "+j({k:v for k,v in report.items() if k!="sourcePin"}))
if __name__=="__main__":main()
