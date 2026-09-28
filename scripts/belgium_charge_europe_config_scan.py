#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,zipfile
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.total.europe?version=latest"
TMP=Path("/tmp/charge-europe-config"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"app.xapk"
subprocess.run(["curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","180",
 "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(xapk),URL],check=True)
xr=TMP/"x";xr.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z:z.extractall(xr)

hits=[]
names=[]
patterns=("prod.apix","evdc-bff","api_key","apikey","api-key","subscription-key","ocp-apim","x-api-key","client_id","clientid","environment","baseurl","base_url")
for idx,apk in enumerate(xr.rglob("*.apk")):
    ar=TMP/f"a{idx}";ar.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(apk) as z:z.extractall(ar)
    except: continue
    for fp in ar.rglob("*"):
        if not fp.is_file(): continue
        rel=str(fp.relative_to(ar)); names.append(rel)
        if fp.stat().st_size>8_000_000: continue
        try: raw=fp.read_bytes()
        except: continue
        # text-ish and embedded readable strings
        text=raw.decode("utf-8","replace")
        low=text.lower()
        if not any(p in low for p in patterns): continue
        snippets=[]
        for p in patterns:
            start=0
            while True:
                i=low.find(p,start)
                if i<0: break
                s=text[max(0,i-500):min(len(text),i+1400)]
                # redact likely key/token assignments, but preserve header names and URLs
                s=re.sub(r'(?i)((?:api[_-]?key|apikey|subscription[_-]?key|client[_-]?secret|access[_-]?token|authorization)\s*["\']?\s*[:=]\s*["\'])([^"\']+)',r'\1[REDACTED]',s)
                snippets.append(s)
                start=i+len(p)
                if len(snippets)>=80: break
            if len(snippets)>=80: break
        hits.append({"file":rel,"size":fp.stat().st_size,"snippets":snippets})

# filenames likely config
configNames=[n for n in sorted(set(names)) if any(x in n.lower() for x in ("config","env","setting","flavor","firebase","manifest","assetmanifest"))]
out={"package":"com.total.europe","hits":hits,"configLikeFiles":configNames[:1500],
 "notes":["Values matching credential-like assignments are redacted in persisted report.","No binary is persisted."]}
(OUT/"charge-europe-config-scan-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"hitFiles":[{"file":h["file"],"size":h["size"],"snippetCount":len(h["snippets"])} for h in hits],"configLikeFiles":configNames[:300]},ensure_ascii=False,indent=2))
