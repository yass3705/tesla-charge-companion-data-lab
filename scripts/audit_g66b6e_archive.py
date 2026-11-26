"""G6.6b-6e: preserve exact source ZIPs and verify restoration without Actions or providers.

No public repository data write, publication or durable external storage claim.
The recovery ZIP must be retained separately on an authorized private location.
"""
import collections,hashlib,json,os,pathlib,re,shutil,sqlite3,stat,subprocess,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
FIELDS=("run","artifact","codeSha","name","zipSha256")
def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()
def verify(p,h):
    if digest(p)!=h:raise ValueError("SHA256 mismatch: "+p.name)
def j(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def put(p,v):p.write_text(j(v)+"\n",encoding="utf-8")
def safe_entries(z):
    seen=set()
    for info in z.infolist():
        pp=pathlib.PurePosixPath(info.filename)
        if pp.is_absolute() or ".." in pp.parts or "\\" in info.filename or stat.S_IFMT(info.external_attr>>16)==stat.S_IFLNK or info.filename in seen:raise ValueError("Unsafe ZIP entry")
        seen.add(info.filename)
    if z.testzip() is not None:raise ValueError("ZIP CRC")
def extract(z,wanted,root):
    root.mkdir(parents=True,exist_ok=True)
    found={}
    for info in z.infolist():
        if info.is_dir():continue
        pp=pathlib.PurePosixPath(info.filename)
        for name,suffix in wanted.items():
            if tuple(pp.parts[-len(suffix):])==suffix:
                if name in found:raise ValueError("Ambiguous entry "+name)
                dest=root/name
                with z.open(info) as src,dest.open("wb") as dst:shutil.copyfileobj(src,dst)
                found[name]=dest
    if set(found)!=set(wanted):raise ValueError("Missing entries "+str(set(wanted)-set(found)))
    return found
def pins_from(pin):
    pins={};refs=collections.defaultdict(set)
    def visit(obj,label):
        if isinstance(obj,dict):
            if all(k in obj for k in FIELDS):
                spec={k:obj[k] for k in FIELDS};i=spec["artifact"]
                if type(i) is not int or type(spec["run"]) is not int or not re.fullmatch(r"[a-f0-9]{40}",spec["codeSha"]) or not re.fullmatch(r"[a-f0-9]{64}",spec["zipSha256"]) or not re.fullmatch(r"[A-Za-z0-9_.:-]+",spec["name"]):raise ValueError("Invalid archive pin")
                if i in pins and pins[i]!=spec:raise ValueError("Conflicting pin "+str(i))
                pins[i]=spec;refs[i].add(label)
            for k,v in obj.items():visit(v,label)
        elif isinstance(obj,list):
            for v in obj:visit(v,label)
    requests={}
    for name in pin["sourceRequests"]:
        if not re.fullmatch(r"[a-z0-9-]+-request\.json",name):raise ValueError("Request path")
        f=ROOT/"migration/v9"/name
        old=subprocess.check_output(["git","show",pin["dataLabParent"]+":migration/v9/"+name])
        if old!=f.read_bytes():raise ValueError("Request drift")
        requests[name]=digest(f);visit(json.loads(old),name)
    visit(pin["finalLocalGate"],"finalLocalGate")
    if not set(pin["requiredRuntimeArtifacts"])<=set(pins):raise ValueError("Missing dependency closure")
    return pins,refs,requests
def api(repo,endpoint):
    return json.loads(subprocess.check_output(["gh","api",f"repos/{repo}/{endpoint}"]))
def filename(i):return str(i)+".zip"
def prepare(pin,root):
    if pin["purpose"]!="offline_g66b6e_verified_recovery_bundle" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation","publicRawArchive")):raise ValueError("Scope")
    if os.environ.get("GITHUB_REPOSITORY")!="yass3705/tesla-charge-companion-data-lab":raise ValueError("Repository")
    root.mkdir();src=root/"originals";src.mkdir();out=root/"results";out.mkdir()
    pins,refs,requests=pins_from(pin);repo=os.environ["GITHUB_REPOSITORY"]
    entries=[]
    for i,spec in sorted(pins.items()):
        run=api(repo,f"actions/runs/{spec['run']}")
        art=api(repo,f"actions/artifacts/{i}")
        if (run["status"]!="completed" or run["conclusion"]!="success" or run["head_sha"]!=spec["codeSha"] or run["head_branch"]!="rebuild/v9-20261020" or art["expired"] or art["name"]!=spec["name"] or art["digest"]!="sha256:"+spec["zipSha256"] or art["workflow_run"]["id"]!=spec["run"]):raise ValueError("Source provenance: "+str(i))
        p=src/filename(i)
        with p.open("wb") as f:subprocess.run(["gh","api",f"repos/{repo}/actions/artifacts/{i}/zip"],stdout=f,check=True,timeout=300)
        verify(p,spec["zipSha256"])
        if p.stat().st_size!=art["size_in_bytes"]:raise ValueError("ZIP size")
        with zipfile.ZipFile(p) as z:
            safe_entries(z)
            count=sum(not x.is_dir() for x in z.infolist())
        entries.append({**spec,"file":"originals/"+filename(i),"bytes":p.stat().st_size,"members":count,"originalExpiresAt":art["expires_at"],"referencedBy":sorted(refs[i])})
        print("G66B6E verified artifact",i,spec["name"],p.stat().st_size,flush=True)
    manifest={"schemaVersion":1,"codeSha":os.environ["GITHUB_SHA"],"dataLabParent":pin["dataLabParent"],"productionSha":pin["productionSha"],"baselineProductionSha":pin["baselineProductionSha"],"sourceRequestsSha256":requests,"artifacts":entries,"privateRetentionRequired":True,"supplierCalls":0,"publicRawArchive":False,"scope":"FR Electroverse G6 archive lineage and G5 consolidated ledger/evidence parents; not all earlier collection history"}
    put(root/"manifest.json",manifest)
    archive=out/"TCC_V9_Electroverse_FR_proofs_2026-11-26.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        z.write(root/"manifest.json","manifest.json")
        for e in entries:z.write(root/e["file"],e["file"])
    restored=restore(archive,root/"restored")
    # Prove the existing gate can replay from restored bytes without any
    # Actions download; the prior compiler and engine remain unchanged.
    replay_report=replay(pin,restored,root/"replay")
    report={"codeSha":os.environ["GITHUB_SHA"],"sourcePin":pin,"archiveFile":archive.name,"archiveSha256":digest(archive),"archiveBytes":archive.stat().st_size,"manifestSha256":digest(root/"manifest.json"),"verifiedArtifacts":len(entries),"sourceBytes":sum(x["bytes"] for x in entries),"artifacts":[{k:e[k] for k in ("artifact","run","codeSha","name","zipSha256","bytes","members","originalExpiresAt")} for e in entries],"restoration":replay_report,"supplierCalls":0,"identityChanges":0,"pricesPromoted":0,"published":False,"runtimeActivated":False,"durableExternalCopyVerified":False,"status":"RECOVERY_BUNDLE_VERIFIED_PENDING_PRIVATE_RETENTION"}
    put(out/"g66b6e-report.json",report);print("G66B6E "+j(report))
def restore(archive,root):
    root.mkdir()
    with zipfile.ZipFile(archive) as z:
        safe_entries(z)
        manifest=json.loads(z.read("manifest.json"))
        if manifest["schemaVersion"]!=1 or not manifest["privateRetentionRequired"] or manifest["publicRawArchive"] or manifest["supplierCalls"]:raise ValueError("Manifest scope")
        entries=manifest["artifacts"];ids={x["artifact"] for x in entries}
        if len(ids)!=len(entries):raise ValueError("Duplicate artifact")
        wanted={"manifest.json",*(x["file"] for x in entries)}
        if set(z.namelist())!=wanted:raise ValueError("Archive inventory")
        for e in entries:
            if e["file"]!="originals/"+filename(e["artifact"]):raise ValueError("Restore path")
            p=root/filename(e["artifact"])
            with z.open(e["file"]) as inp,p.open("wb") as out:shutil.copyfileobj(inp,out)
            verify(p,e["zipSha256"])
            if p.stat().st_size!=e["bytes"]:raise ValueError("Restore size")
            with zipfile.ZipFile(p) as nested:
                safe_entries(nested)
                if sum(not x.is_dir() for x in nested.infolist())!=e["members"]:raise ValueError("Restore members")
    put(root/"manifest.json",manifest)
    return root
def replay(pin,restored,work):
    import scripts.audit_irve_g5_power_scope as helper
    manifest=json.loads((restored/"manifest.json").read_text())
    indexed={e["artifact"]:e for e in manifest["artifacts"]}
    downloads=[]
    def local_download(root,spec,wanted):
        e=indexed.get(spec["artifact"])
        if not e or any(spec[k]!=e[k] for k in FIELDS):raise ValueError("Local pin mismatch")
        zpath=restored/filename(spec["artifact"]);verify(zpath,spec["zipSha256"])
        downloads.append(spec["artifact"])
        with zipfile.ZipFile(zpath) as z:return extract(z,wanted,root)
    work.mkdir()
    # Read full original decision database, including rejected candidates and
    # criterion evidence, rather than preserve just counters or samples.
    spec=indexed[pin["identityLedgerArtifact"]]
    ledger=local_download(work/"ledger",spec,{"db.sqlite":("g5-matching-v6.sqlite",),"report.json":("v6-consolidation-report.json",)})
    lr=json.loads(ledger["report.json"].read_text());verify(ledger["db.sqlite"],lr["sqliteSha256"])
    db=sqlite3.connect(ledger["db.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":raise ValueError("SQLite integrity")
        candidates=db.execute("SELECT count(*) FROM v6_candidate_effective").fetchone()[0]
        matched=db.execute("SELECT count(*) FROM v6_identity_matches").fetchone()[0]
        reviewed=db.execute("SELECT count(*) FROM v6_decisions").fetchone()[0]
        if (candidates,matched,reviewed)!=(581978,24115,9983):raise ValueError("G5 ledger coverage")
        accepted=db.execute("SELECT national_id,source_id FROM v6_identity_matches ORDER BY national_id LIMIT 1").fetchone()
        rejected=db.execute("SELECT national_id,source_id FROM v6_candidate_effective WHERE effective_identity_decision!='MATCH_VALIDATED' ORDER BY national_id,source_id LIMIT 1").fetchone()
        for row in (accepted,rejected):
            if not row:raise ValueError("Missing diagnostic sample")
            result=db.execute("SELECT c.effective_identity_decision,p.criteria,c.first_blocker,c.v6_reasons,c.v6_evidence_json FROM v6_candidate_effective c JOIN criterion_pattern p ON p.id=c.pattern_id WHERE c.national_id=? AND c.source_id=?",row).fetchone()
            if not result or not result[1]:raise ValueError("Missing criteria")
    finally:db.close()
    prior=local_download(work/"final",pin["finalLocalGate"],{**{k:(k,) for k in pin["finalExports"]},"report":("g66b6d-local-gate-report.json",)})
    for k,h in pin["finalExports"].items():verify(prior[k],h)
    final=json.loads(prior["report"].read_text())
    if final["codeSha"]!=pin["finalLocalGate"]["codeSha"] or final["priorRequestsVerified"]!=1047 or final["httpRequests"]!=12 or final["novelPricedRequests"]!=2 or final["supplierCalls"] or final["published"] or final["runtimeActivated"] or final["exportSha256"]!=pin["finalExports"]:raise ValueError("Final proof")
    # Patch only archive loading at the test boundary, before importing
    # any consumers. The original replay script and pricing logic are intact.
    helper.download=local_download
    from scripts import audit_g66b6c_bump_complement as complement
    if complement.download is not local_download:raise ValueError("Offline loader not bound")
    oldpin=ROOT/"migration/v9/g66b6c-bump-complement-request.json"
    oldargs=sys.argv[:];saved={k:os.environ.pop(k) for k in ("GH_TOKEN","GITHUB_TOKEN") if k in os.environ}
    try:
        sys.argv=[str(ROOT/"scripts/audit_g66b6c_bump_complement.py"),str(oldpin),str(work/"complement")]
        complement.main()
    finally:sys.argv=oldargs;os.environ.update(saved)
    r=json.loads((work/"complement/results/g66b6c-bump-report.json").read_text())
    localpin=json.loads((ROOT/"migration/v9/g66b6d-local-gate-request.json").read_text())
    for k,h in localpin["exports"].items():verify(work/"complement/results"/k,h)
    if r["checks"]!=1047 or r["previous6cRegressions"] or r["tripleLaneValidation"]!="PASS" or r["runtime"]["mixed"]["threePricedConnectors"]!=10:raise ValueError("Offline replay")
    return {"zipAndCrcVerified":True,"decisionDatabaseIntegrity":"PASS","candidates":candidates,"matchedIdentities":matched,"v6Reviewed":reviewed,"acceptedAndRejectedLookup":"PASS","priorLocalBrowserEvidence":"PASS","offlineReplayRequests":1047,"offlineReplayRegressions":0,"offlineArtifactReads":len(downloads),"uniqueOfflineArtifacts":len(set(downloads)),"tripleConnectors":10,"productionService":False,"fullShell":False}
def main():
    if len(sys.argv)!=4:raise SystemExit("prepare <request.json> <workdir> | restore <archive.zip> <workdir>")
    mode,source,target=sys.argv[1:];root=pathlib.Path(target).resolve()
    if root==ROOT or ROOT in root.parents:raise ValueError("Workdir must be outside Git")
    if mode=="prepare":prepare(json.loads(pathlib.Path(source).read_text()),root)
    elif mode=="restore":
        restore(pathlib.Path(source),root);print("Verified exact source ZIPs and manifest; no network")
    else:raise ValueError("Mode")
if __name__=="__main__":main()
