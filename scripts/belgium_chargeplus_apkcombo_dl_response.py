#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,urllib.parse
from pathlib import Path

BASE="https://apkcombo.com"
DL_PATH="/totalenergies-charge/com.totalenergies.chargeplus/01a1200x20240308/dl"
PACKAGE="com.totalenergies.chargeplus"
OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True,exist_ok=True)
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

def post(url,data=None):
    cmd=["curl","-LsS","--retry","2","--connect-timeout","15","--max-time","60",
         "-A",UA,"-H","Referer: https://apkcombo.com/totalenergies-charge/com.totalenergies.chargeplus/download/apk",
         "-X","POST"]
    if data:
        for k,v in data.items():
            cmd += ["--form-string",f"{k}={v}"]
    cmd += ["-w","\n__HTTP__%{http_code}\n__URL__%{url_effective}",url]
    p=subprocess.run(cmd,capture_output=True,text=True)
    body=p.stdout
    m=re.search(r"\n__HTTP__(\d+)\n__URL__(.*)$",body,re.S)
    status=0; final=url
    if m:
        status=int(m.group(1)); final=m.group(2).strip(); body=body[:m.start()]
    return status,final,body,p.stderr[-2000:]

def get(url):
    cmd=["curl","-LsS","--retry","2","--connect-timeout","15","--max-time","60",
         "-A",UA,"-H","Referer: https://apkcombo.com/totalenergies-charge/com.totalenergies.chargeplus/download/apk",
         "-w","\n__HTTP__%{http_code}\n__URL__%{url_effective}",url]
    p=subprocess.run(cmd,capture_output=True,text=True)
    body=p.stdout
    m=re.search(r"\n__HTTP__(\d+)\n__URL__(.*)$",body,re.S)
    status=0; final=url
    if m:
        status=int(m.group(1)); final=m.group(2).strip(); body=body[:m.start()]
    return status,final,body,p.stderr[-2000:]

status,final,html,err=post(BASE+DL_PATH,{"package_name":PACKAGE,"version":""})

hrefs=[]
for h in re.findall(r'href=["\']([^"\']+)["\']',html,re.I):
    u=urllib.parse.urljoin(final,h.replace("&amp;","&"))
    if any(x in u.lower() for x in ("download","dl?","apk","xapk","apks","bundle")):
        hrefs.append(u)

# APKCombo appends an opaque anti-abuse/check-in query to variant links.
cs,cf,checkin,cerr=post(BASE+"/checkin")
checkin=checkin.strip()
augmented=[]
for u in dict.fromkeys(hrefs):
    if checkin and "=" in checkin:
        sep="&" if "?" in u else "?"
        augmented.append(u+sep+checkin+"&package_name="+urllib.parse.quote(PACKAGE)+"&lang=en")
    augmented.append(u)

probes=[]
for u in list(dict.fromkeys(augmented))[:30]:
    st,fin,body,e=get(u)
    ct=""
    # Avoid writing binaries; only keep textual pages and redirect target.
    looks_binary=body.startswith("PK\x03\x04") or body[:4]=="PK\x03\x04"
    rec={"url":u,"status":st,"finalUrl":fin,"bodyBytes":len(body.encode("utf-8","ignore")),"error":e}
    if not looks_binary and len(body)<500000:
        rec["snippet"]=body[:12000]
        rec["hrefs"]=re.findall(r'href=["\']([^"\']+)["\']',body,re.I)[:200]
    probes.append(rec)

out={
 "endpoint":BASE+DL_PATH,
 "postStatus":status,"postFinalUrl":final,"postError":err,
 "responseBytes":len(html),"responseSnippet":html[:50000],
 "variantHrefs":list(dict.fromkeys(hrefs)),
 "checkinStatus":cs,
 "checkinTokenPresent":bool(checkin),
 "probes":probes,
}
(OUT/"apkcombo-dl-response-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({
 "postStatus":status,"responseBytes":len(html),"variantHrefCount":len(set(hrefs)),
 "checkinStatus":cs,"checkinTokenPresent":bool(checkin),
 "variants":list(dict.fromkeys(hrefs))[:20],
 "probeSummary":[{"status":p["status"],"finalUrl":p["finalUrl"],"bodyBytes":p["bodyBytes"]} for p in probes]
},ensure_ascii=False,indent=2))
