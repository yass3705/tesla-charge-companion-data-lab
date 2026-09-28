#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,zipfile,urllib.request,urllib.error,hashlib
from pathlib import Path

URL="https://d.apkpure.net/b/XAPK/com.total.europe?version=latest"
TMP=Path("/tmp/ce-firebase-v2")
TMP.mkdir(parents=True,exist_ok=True)
OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True,exist_ok=True)
xapk=TMP/"app.xapk"

subprocess.run([
    "curl","-fLsS","--retry","3","--connect-timeout","15","--max-time","180",
    "-A","Mozilla/5.0","-H","Referer: https://apkpure.net/","-o",str(xapk),URL
],check=True)

xr=TMP/"x"
xr.mkdir(exist_ok=True)
with zipfile.ZipFile(xapk) as z:
    z.extractall(xr)

apks=list(xr.rglob("*.apk"))
if not apks:
    raise SystemExit("no APK in XAPK")

def is_base_apk(p):
    name=p.name.lower()
    return name in ("base.apk","com.total.europe.apk") or ("base" in name and "config." not in name)

base=next((p for p in apks if is_base_apk(p)), apks[0])
wanted=("google_app_id","google_api_key","project_id","gcm_defaultSenderId","firebase_database_url")

def aapt_values(apk):
    vals={}
    debug={}
    cmds=[
        ["aapt","dump","--values","resources",str(apk)],
        ["aapt","dump","resources",str(apk)],
    ]
    for cmd in cmds:
        r=subprocess.run(cmd,capture_output=True,text=True,errors="replace",timeout=180,check=False)
        lines=r.stdout.splitlines()
        for i,l in enumerate(lines):
            for name in wanted:
                if f":string/{name}" not in l:
                    continue
                val=None
                for q in lines[i:i+30]:
                    for pat in (
                        r'Raw:\s+"([^"]*)"',
                        r'\(string8\)\s+"([^"]*)"',
                        r'\(string16\)\s+"([^"]*)"',
                    ):
                        m=re.search(pat,q)
                        if m:
                            cand=m.group(1).strip()
                            if cand and cand not in ("reference","string","default"):
                                val=cand
                                break
                    if val:
                        break
                    m=re.search(r'\(string8\)\s+([^\s].*)$',q)
                    if m:
                        cand=m.group(1).strip().strip('"')
                        if cand and cand not in ("(reference)","reference") and not cand.startswith("0x"):
                            val=cand
                            break
                debug[name]={
                    "foundResourceLine":True,
                    "parserMatched":bool(val),
                    "command":" ".join(cmd[:3]),
                    "lineIndex":i,
                }
                if val and name not in vals:
                    vals[name]=val
        if all(k in vals for k in ("google_app_id","google_api_key","project_id")):
            break
    return vals,debug

vals,extract_debug=aapt_values(base)
if not vals.get("google_app_id"):
    per_apk={}
    for apk in apks:
        v,d=aapt_values(apk)
        per_apk[apk.name]=d
        if v.get("google_app_id"):
            base=apk
            vals=v
            extract_debug=d
            break
    extract_debug={"selectedApk":base.name,"perApk":per_apk,"selectedDebug":extract_debug}

app_id=vals.get("google_app_id")
api_key=vals.get("google_api_key")
project_id=vals.get("project_id")

def post_json(url,headers,payload):
    data=json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,headers=headers,method="POST")
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            body=r.read().decode("utf-8","replace")
            try:
                obj=json.loads(body)
            except Exception:
                obj={"raw":body[:20000]}
            return r.status,obj
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        try:
            obj=json.loads(body)
        except Exception:
            obj={"raw":body[:20000]}
        return e.code,obj
    except Exception as e:
        return 0,{"error":type(e).__name__+": "+str(e)}

install_status=None
install_schema=None
rc_status=None
rc_keys=[]
interesting={}
auth_token=None
fid=None

if app_id and api_key and project_id:
    fis_url=f"https://firebaseinstallations.googleapis.com/v1/projects/{project_id}/installations"
    fid="c"+hashlib.sha256((app_id+"tcc-v2").encode()).hexdigest()[:21]
    install_status,inst=post_json(
        fis_url,
        {
            "Content-Type":"application/json",
            "Accept":"application/json",
            "x-goog-api-key":api_key,
        },
        {
            "fid":fid,
            "appId":app_id,
            "authVersion":"FIS_v2",
            "sdkVersion":"a:17.2.0",
        },
    )
    if isinstance(inst,dict):
        install_schema={"keys":sorted(inst.keys())}
        auth_obj=inst.get("authToken") if isinstance(inst.get("authToken"),dict) else {}
        auth_token=auth_obj.get("token")

    if auth_token:
        rc_url=f"https://firebaseremoteconfig.googleapis.com/v1/projects/{project_id}/namespaces/firebase:fetch"
        rc_status,rc=post_json(
            rc_url,
            {
                "Content-Type":"application/json",
                "Accept":"application/json",
                "x-goog-api-key":api_key,
                "x-goog-firebase-installations-auth":auth_token,
            },
            {
                "appId":app_id,
                "appInstanceId":fid,
                "appInstanceIdToken":auth_token,
                "languageCode":"en-US",
                "countryCode":"BE",
                "platformVersion":"Android",
                "packageName":"com.total.europe",
                "sdkVersion":"21.6.0",
            },
        )
        if isinstance(rc,dict):
            entries=rc.get("entries") or {}
            if isinstance(entries,dict):
                rc_keys=sorted(entries.keys())
                for k,v in entries.items():
                    lk=k.lower()
                    if any(x in lk for x in ("api","key","url","base","endpoint","evdc","marketplace","infra","environment")):
                        sv=str(v)
                        interesting[k]={
                            "length":len(sv),
                            "sha256":hashlib.sha256(sv.encode()).hexdigest()[:16],
                            "looksUrl":sv.startswith("http"),
                            "looksOpaque":bool(re.fullmatch(r"[A-Za-z0-9._~+/=-]{20,}",sv)),
                        }

out={
    "purpose":"Retry Charge Europe Firebase bootstrap with robust Android resource extraction.",
    "baseApk":{"name":base.name,"bytes":base.stat().st_size},
    "resourcePresence":{
        "googleAppId":bool(app_id),
        "googleApiKey":bool(api_key),
        "projectId":bool(project_id),
        "gcmDefaultSenderId":bool(vals.get("gcm_defaultSenderId")),
        "firebaseDatabaseUrl":bool(vals.get("firebase_database_url")),
    },
    "resourceExtractionDebug":extract_debug,
    "resourceValueShape":{
        k:{
            "length":len(v),
            "prefixClass":(
                "google_api_key" if v.startswith("AIza")
                else "google_app_id" if re.match(r"^1:\d+:android:",v)
                else "project_id" if re.fullmatch(r"[a-z0-9-]+",v)
                else "other"
            ),
        } for k,v in vals.items()
    },
    "resourceHashes":{
        k:{"length":len(v),"sha256":hashlib.sha256(v.encode()).hexdigest()[:16]}
        for k,v in vals.items()
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
        "publicClientFlowOnly":True,
    },
}

(OUT/"charge-europe-firebase-bootstrap-probe-v2-2026-09-28.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2)+"\n"
)
print(json.dumps({
    k:out[k] for k in (
        "resourcePresence","resourceValueShape","installationStatus",
        "remoteConfigStatus","remoteConfigKeyCount","remoteConfigKeys",
        "interestingEntryMetadata"
    )
},ensure_ascii=False,indent=2))
