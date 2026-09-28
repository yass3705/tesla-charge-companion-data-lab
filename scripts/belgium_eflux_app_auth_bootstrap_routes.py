#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess
from pathlib import Path

URL="https://d.apkpure.net/b/APK/com.eflux.ev?version=latest"
TMP=Path("/tmp/eflux-authroutes"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/road"); OUT.mkdir(parents=True,exist_ok=True)
apk=TMP/"app.apk"
subprocess.run([
 "curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","240",
 "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(apk),URL
],check=True)
r=subprocess.run(["strings","-a",str(apk)],capture_output=True,text=True,errors="replace",timeout=180)
lines=r.stdout.splitlines()
terms=("anonymous","guest","auth","token","jwt","session","login","signin","sign-in","register","map/locations","locations/msp")
hits=[]
for i,l in enumerate(lines):
    ll=l.lower()
    if any(t in ll for t in terms):
        if len(l)>300: continue
        # keep only route/header/model-ish strings; avoid credential values
        if not ("/" in l or ":" in l or "get:" in l or "set:" in l or "package:road_mobile" in l or "authorization" in ll or "jwt" in ll):
            continue
        if re.search(r'Bearer\s+[A-Za-z0-9._-]{15,}|AIza[0-9A-Za-z_-]{20,}',l,re.I):
            l="<redacted credential-like string>"
        hits.append({"index":i,"value":l})
        if len(hits)>=800:break
payload={"country":"BE","asOf":"2026-09-29","scope":"E-Flux auth/bootstrap route discovery","hits":hits,
        "policy":{"secretValuesPersisted":False,"publicAppStaticAnalysisOnly":True}}
(OUT/"eflux-app-auth-bootstrap-routes-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"hitCount":len(hits),"sample":hits[:120]},ensure_ascii=False,indent=2))
