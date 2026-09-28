#!/usr/bin/env python3
from __future__ import annotations
import json, re, subprocess, urllib.request, zipfile, shutil, os
from pathlib import Path

URL="https://download.pureapk.com/b/XAPK/Y29tLnRvdGFsZW5lcmdpZXMuY2hhcmdlcGx1c18yMDI2MDkwMTEzXzc0Y2M4MDc4?as2=cc78d5fcf5499f8c9e9167f075c12b946c953d25&k=aba31a210e2405ac3acb978d0dc3e56f6c953d25&_p=Y29tLnRvdGFsZW5lcmdpZXMuY2hhcmdlcGx1cw&c=1%7CTOOLS%7Cb2lkPTkmZGV2PVRvdGFsRW5lcmdpZXMlMjBNYXJrZXRpbmclMjAlMjYlMjBTZXJ2aWNlcyZ0PXhhcGsmcz0yMzA4MTI2MSZ2bj0yLjE3LjMmdmM9MjAyNjA5MDExMw&_fn=VG90YWxFbmVyZ2llcystK0NoYXJnZSUyQl8yLjE3LjNfYXBrY29tYm8uY29tLnhhcGs%3D"
TMP=Path("/tmp/chargeplus-static")
OUT=Path("reports/belgium/totalenergies")
TMP.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
XAPK=TMP/"chargeplus.xapk"

req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0","Referer":"https://apkcombo.com/"})
with urllib.request.urlopen(req,timeout=120) as r:
    data=r.read()
XAPK.write_bytes(data)

report={"package":"com.totalenergies.chargeplus","version":"2.17.3","downloadBytes":len(data),"isZip":zipfile.is_zipfile(XAPK)}

def redact(s:str)->str:
    s=re.sub(r'(?i)(client_secret|api[_-]?key|apikey|access_token|id_token|refresh_token|authorization)=([^&\s"\']+)',r'\1=[REDACTED]',s)
    s=re.sub(r'(?i)("?(?:client_secret|api[_-]?key|apikey|access_token|id_token|refresh_token|authorization)"?\s*[:=]\s*["\'])([^"\']+)',r'\1[REDACTED]',s)
    return s

if not zipfile.is_zipfile(XAPK):
    report["error"]="Downloaded object is not a ZIP/XAPK"
else:
    root=TMP/"xapk"; root.mkdir(exist_ok=True)
    with zipfile.ZipFile(XAPK) as z:
        names=z.namelist()
        report["xapkFiles"]=names
        z.extractall(root)
    apks=list(root.rglob("*.apk"))
    report["apkCount"]=len(apks)
    extracted=[]
    all_strings=[]
    for i,apk in enumerate(apks):
        adir=TMP/f"apk_{i}"
        adir.mkdir(exist_ok=True)
        if zipfile.is_zipfile(apk):
            with zipfile.ZipFile(apk) as z:
                z.extractall(adir)
        extracted.append({"name":apk.name,"bytes":apk.stat().st_size})
        for fp in adir.rglob("*"):
            if not fp.is_file() or fp.stat().st_size>150_000_000: continue
            try:
                p=subprocess.run(["strings","-n","5",str(fp)],capture_output=True,text=True,errors="replace",timeout=30)
                if p.stdout:
                    all_strings.append(p.stdout)
            except Exception:
                pass
    report["apks"]=extracted
    text="\n".join(all_strings)
    low=text.lower()
    keywords=["bemo","be-mo","auth.bemo","tariff","pricing","price","getplace","place","evse","connector","station","charger","guest","oauth","api-key","x-api-key","endusertariff","simulation"]
    contexts=[]
    for kw in keywords:
        start=0; seen=0
        while True:
            pos=low.find(kw,start)
            if pos<0 or seen>=80: break
            ctx=text[max(0,pos-350):min(len(text),pos+900)].replace("\x00","")
            ctx=redact(ctx)
            if ctx not in contexts: contexts.append(ctx)
            start=pos+len(kw); seen+=1
    urls=sorted(set(re.findall(r'https?://[^\s"\'<>\\]{5,500}',text)))
    hosts=[]
    for u in urls:
        if any(k in u.lower() for k in ("bemo","totalenergies","charge","api","oauth","station","map")):
            hosts.append(redact(u))
    report["interestingUrls"]=hosts[:1000]
    report["contexts"]=contexts[:1000]
    report["keywordCounts"]={k:low.count(k) for k in keywords}

(OUT/"chargeplus-static-analysis-2026-09-28.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({
 "downloadBytes":report["downloadBytes"],"isZip":report["isZip"],"apkCount":report.get("apkCount"),
 "apks":report.get("apks"),"keywordCounts":report.get("keywordCounts"),
 "interestingUrls":report.get("interestingUrls",[])[:100]
},ensure_ascii=False,indent=2))
