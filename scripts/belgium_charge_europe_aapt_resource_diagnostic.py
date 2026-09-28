#!/usr/bin/env python3
import json,re,subprocess,zipfile,hashlib
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.total.europe?version=latest"
TMP=Path("/tmp/ce-aapt-diag"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"app.xapk"
subprocess.run([
 "curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","180",
 "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(xapk),URL
],check=True)
xr=TMP/"x"; xr.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z:z.extractall(xr)
apks=list(xr.rglob("*.apk"))
base=next((p for p in apks if p.name.lower() in ("com.total.europe.apk","base.apk")),apks[0])
wanted=("google_app_id","google_api_key","project_id","gcm_defaultSenderId")
r=subprocess.run(["aapt","dump","--values","resources",str(base)],capture_output=True,text=True,errors="replace",timeout=180,check=False)
lines=r.stdout.splitlines()

def sanitize(s):
    # preserve structure while redacting literal values
    def repl(m):
        v=m.group(1)
        return '"<redacted len=%d sha256=%s>"' % (len(v),hashlib.sha256(v.encode()).hexdigest()[:16])
    s=re.sub(r'"([^"]*)"',repl,s)
    s=re.sub(r'(AIza[0-9A-Za-z_-]{20,})',lambda m:'<redacted-google-key len=%d>'%len(m.group(1)),s)
    s=re.sub(r'(1:\d+:android:[0-9a-f]+)',lambda m:'<redacted-app-id len=%d>'%len(m.group(1)),s)
    return s[:2000]

blocks={}
for name in wanted:
    idx=next((i for i,l in enumerate(lines) if f":string/{name}" in l),None)
    if idx is None:
        blocks[name]={"found":False}
    else:
        raw=lines[max(0,idx-2):min(len(lines),idx+45)]
        blocks[name]={"found":True,"lineIndex":idx,"lines":[sanitize(x) for x in raw]}

out={"baseApk":base.name,"blocks":blocks,"policy":{"literalValuesPersisted":False,"readOnly":True}}
(OUT/"charge-europe-aapt-resource-diagnostic-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"baseApk":base.name,"found":{k:v["found"] for k,v in blocks.items()}},indent=2))
