#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,zipfile,shutil
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.totalenergies.chargeplus?nc=arm64-v8a&sv=26&versionCode=2026072815"
TMP=Path("/tmp/chargeplus-routes"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"chargeplus.xapk"

p=subprocess.run([
 "curl","-LsS","--retry","3","--connect-timeout","15","--max-time","180",
 "-A","Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
 "-H","Referer: https://apkpure.net/","-o",str(xapk),URL
],capture_output=True,text=True)
if not xapk.exists() or xapk.stat().st_size<1_000_000:
    raise RuntimeError("XAPK download failed: "+p.stderr[-1200:])

xr=TMP/"x"; xr.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z: z.extractall(xr)
base=next((p for p in xr.rglob("com.totalenergies.chargeplus.apk")),None)
if not base: base=next(xr.rglob("*.apk"))
ar=TMP/"a"; ar.mkdir(exist_ok=True)
with zipfile.ZipFile(base) as z: z.extractall(ar)

lines=[]
for fp in ar.rglob("*"):
    if not fp.is_file() or fp.stat().st_size>120_000_000: continue
    if fp.suffix not in (".dex",".so",".xml",".json","") and "resources" not in fp.name: continue
    try:
        r=subprocess.run(["strings","-n","4",str(fp)],capture_output=True,text=True,errors="replace",timeout=45)
        lines.extend(r.stdout.splitlines())
    except Exception:
        pass

needles=("poi","pois","price","pricing","tariff","atlas","guest","public_base_url","private_base_url")
cand=[]
for line in lines:
    l=line.strip()
    low=l.lower()
    if not any(n in low for n in needles): continue
    if len(l)>600: continue
    # Prioritize route-like, Retrofit-like, model/api-client and base URL strings.
    score=0
    if l.startswith("/") or "/v1/" in low or "/v2/" in low or "/v3/" in low: score+=6
    if "http" in low: score+=5
    if "api" in low: score+=3
    if "poiprices" in low or "pricing" in low or "tariff" in low: score+=5
    if "atlaspoi" in low: score+=4
    if "guest" in low: score+=2
    if score>=4:
        cand.append((score,l))

seen=set(); rows=[]
for score,l in sorted(cand,key=lambda x:(-x[0],x[1])):
    if l in seen: continue
    seen.add(l)
    # redact credential-looking literals if any
    safe=re.sub(r'(?i)(api[_-]?key|client_secret|access_token|authorization)([=: ]+)(\S+)',r'\1\2[REDACTED]',l)
    rows.append({"score":score,"value":safe})

# Capture adjacency around key API client names in global string order.
contexts=[]
for i,l in enumerate(lines):
    low=l.lower()
    if any(k in low for k in ("atlaspoiapiclient","atlaspoipricesapiclient","public_base_url","private_base_url")):
        contexts.append({"hit":l,"before":lines[max(0,i-20):i],"after":lines[i+1:i+31]})

out={"package":"com.totalenergies.chargeplus","version":"2.17.0","routeCandidates":rows[:2500],"apiClientContexts":contexts[:300]}
(OUT/"chargeplus-route-contract-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"candidateCount":len(rows),"top":rows[:250],"contexts":contexts[:30]},ensure_ascii=False,indent=2))
