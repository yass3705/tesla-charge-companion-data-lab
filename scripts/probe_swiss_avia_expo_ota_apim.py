#!/usr/bin/env python3
import hashlib,json,re,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone

UPDATE="https://u.expo.dev/fa2bf032-b95f-46b0-807b-0cbb741794c5"
TENANT="fdcb995a-8234-42ed-826f-3f2c7499d7f8"
API="https://pdefweushaapiam01.azure-api.net/app-backend/v1/cpos"
OUT=Path("docs/switzerland-avia-expo-ota-apim-probe-2026-09-28.json")

def req(url,headers=None,limit=None):
    r=urllib.request.Request(url,headers=headers or {})
    with urllib.request.urlopen(r,timeout=30) as x:
        b=x.read() if limit is None else x.read(limit)
        return x.status,dict(x.headers),b

headers={
 "expo-platform":"android",
 "expo-runtime-version":"2.3.0",
 "expo-channel-name":"production",
 "accept":"application/expo+json,application/json,multipart/mixed",
 "user-agent":"expo-updates/AVIA-VOLT"
}
report={"generatedAt":datetime.now(timezone.utc).isoformat(),"updateUrl":UPDATE,"tenantId":TENANT}
try:
    status,h,b=req(UPDATE,headers)
    report["manifestStatus"]=status
    report["manifestContentType"]=h.get("Content-Type")
    report["manifestBytes"]=len(b)
    launch_urls=[]
    try:
        m=json.loads(b.decode("utf-8"))
        report["manifestKeys"]=list(m)[:50]
        la=m.get("launchAsset") or {}
        if isinstance(la,dict) and la.get("url"): launch_urls.append(la["url"])
        for a in m.get("assets") or []:
            if isinstance(a,dict) and a.get("url") and str(a.get("contentType","")).find("javascript")>=0:
                launch_urls.append(a["url"])
    except Exception as e:
        report["manifestJsonError"]=repr(e)
        # best effort extract URLs from multipart/text
        txt=b.decode("utf-8","replace")
        launch_urls += re.findall(r'https://[^"\\\s]+',txt)
    report["candidateLaunchAssetCount"]=len(launch_urls)
    results=[]
    for url in launch_urls[:20]:
        try:
            s,h2,asset=req(url,{"User-Agent":"AVIA VOLT Suisse/4617"})
            # candidate API keys: 32-char hex + base64ish 32-64 chars, dedup
            cands=set(re.findall(rb'(?<![0-9A-Fa-f])[0-9A-Fa-f]{32}(?![0-9A-Fa-f])',asset))
            cands.update(re.findall(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{40,64}(?![A-Za-z0-9_-])',asset))
            tested=[]
            for c in list(cands)[:500]:
                try:
                    val=c.decode()
                except: continue
                # skip obvious ids/hashes
                if val.lower().startswith(("http","sha")): continue
                hh={"Accept":"application/json","User-Agent":"AVIA VOLT Suisse/4617","Ocp-Apim-Subscription-Key":val,"X-Tenant-Id":TENANT}
                rr=urllib.request.Request(API,headers=hh)
                try:
                    with urllib.request.urlopen(rr,timeout=12) as x:
                        body=x.read(2000)
                        code=x.status
                except urllib.error.HTTPError as e:
                    code=e.code; body=e.read(1000)
                if code!=401:
                    tested.append({"keySha256Prefix":hashlib.sha256(c).hexdigest()[:12],"status":code,"bodyPreview":body.decode("utf-8","replace")[:300]})
                    if 200<=code<300:
                        report["workingSubscriptionKeyFound"]=True
                        report["workingKeySha256Prefix"]=hashlib.sha256(c).hexdigest()[:12]
                        report["workingStatus"]=code
                        break
            results.append({"url":url,"status":s,"contentType":h2.get("Content-Type"),"bytes":len(asset),"candidateCount":len(cands),"non401Results":tested[:20]})
            if report.get("workingSubscriptionKeyFound"): break
        except Exception as e:
            results.append({"url":url,"error":repr(e)})
    report["assets"]=results
except Exception as e:
    report["error"]=repr(e)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
