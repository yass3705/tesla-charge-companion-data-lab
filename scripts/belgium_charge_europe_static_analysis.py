#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,zipfile,shutil
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.total.europe?version=latest"
TMP=Path("/tmp/charge-europe"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"charge-europe.xapk"

p=subprocess.run([
 "curl","-LsS","--retry","3","--connect-timeout","15","--max-time","180",
 "-A","Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
 "-H","Referer: https://apkpure.net/","-o",str(xapk),URL
],capture_output=True,text=True)
if not xapk.exists() or xapk.stat().st_size<1_000_000:
    raise RuntimeError("XAPK download failed: "+p.stderr[-1200:])

root=TMP/"x"; root.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z: z.extractall(root)
apks=list(root.rglob("*.apk"))
strings=[]
for i,apk in enumerate(apks):
    ar=TMP/f"a{i}"; ar.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(apk) as z: z.extractall(ar)
    except Exception: continue
    for fp in ar.rglob("*"):
        if not fp.is_file() or fp.stat().st_size>150_000_000: continue
        try:
            r=subprocess.run(["strings","-n","5",str(fp)],capture_output=True,text=True,errors="replace",timeout=35)
            strings.extend(r.stdout.splitlines())
        except Exception: pass

needles=("api","tariff","price","pricing","paygo","chargepoint","charge-point","station","connector","evse","spot2charge","total-ev-charge","ocpi","adhoc","ad-hoc","payment")
rows=[]
for l in strings:
    s=l.strip()
    if not s or len(s)>700: continue
    low=s.lower()
    if not any(n in low for n in needles): continue
    score=0
    if "http" in low: score+=8
    if "/api/" in low or "/v1/" in low or "/v2/" in low or "/v3/" in low: score+=5
    if any(n in low for n in ("tariff","price","pricing","paygo","adhoc","ad-hoc")): score+=5
    if any(n in low for n in ("connector","evse","chargepoint","charge-point")): score+=3
    if score>=5: rows.append((score,s))

seen=set(); clean=[]
for sc,s in sorted(rows,key=lambda x:(-x[0],x[1])):
    if s in seen: continue
    seen.add(s)
    # redact likely opaque tokens but keep URLs/routes/class names
    s=re.sub(r'(?i)(authorization|access_token|refresh_token|client_secret|api[_-]?key)([=: ]+)([^\s"\']+)',r'\1\2[REDACTED]',s)
    clean.append({"score":sc,"value":s})

urls=sorted(set(x["value"] for x in clean if "http" in x["value"].lower()))
report={
 "package":"com.total.europe","source":"APKPure latest",
 "downloadBytes":xapk.stat().st_size,"apkCount":len(apks),
 "routeCandidates":clean[:4000],"urls":urls[:1500],
 "notes":["Static read-only analysis. APK/XAPK not persisted in repository.","Credential-looking literals are redacted."]
}
(OUT/"charge-europe-static-analysis-2026-09-28.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"downloadBytes":report["downloadBytes"],"apkCount":len(apks),"top":clean[:300]},ensure_ascii=False,indent=2))
