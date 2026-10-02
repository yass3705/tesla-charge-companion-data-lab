import json, os, subprocess, pathlib, re, sys
body=os.environ["REQUEST_BODY"]
m=re.search(r"\x60\x60\x60json\s*(\{.*?\})\s*\x60\x60\x60",body,re.S)
if not m: raise SystemExit("missing JSON payload")
req=json.loads(m.group(1))
required={"expectedLedger","ledgerPath","ledger","counts"}
if not required.issubset(req): raise SystemExit("missing required keys")
if not re.fullmatch(r"docs/germany-cpo-second-pass-resolution-\d+\.json",req["ledgerPath"]): raise SystemExit("invalid ledgerPath")
progress_path=pathlib.Path("docs/germany-cpo-progress-2026-09.json")
progress=json.loads(progress_path.read_text())
if progress.get("resolutionLedger") != req["expectedLedger"]:
    raise SystemExit(f"concurrent advance: expected {req['expectedLedger']} got {progress.get('resolutionLedger')}")
if pathlib.Path(req["ledgerPath"]).exists(): raise SystemExit("ledger already exists")
c=req["counts"]
if c["totalNamedCpos"] != 591 or c["complete"]+c["partial"]+c["blocked"] != 591: raise SystemExit("invalid counts")
ledger=req["ledger"]
after=ledger.get("canonicalAfter",{})
for k in ("totalNamedCpos","complete","partial","blocked"):
    if after.get(k) != c[k]: raise SystemExit(f"ledger/count mismatch: {k}")
pathlib.Path(req["ledgerPath"]).write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+"\n")
progress.update({"updatedAt":req.get("updatedAt"),"resolutionLedger":req["ledgerPath"],"totalNamedCpos":c["totalNamedCpos"],"complete":c["complete"],"partial":c["partial"],"blocked":c["blocked"]})
progress_path.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+"\n")
subprocess.run(["git","config","user.name","github-actions[bot]"],check=True)
subprocess.run(["git","config","user.email","41898282+github-actions[bot]@users.noreply.github.com"],check=True)
subprocess.run(["git","add",req["ledgerPath"],str(progress_path)],check=True)
subprocess.run(["git","commit","-m",f"docs(de): persist {pathlib.Path(req['ledgerPath']).stem}"],check=True)
subprocess.run(["git","push","origin","HEAD:main"],check=True)
issue=os.environ["ISSUE_NUMBER"]
subprocess.run(["gh","issue","comment",issue,"--body",f"Persisted {req['ledgerPath']} and advanced Germany canonical progress."],check=True)
subprocess.run(["gh","issue","close",issue],check=True)
