#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,zipfile,re
from pathlib import Path

APK=Path("/tmp/enel-apk/enel.apk")
OUT=Path("data/reports/enel_apk_callsite_probe_20260929.json")
TOKENS=("pst/evos/tariff/","pst/evos/v2/tariff/tariff-plan/calendar/","optimization/tariffs/","pst/evos/v1/catalog/penalty")
ROOT=Path("/tmp/enel-apk/unpack")

def run(cmd):
    return subprocess.run(cmd,check=False,text=True,capture_output=True).stdout

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(APK) as z: z.extractall(ROOT)
    files=[p for p in ROOT.rglob("*") if p.is_file() and (p.suffix in (".dex",".so",".json",".js",".xml",".txt") or p.name.startswith("classes"))]
    hits=[]
    for p in files:
        try:
            out=run(["strings","-a","-t","d","-n","4",str(p)])
        except Exception:
            continue
        lines=out.splitlines()
        for i,line in enumerate(lines):
            for t in TOKENS:
                if t in line:
                    lo=max(0,i-30); hi=min(len(lines),i+31)
                    hits.append({"file":str(p.relative_to(ROOT)),"token":t,"line":line,"context":lines[lo:hi]})
    # Search likely HTTP hints in same files containing route tokens.
    http_terms=("GET","POST","PUT","PATCH","DELETE","retrofit","okhttp","RequestBody","Query","Path","Header","Body","tariff","calendar")
    enriched=[]
    byfile={}
    for h in hits: byfile.setdefault(h["file"],[]).append(h)
    for fname,rows in byfile.items():
        p=ROOT/fname
        out=run(["strings","-a","-n","4",str(p)])
        hints=[x for x in out.splitlines() if any(term.lower() in x.lower() for term in http_terms)]
        enriched.append({"file":fname,"routeHits":rows,"httpishHints":hints[:1000]})
    report={"scope":"enel_apk_raw_string_proximity_probe","fileCount":len(files),"hitCount":len(hits),"files":enriched}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:80000])

if __name__=="__main__": main()
