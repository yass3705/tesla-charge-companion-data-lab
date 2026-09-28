#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,subprocess,zipfile,urllib.request,urllib.parse,urllib.error
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.total.europe?version=latest"
BASE="https://prod.apix.alzp.tgscloud.net/evdc-bff-europe/v0.0.1"
TMP=Path("/tmp/charge-europe-keyprobe"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"app.xapk"

subprocess.run([
 "curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","180",
 "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(xapk),URL
],check=True)
xr=TMP/"x"; xr.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z: z.extractall(xr)

files=[]
for idx,apk in enumerate(xr.rglob("*.apk")):
    ar=TMP/f"a{idx}"; ar.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(apk) as z: z.extractall(ar)
    except Exception:
        continue
    for p in ar.rglob("*"):
        if p.is_file() and (p.name=="libapp.so" or p.name=="libflutter.so" or p.suffix==".dex"):
            files.append(p)

all_lines=[]
for fp in files:
    try:
        r=subprocess.run(["strings","-n","4",str(fp)],capture_output=True,text=True,errors="replace",timeout=120)
        all_lines.extend(r.stdout.splitlines())
    except Exception:
        pass

# Collect opaque-looking literals near API/header markers. Never persist candidate values.
marker_idx=[i for i,l in enumerate(all_lines) if any(n in l.lower() for n in (
    "x-apif-apikey","evdc-bff-europe","prod.apix.alzp.tgscloud.net","x-user-account-id"
))]
cand=[]
seen=set()
for i in marker_idx:
    for l in all_lines[max(0,i-80):min(len(all_lines),i+81)]:
        s=l.strip()
        if s in seen: continue
        seen.add(s)
        if not (16 <= len(s) <= 180): continue
        if "http://" in s or "https://" in s: continue
        if any(x in s.lower() for x in ("x-apif-apikey","authorization","bearer","evdc-bff","prod.apix","content-type","user-agent","x-user-account-id")): continue
        # likely API-key-ish: high alnum content, limited punctuation, no spaces
        if " " in s or "\t" in s: continue
        if not re.fullmatch(r"[A-Za-z0-9._~+/=-]+",s): continue
        alnum=sum(ch.isalnum() for ch in s)
        if alnum/len(s) < .80: continue
        cand.append(s)

# Prefer longer opaque candidates, but cap attempts.
cand=sorted(cand,key=lambda s:(-len(s),s))[:120]

def request_with(key):
    params={"countryCode":"BE","pageNumber":"0","pageSize":"1"}
    url=BASE+"/v3/infrastructure/locations?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={
      "Accept":"application/json",
      "User-Agent":"TotalEnergies-Charge-Europe-research/1.0",
      "x-apif-apikey":key,
    })
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            body=r.read().decode("utf-8","replace")
            return r.status,body
    except urllib.error.HTTPError as e:
        return e.code,e.read().decode("utf-8","replace")
    except Exception as e:
        return 0,type(e).__name__+": "+str(e)

attempts=[]; valid=None; valid_body=None
for idx,key in enumerate(cand):
    status,body=request_with(key)
    marker="valid-or-different" if status not in (401,403) or "API Key provided is not valid" not in body else "invalid-key"
    attempts.append({
      "index":idx,
      "sha256":hashlib.sha256(key.encode()).hexdigest()[:16],
      "length":len(key),
      "status":status,
      "result":marker,
    })
    if marker=="valid-or-different":
        valid=key; valid_body=body; break

parsed=None
if valid_body:
    try: parsed=json.loads(valid_body)
    except Exception: parsed={"raw":valid_body[:30000]}

def schema_summary(obj):
    if isinstance(obj,dict):
        return {"type":"object","keys":sorted(obj.keys()),"dataType":type(obj.get("data")).__name__ if "data" in obj else None}
    if isinstance(obj,list):
        return {"type":"list","count":len(obj),"firstKeys":sorted(obj[0].keys()) if obj and isinstance(obj[0],dict) else []}
    return {"type":type(obj).__name__}

out={
 "purpose":"Transiently test embedded Charge Europe application API-key candidates without persisting any credential.",
 "candidateCount":len(cand),
 "attempts":attempts,
 "validCandidateFound":valid is not None,
 "validCandidateSha256":hashlib.sha256(valid.encode()).hexdigest()[:16] if valid else None,
 "responseStatus":next((a["status"] for a in attempts if a["result"]=="valid-or-different"),None),
 "responseSchema":schema_summary(parsed) if parsed is not None else None,
 "response":parsed,
 "safety":{"apiKeyPersisted":False,"xapkPersisted":False,"readOnly":True},
}
(OUT/"charge-europe-transient-apikey-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:out[k] for k in ("candidateCount","validCandidateFound","validCandidateSha256","responseStatus","responseSchema")},ensure_ascii=False,indent=2))
