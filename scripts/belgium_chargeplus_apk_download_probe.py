#!/usr/bin/env python3
from __future__ import annotations
import json, re, subprocess, zipfile, os, shutil
from pathlib import Path
from urllib.parse import urljoin

OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True,exist_ok=True)
TMP=Path("/tmp/chargeplus-apk")
TMP.mkdir(parents=True,exist_ok=True)

PAGES=[
 "https://apkpure.net/charge/com.totalenergies.chargeplus/download",
 "https://apkpure.net/charge/com.totalenergies.chargeplus/download/2.17.2",
 "https://apkcombo.com/totalenergies-charge/com.totalenergies.chargeplus/download/apk",
]
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

def curl(url,out=None):
    cmd=["curl","-k","-LsS","--retry","2","--connect-timeout","15","--max-time","90","-A",UA]
    if out:
        cmd += ["-o",str(out),"-w","%{http_code}\n%{url_effective}"]
    else:
        cmd += ["-w","\n__HTTP__%{http_code}\n__URL__%{url_effective}"]
    cmd += [url]
    p=subprocess.run(cmd,capture_output=True,text=True)
    if out:
        parts=p.stdout.strip().splitlines()
        code=int(parts[-2]) if len(parts)>=2 and parts[-2].isdigit() else 0
        final=parts[-1] if parts else url
        return code,final,"",p.stderr[-2000:]
    body=p.stdout
    m=re.search(r"\n__HTTP__(\d+)\n__URL__(.*)$",body,re.S)
    code=0; final=url
    if m:
        code=int(m.group(1)); final=m.group(2).strip(); body=body[:m.start()]
    return code,final,body,p.stderr[-2000:]

pages=[]
candidates=[]
for page in PAGES:
    code,final,body,err=curl(page)
    urls=set()
    for m in re.findall(r'https?://[^"\'<>\s]+',body):
        if any(x in m.lower() for x in (".apk",".xapk","download.apkpure","d.apkpure","apkcombo")):
            urls.add(m.replace("&amp;","&"))
    for m in re.findall(r'(?:href|data-dt-url|data-url)=["\']([^"\']+)["\']',body,re.I):
        u=urljoin(final,m.replace("&amp;","&"))
        if any(x in u.lower() for x in (".apk",".xapk","download","apkpure","apkcombo")):
            urls.add(u)
    pages.append({"url":page,"status":code,"finalUrl":final,"bytes":len(body),"error":err,"candidates":sorted(urls)[:300]})
    candidates.extend(sorted(urls))

# rank likely binary URLs
ranked=[]
for u in dict.fromkeys(candidates):
    s=u.lower()
    score=0
    if ".xapk" in s or ".apk" in s: score+=10
    if "download.apkpure" in s or "d.apkpure" in s: score+=6
    if "com.totalenergies.chargeplus" in s or "chargeplus" in s: score+=4
    if "2.17.2" in s: score+=2
    ranked.append((score,u))
ranked.sort(reverse=True)

download=None
for score,u in ranked[:30]:
    if score<6: continue
    dest=TMP/"chargeplus.bin"
    code,final,_,err=curl(u,dest)
    size=dest.stat().st_size if dest.exists() else 0
    if code==200 and size>1_000_000:
        download={"source":u,"finalUrl":final,"httpStatus":code,"bytes":size,"error":err}
        break
    if dest.exists(): dest.unlink()

report={"package":"com.totalenergies.chargeplus","pages":pages,"rankedCandidates":[{"score":s,"url":u} for s,u in ranked[:80]],"download":download}

if download:
    dest=TMP/"chargeplus.bin"
    # XAPK/ZIP inspection only; do not persist binaries.
    if zipfile.is_zipfile(dest):
        with zipfile.ZipFile(dest) as z:
            names=z.namelist()
            report["archive"]={"fileCount":len(names),"names":names[:500]}
            apks=[n for n in names if n.lower().endswith(".apk")]
            extracted=[]
            for n in apks[:20]:
                target=TMP/Path(n).name
                with z.open(n) as src, open(target,"wb") as out:
                    shutil.copyfileobj(src,out)
                extracted.append(str(target))
            report["archive"]["apkCount"]=len(apks)
            report["archive"]["extracted"]=extracted
    else:
        # Could already be a raw APK.
        report["archive"]={"zip":False}

(OUT/"chargeplus-apk-download-probe-2026-09-28.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"download":download,"candidateCount":len(ranked),"archive":report.get("archive")},ensure_ascii=False,indent=2))
