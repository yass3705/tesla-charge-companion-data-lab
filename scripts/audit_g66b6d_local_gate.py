"""Isolated localhost HTTP test of the existing dynamic gate, not a production service."""
import json,os,pathlib,subprocess,sys,threading,collections,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from scripts.audit_irve_g5_power_scope import download,verify,digest,gzjson
from scripts.consolidate_g6_fr_scenarios import read_csv
from scripts.g66b3_quote_gate import QuoteGate
from scripts.g66b5e_dynamic_gate import DynamicPlannerGate
from scripts.replay_g6_fr_simple import j
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b6d_live_local_gate_recipe" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")):raise ValueError("Scope")
    a=download(root/"browser",pin["browser"],{**{k:(k,) for k in pin["browserExports"]},"report":("g66b6d-report.json",)})
    for k,v in pin["browserExports"].items():verify(a[k],v)
    prior=json.loads(a["report"].read_text())
    if prior["codeSha"]!=pin["browser"]["codeSha"] or prior["priorRequestsVerified"]!=1047 or prior["supplierCalls"] or prior["published"] or prior["runtimeActivated"] or prior["sourcePin"]!=json.loads((ROOT/"migration/v9/g66b6d-browser-request.json").read_text()) or prior["exportSha256"]!=pin["browserExports"]:raise ValueError("Browser evidence")
    oldpin=ROOT/"migration/v9/g66b6c-bump-complement-request.json";replay=root/"replay"
    subprocess.run([sys.executable,"-m","scripts.audit_g66b6c_bump_complement",str(oldpin),str(replay)],check=True,timeout=1800)
    for k,v in pin["exports"].items():verify(replay/"results"/k,v)
    comp=json.loads((replay/"results/g66b6c-bump-report.json").read_text())
    if comp["checks"]!=1047 or comp["tripleLaneValidation"]!="PASS":raise ValueError("Complement")
    dynpin=json.loads((ROOT/"migration/v9/g66b5e-dynamic-zero-request.json").read_text())
    clockpin=json.loads((ROOT/"migration/v9/g66b5b-clock-planner-request.json").read_text())
    canonical=gzjson(replay/"alignment/g66b2-national-active-canonical.json.gz")
    crosswalk=gzjson(replay/"alignment/g66b2-november-crosswalk.json.gz")
    legacy_report=json.loads((replay/"legacy/report").read_text())
    # Input bytes have already been verified during the intact complement replay.
    legacy=QuoteGate(read_csv(replay/"refined/g6-refined-offers.csv.gz"),crosswalk,canonical,dynpin["candidateSha256"],legacy_report["lineage"])
    if len(legacy.bound)!=24102 or len(legacy.registry)!=262:raise ValueError("Registry coverage")
    gate=DynamicPlannerGate(legacy,comp["lineage"])
    ledger=[];lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_args):pass
        def respond(self,status,payload,kind="application/json"):
            self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Cache-Control","no-store");self.send_header("X-Robots-Tag","noindex, nofollow");self.send_header("Content-Length",str(len(payload)));self.end_headers();self.wfile.write(payload)
        def do_GET(self):
            if self.path!="/":return self.respond(404,b"{}")
            self.respond(200,b'<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><style>body{margin:0;padding:12px;background:#101820;color:#eee;font:16px system-ui}main{max-width:760px;margin:auto}.box{box-sizing:border-box;padding:12px;border:1px solid #34404c;border-radius:8px}.small{font-size:13px;overflow-wrap:anywhere}</style><main><div id="results"></div></main></html>',"text/html; charset=utf-8")
        def do_POST(self):
            if self.path!="/quote":return self.respond(404,b"{}")
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=262144:return self.respond(400,b"{}")
                req=json.loads(self.rfile.read(size))
                with lock:
                    start=time.monotonic();answers,n=gate.quote([req])
                    if len(answers)!=1:raise ValueError("Quote count")
                    answer=answers[0]
                    if answer.get("diagnosticOnly") is not True or answer.get("publicationEligible") is not False:raise ValueError("Promotion")
                    ledger.append(dict(request=req,response=answer,candidateComparisons=n,elapsedMs=round((time.monotonic()-start)*1000,1)))
                self.respond(200,j(answer).encode())
            except Exception as ex:
                print("LOCAL_GATE_ERROR",repr(ex),flush=True);self.respond(500,b"{}")
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    out=root/"results";out.mkdir()
    try:
        subprocess.run(["node","--max-old-space-size=6144",str(ROOT/"scripts/test_g66b6d_local_gate.cjs"),str(ROOT/"production"),str(replay/"input.json"),str(replay/"responses.json"),str(out),f"http://127.0.0.1:{server.server_port}"],check=True,timeout=900)
    finally:
        server.shutdown();server.server_close()
    report=json.loads((out/"local-browser.json").read_text())
    if len(ledger)!=report["httpRequests"] or not ledger:raise ValueError("HTTP evidence")
    old={j(x["request"]):x["response"] for x in json.loads((replay/"responses.json").read_text())}
    prior_rows=[x for x in ledger if j(x["request"]) in old]
    if not prior_rows or any(old[j(x["request"])]!=x["response"] for x in prior_rows):raise ValueError("Prior response regression")
    novel=[x for x in ledger if j(x["request"]) not in old]
    if not any(x["response"].get("estimateEur") is not None for x in novel):raise ValueError("Novel real quote required")
    (out/"http-ledger.json").write_text(j(ledger))
    report.update(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,priorRequestsVerified=1047,previousBrowserArtifactVerified=True,knownHttpRequests=len(prior_rows),novelHttpRequests=len(novel),novelPricedRequests=sum(x["response"].get("estimateEur") is not None for x in novel),candidateComparisons=sum(x["candidateComparisons"] for x in ledger),supplierCalls=0,pricesPromoted=0,published=False,runtimeActivated=False)
    report["exportSha256"]={p.name:digest(p) for p in out.iterdir()}
    (out/"g66b6d-local-gate-report.json").write_text(j(report));print("G66B6D_LOCAL_GATE "+j(report))
if __name__=="__main__":main()
