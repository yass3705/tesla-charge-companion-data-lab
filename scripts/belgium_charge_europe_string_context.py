#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,zipfile,re
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.total.europe?version=latest"
TMP=Path("/tmp/charge-europe-context"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"app.xapk"

subprocess.run([
 "curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","180",
 "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(xapk),URL
],check=True)

xr=TMP/"x"; xr.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z:z.extractall(xr)
base=next((p for p in xr.rglob("com.total.europe.apk")),None)
if not base: base=next(xr.rglob("*.apk"))
ar=TMP/"a"; ar.mkdir(exist_ok=True)
with zipfile.ZipFile(base) as z:z.extractall(ar)

files=[]
for p in ar.rglob("*"):
    if p.is_file() and (p.name=="libapp.so" or p.suffix==".so" or p.suffix==".dex"):
        files.append(p)

needles=[
 "evdc-bff-europe","EvsePriceGridViewModelBase","dynamicPriceDescriptions","priceDescriptions",
 "localDynamicPriceModel","LocalProductPrice","PAYGO_ANONYMOUS","connector","evse","chargepoint",
 "chargePoint","tariff","pricing","products","poi","station","locations","map/search","search"
]
contexts=[]
routeish=set()
for fp in files:
    try:
        r=subprocess.run(["strings","-n","3",str(fp)],capture_output=True,text=True,errors="replace",timeout=90)
    except Exception:
        continue
    lines=r.stdout.splitlines()
    for i,line in enumerate(lines):
        low=line.lower()
        if any(n.lower() in low for n in needles):
            lo=max(0,i-14); hi=min(len(lines),i+20)
            block=lines[lo:hi]
            contexts.append({"file":str(fp.relative_to(ar)),"hit":line,"before":block[:i-lo],"after":block[i-lo+1:]})
        s=line.strip()
        if len(s)<=300 and (
            s.startswith("/") or re.search(r'\b(?:v[0-9]+|api)/[A-Za-z0-9_?&=/{}/.-]+',s)
            or any(k in low for k in ("price","tariff","connector","evse","chargepoint","paygo"))
        ):
            if "/" in s or "Price" in s or "price" in s or "tariff" in low:
                routeish.add(s)

# Redact very long opaque tokens, preserving URLs and readable routes.
def safe(s):
    if "http://" in s or "https://" in s: return s
    return re.sub(r'(?<![A-Za-z0-9])([A-Za-z0-9_-]{64,})(?![A-Za-z0-9])','[REDACTED_LONG_LITERAL]',s)

for c in contexts:
    c["hit"]=safe(c["hit"])
    c["before"]=[safe(x) for x in c["before"]]
    c["after"]=[safe(x) for x in c["after"]]

out={
 "package":"com.total.europe","contextCount":len(contexts),
 "contexts":contexts[:2200],
 "routeishStrings":[safe(x) for x in sorted(routeish)][:5000],
 "notes":["Strings adjacency analysis only; binaries not persisted."]
}
(OUT/"charge-europe-string-context-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"contextCount":len(contexts),"routeishCount":len(routeish),"sample":out["routeishStrings"][:500]},ensure_ascii=False,indent=2))
