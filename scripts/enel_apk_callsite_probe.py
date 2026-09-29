#!/usr/bin/env python3
from __future__ import annotations
import json,re,zipfile
from pathlib import Path
from androguard.misc import AnalyzeAPK

APK=Path("/tmp/enel-apk/enel.apk")
OUT=Path("data/reports/enel_apk_callsite_probe_20260929.json")
TOKENS=("pst/evos/tariff/","pst/evos/v2/tariff/tariff-plan/calendar/","optimization/tariffs/","pst/evos/v1/catalog/penalty")

def ins_text(m):
    try:
        code=m.get_code()
        if not code: return []
        bc=code.get_bc()
        return [f"{i.get_name()} {i.get_output()}" for i in bc.get_instructions()]
    except Exception:
        return []

def main():
    a,ds,dx=AnalyzeAPK(str(APK))
    rows=[]
    for d in ds:
        for c in d.get_classes():
            for m in c.get_methods():
                ins=ins_text(m)
                blob="\n".join(ins)
                hit=[t for t in TOKENS if t in blob]
                if not hit: continue
                # Keep only bounded instruction windows around each hit.
                windows=[]
                for idx,line in enumerate(ins):
                    if any(t in line for t in TOKENS):
                        lo=max(0,idx-25); hi=min(len(ins),idx+40)
                        windows.append(ins[lo:hi])
                rows.append({
                    "class":c.get_name(),
                    "method":m.get_name(),
                    "descriptor":m.get_descriptor(),
                    "hits":hit,
                    "windows":windows,
                })
    # Also surface nearby Retrofit/HTTP annotation strings and parameter hints from all methods.
    httpish=[]
    keys=("GET","POST","PUT","DELETE","PATCH","@Body","@Query","@Path","@Header","retrofit2/http","okhttp3","RequestBody")
    for d in ds:
        for c in d.get_classes():
            for m in c.get_methods():
                ins=ins_text(m)
                blob="\n".join(ins)
                if any(t in blob for t in TOKENS) or any(k in blob for k in keys):
                    if any(t in blob for t in TOKENS):
                        httpish.append({"class":c.get_name(),"method":m.get_name(),"lines":[x for x in ins if any(k in x for k in keys)][:120]})
    report={"scope":"enel_apk_dex_callsite_probe","tokenCallsites":rows,"httpContext":httpish[:200]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:60000])

if __name__=="__main__": main()
