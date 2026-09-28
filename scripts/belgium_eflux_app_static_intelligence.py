#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,zipfile,hashlib
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.eflux.ev?version=latest"
TMP=Path("/tmp/eflux-apk"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/road"); OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"app.xapk"
subprocess.run([
 "curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","240",
 "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(xapk),URL
],check=True)

xr=TMP/"x"; xr.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z:z.extractall(xr)
apks=list(xr.rglob("*.apk"))
if not apks: raise SystemExit("no APK found")
base=next((p for p in apks if p.name.lower() in ("base.apk","com.eflux.ev.apk")),max(apks,key=lambda p:p.stat().st_size))

# strings is enough for endpoint/contract discovery without persisting secrets.
r=subprocess.run(["strings","-a",str(base)],capture_output=True,text=True,errors="replace",timeout=180)
txt=r.stdout
urls=sorted(set(re.findall(r'https?://[^\s"\'<>]{5,250}',txt)))
# sanitize query tokens and credential-looking material
safe_urls=[]
for u in urls:
    if any(k in u.lower() for k in ("token=","apikey=","api_key=","signature=","secret=")):
        continue
    safe_urls.append(u)
safe_urls=safe_urls[:500]

markers=[]
for pat in [
  "tariff","price","pricing","chargepoint","charge_point","location","connector",
  "guest","anonymous","scan2pay","scan-to-pay","payment","map","api","ocpi"
]:
    if pat.lower() in txt.lower(): markers.append(pat)

# collect only short context around non-secret route-ish strings
routes=sorted(set(re.findall(r'/(?:v\d+/)?[A-Za-z0-9_./{}-]{3,120}',txt)))
routes=[x for x in routes if any(k in x.lower() for k in ("location","charge","tariff","price","connector","map","payment"))][:500]

hosts=[]
for u in safe_urls:
    m=re.match(r'https?://([^/]+)',u)
    if m: hosts.append(m.group(1))
host_counts={}
for h in hosts:host_counts[h]=host_counts.get(h,0)+1

out={
 "package":"com.eflux.ev",
 "source":"APKPure latest public package",
 "baseApk":{"name":base.name,"bytes":base.stat().st_size,"sha256":hashlib.sha256(base.read_bytes()).hexdigest()},
 "markers":markers,
 "hostCounts":dict(sorted(host_counts.items(),key=lambda kv:(-kv[1],kv[0]))),
 "urls":safe_urls,
 "routeCandidates":routes,
 "policy":{"secretValuesPersisted":False,"readOnly":True,"publicAppStaticAnalysisOnly":True}
}
(OUT/"eflux-app-static-intelligence-2026-09-29.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"baseApk":out["baseApk"],"markers":markers,"hostCounts":out["hostCounts"],"routeCandidates":routes[:80]},ensure_ascii=False,indent=2))
