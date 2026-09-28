#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,zipfile
from pathlib import Path

URL="https://d.apkpure.net/b/APK/com.eflux.ev?version=latest"
TMP=Path("/tmp/eflux-context"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/road"); OUT.mkdir(parents=True,exist_ok=True)
apk=TMP/"app.apk"
subprocess.run([
 "curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","240",
 "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(apk),URL
],check=True)

r=subprocess.run(["strings","-a",str(apk)],capture_output=True,text=True,errors="replace",timeout=180)
lines=r.stdout.splitlines()
needles=["/1/map/locations","/1/map/config","/2/locations/msp/search/fast","tariff_model.dart","rm_tariff_pricing_widget.dart"]
out={}
for n in needles:
    hits=[]
    for i,l in enumerate(lines):
        if n in l:
            block=[]
            for q in lines[max(0,i-25):min(len(lines),i+26)]:
                # strip credential-looking literals, keep method/route/schema context
                if re.search(r'AIza[0-9A-Za-z_-]{20,}|Bearer\s+[A-Za-z0-9._-]{15,}|api[_-]?key\s*[:=]',q,re.I):
                    q="<redacted credential-like string>"
                if len(q)>500:q=q[:500]
                block.append(q)
            hits.append({"index":i,"context":block})
            if len(hits)>=8:break
    out[n]=hits

payload={"country":"BE","asOf":"2026-09-29","scope":"E-Flux app route context","needles":out,
        "policy":{"secretValuesPersisted":False,"publicAppStaticAnalysisOnly":True}}
(OUT/"eflux-app-route-context-2026-09-29.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"hits":{k:len(v) for k,v in out.items()}},indent=2))
