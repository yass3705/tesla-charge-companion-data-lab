"""G6.6b-6d component browser recipe on pinned real archive; no publication."""
import json,os,pathlib,subprocess,sys
from scripts.audit_irve_g5_power_scope import download,verify,digest
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b6d_browser_component_recipe" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    a=download(root/"previous",pin["complement"],{**{k:(k,) for k in pin["exports"]},"report":("g66b6c-bump-report.json",)})
    for k,v in pin["exports"].items():verify(a[k],v)
    prev=json.loads(a["report"].read_text())
    oldpin=ROOT/"migration/v9/g66b6c-bump-complement-request.json"
    if prev["codeSha"]!=pin["complement"]["codeSha"] or prev["sourcePin"]!=json.loads(oldpin.read_text()) or prev["tripleLaneValidation"]!="PASS" or prev["checks"]!=1047 or prev["previous6cRegressions"] or prev["published"] or prev["runtimeActivated"] or prev["supplierCalls"]:raise ValueError("Prior proof")
    replay=root/"replay"
    subprocess.run([sys.executable,"-m","scripts.audit_g66b6c_bump_complement",str(oldpin),str(replay)],check=True,timeout=1800)
    current=json.loads((replay/"results/g66b6c-bump-report.json").read_text())
    for k,v in pin["exports"].items():verify(replay/"results"/k,v)
    for k in ("runtime","checks","previous6cExactMatches","previous6cRegressions","bumpArchive","tripleLaneValidation"):
        if current[k]!=prev[k]:raise ValueError("Previous complement differs: "+k)
    out=root/"results";out.mkdir()
    subprocess.run(["node","--max-old-space-size=6144",str(ROOT/"scripts/test_g66b6d_browser.cjs"),str(ROOT/"production"),str(replay/"input.json"),str(replay/"responses.json"),str(out)],check=True,timeout=900)
    report=json.loads((out/"browser-observations.json").read_text())
    report.update(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,priorRequestsVerified=1047,previousArchiveDigest=digest(a["report"]),productionSha=pin["productionSha"],supplierCalls=0,pricesPromoted=0,published=False,runtimeActivated=False)
    report["exportSha256"]={p.name:digest(p) for p in out.iterdir()}
    (out/"g66b6d-report.json").write_text(json.dumps(report,sort_keys=True,ensure_ascii=False)+"\n")
    print("G66B6D "+json.dumps(report,sort_keys=True,ensure_ascii=False))
if __name__=="__main__":main()
