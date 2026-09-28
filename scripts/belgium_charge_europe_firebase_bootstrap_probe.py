#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,zipfile,urllib.request,urllib.error,hashlib,os
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.total.europe?version=latest"
TMP=Path("/tmp/ce-firebase"); TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"app.xapk"
subprocess.run([
 "curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","180",
 "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(xapk),URL
],check=True)

xr=TMP/"x"; xr.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z: z.extractall(xr)

# Find likely base APK and inspect Android resources using aapt if available.
apks=list(xr.rglob("*.apk"))
if not apks: raise SystemExit("no APK in XAPK")
base=max(apks,key=lambda p:p.stat().st_size)

def aapt_values(apk):
    vals={}
    try:
        r=subprocess.run(["aapt","dump","resources",str(apk)],capture_output=True,text=True,errors="replace",timeout=120,check=False)
        txt=r.stdout
        wanted=("google_app_id","google_api_key","project_id","gcm_defaultSenderId","firebase_database_url")
        for w in wanted:
            # capture the following raw string value line
            pos=txt.find(f"resource 0x")
        # robust line scanner: when spec resource ...:string/name appears, inspect next ~12 lines for Raw:
        lines=txt.splitlines()
        for i,l in enumerate(lines):
            m=re.search(r":string/([A-Za-z0-9_.-]+):",l)
            if not m: continue
            name=m.group(1)
            if name not in wanted: continue
            for q in lines[i:i+16]:
                mm=re.search(r'Raw:\s+"(.*)"',q)
                if mm:
                    vals[name]=mm.group(1); break
    except Exception:
        pass
    return vals

vals=aapt_values(base)
# Fallback to printable strings around well-known resource names.
if not vals:
    raw=base.read_bytes()
    txt=raw.decode("latin1","ignore")
    # We do not try to persist any credential values; only collect transiently.
    for name in ("google_app_id","google_api_key","project_id"):
        p=txt.find(name)
        if p>=0:
            chunk=txt[max(0,p-5000):p+5000]
            # candidate patterns
            if name=="google_app_id":
                m=re.search(r'1:\d+:android:[0-9a-f]{16,}',chunk)
            elif name=="google_api_key":
                m=re.search(r'AIza[0-9A-Za-z_-]{30,}',chunk)
            else:
                m=re.search(r'[a-z][a-z0-9-]{5,}\d[a-z0-9-]*',chunk)
            if m: vals[name]=m.group(0)

app_id=vals.get("google_app_id")
api_key=vals.get("google_api_key")
project_id=vals.get("project_id")

def post_json(url,headers,payload):
    data=json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,headers=headers,method="POST")
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            body=r.read().decode("utf-8","replace")
            try: obj=json.loads(body)
            except Exception: obj={"raw":body[:20000]}
            return r.status,obj
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        try: obj=json.loads(body)
        except Exception: obj={"raw":body[:20000]}
        return e.code,obj
    except Exception as e:
        return 0,{"error":type(e).__name__+": "+str(e)}

install_status=None; install_schema=None; rc_status=None; rc_keys=[]; interesting={}
auth_token=None
if app_id and api_key and project_id:
    fis_url=f"https://firebaseinstallations.googleapis.com/v1/projects/{project_id}/installations"
    fid="c"+hashlib.sha256((app_id+"tcc").encode()).hexdigest()[:21]
    install_status,inst=post_json(fis_url,{
      "Content-Type":"application/json",
      "Accept":"application/json",
      "x-goog-api-key":api_key,
    },{
      "fid":fid,
      "appId":app_id,
      "authVersion":"FIS_v2",
      "sdkVersion":"a:17.2.0",
    })
    if isinstance(inst,dict):
        install_schema={"keys":sorted(inst.keys())}
        auth=(inst.get("authToken") or {})
        auth_token=auth.get("token")
    if auth_token:
        rc_url=f"https://firebaseremoteconfig.googleapis.com/v1/projects/{project_id}/namespaces/firebase:fetch"
        rc_status,rc=post_json(rc_url,{
          "Content-Type":"application/json",
          "Accept":"application/json",
          "x-goog-api-key":api_key,
          "x-goog-firebase-installations-auth":auth_token,
        },{
          "appId":app_id,
          "appInstanceId":fid,
          "appInstanceIdToken":auth_token,
          "languageCode":"en-US",
          "countryCode":"BE",
          "platformVersion":"Android",
          "packageName":"com.total.europe",
          "sdkVersion":"21.6.0",
        })
        if isinstance(rc,dict):
            entries=rc.get("entries") or {}
            if isinstance(entries,dict):
                rc_keys=sorted(entries.keys())
                for k,v in entries.items():
                    lk=k.lower()
                    if any(x in lk for x in ("api","key","url","base","endpoint","evdc","marketplace","infra","environment")):
                        # Never persist secret-looking values; record only key name and value shape/hash.
                        sv=str(v)
                        interesting[k]={
                          "length":len(sv),
                          "sha256":hashlib.sha256(sv.encode()).hexdigest()[:16],
                          "looksUrl":sv.startswith("http"),
                          "looksOpaque":bool(re.fullmatch(r"[A-Za-z0-9._~+/=-]{20,}",sv)),
                        }

out={
 "purpose":"Use the public Charge Europe client Firebase bootstrap flow to inspect Remote Config metadata relevant to EVDC initialization.",
 "resourcePresence":{
   "googleAppId":bool(app_id),"googleApiKey":bool(api_key),"projectId":bool(project_id)
 },
 "installationStatus":install_status,
 "installationResponseSchema":install_schema,
 "remoteConfigStatus":rc_status,
 "remoteConfigKeyCount":len(rc_keys),
 "remoteConfigKeys":rc_keys,
 "interestingEntryMetadata":interesting,
 "policy":{
   "firebaseCredentialValuesPersisted":False,
   "installationTokenPersisted":False,
   "remoteConfigValuesPersisted":False,
   "readOnly":True,
   "publicClientFlowOnly":True
 }
}
(OUT/"charge-europe-firebase-bootstrap-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k:out[k] for k in ("resourcePresence","installationStatus","remoteConfigStatus","remoteConfigKeyCount","remoteConfigKeys","interestingEntryMetadata")},ensure_ascii=False,indent=2))
