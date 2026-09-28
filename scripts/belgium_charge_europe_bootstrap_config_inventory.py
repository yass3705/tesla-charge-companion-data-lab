#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,subprocess,zipfile
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.total.europe?version=latest"
TMP=Path("/tmp/charge-europe-bootstrap"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"app.xapk"

subprocess.run([
 "curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","180",
 "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(xapk),URL
],check=True)
xr=TMP/"x"; xr.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z:z.extractall(xr)

interesting=[]
for idx,apk in enumerate(xr.rglob("*.apk")):
    ar=TMP/f"a{idx}"; ar.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(apk) as z:z.extractall(ar)
    except Exception:
        continue
    for fp in ar.rglob("*"):
        if not fp.is_file(): continue
        rel=str(fp.relative_to(ar))
        lowrel=rel.lower()
        if not any(k in lowrel for k in (
          "asset","config","environment","firebase","remote","setting","flavor","manifest","resource"
        )):
            continue
        if fp.stat().st_size>5_000_000: continue
        try: raw=fp.read_bytes()
        except Exception: continue
        txt=raw.decode("utf-8","replace")
        low=txt.lower()
        markers=[m for m in (
          "x-apif-apikey","evdc-bff-europe","remote_config","remoteconfig",
          "firebase","api_key","apikey","baseurl","base_url","environment",
          "marketplace-evp","infrastructure/locations","prod.apix"
        ) if m in low]
        if not markers: continue
        snippets=[]
        for m in markers:
            pos=0
            while True:
                i=low.find(m,pos)
                if i<0: break
                s=txt[max(0,i-800):min(len(txt),i+1800)]
                # Preserve config key names/URLs, redact long opaque values and explicit assignments.
                s=re.sub(r'(?i)((?:api[_-]?key|apikey|client[_-]?secret|access[_-]?token|authorization)\s*["\']?\s*[:=]\s*["\'])([^"\']+)',r'\1[REDACTED]',s)
                s=re.sub(r'(?<![A-Za-z0-9])([A-Za-z0-9_-]{48,})(?![A-Za-z0-9])','[REDACTED_LONG]',s)
                snippets.append(s)
                pos=i+len(m)
                if len(snippets)>=20: break
        interesting.append({
          "apkIndex":idx,"file":rel,"size":fp.stat().st_size,"markers":markers,
          "sha256":hashlib.sha256(raw).hexdigest(),"snippets":snippets[:20]
        })

out={
 "package":"com.total.europe",
 "purpose":"Inventory embedded bootstrap/config assets relevant to Charge Europe API initialization.",
 "interestingFiles":interesting,
 "policy":{"xapkPersisted":False,"credentialValuesPersisted":False,"readOnly":True}
}
(OUT/"charge-europe-bootstrap-config-inventory-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"fileCount":len(interesting),"files":[{"file":x["file"],"markers":x["markers"]} for x in interesting[:100]]},ensure_ascii=False,indent=2))
