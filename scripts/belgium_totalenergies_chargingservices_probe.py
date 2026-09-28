#!/usr/bin/env python3
from __future__ import annotations
import json, re, ssl, urllib.request, urllib.parse
from html.parser import HTMLParser
from pathlib import Path

OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True,exist_ok=True)
TARGETS=[
  "https://chargingservices.totalenergies.com/en/find-a-charger?countryCode=BE",
  "https://chargingservices.totalenergies.com/en/home/belgium",
  "https://chargingservices.totalenergies.com/fr/home/belgium",
]
CTX=ssl._create_unverified_context()

class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.assets=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        v=d.get("src") if tag=="script" else d.get("href") if tag=="link" else None
        if v: self.assets.append(v)

def get(url):
    req=urllib.request.Request(url,headers={
      "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
      "Accept":"text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"
    })
    try:
        with urllib.request.urlopen(req,timeout=45,context=CTX) as resp:
            return resp.status,resp.geturl(),resp.read().decode("utf-8","replace"),""
    except Exception as e:
        return getattr(e,"code",0) or 0,url,"",type(e).__name__+": "+str(e)

def inspect(txt):
    urls=sorted(set(re.findall(r"https?://[^\\s\\\"<>]+",txt)))
    needles=('api','charger','station','evse','connector','tariff','price','payment','location','countrycode','map','bemo')
    snippets=[]
    low=txt.lower()
    for n in needles:
        start=0
        while True:
            i=low.find(n,start)
            if i<0: break
            s=txt[max(0,i-180):min(len(txt),i+420)]
            if s not in snippets: snippets.append(s)
            start=i+len(n)
            if len(snippets)>=800: break
        if len(snippets)>=800: break
    return {"urls":urls[:1000],"snippets":snippets[:800]}

pages=[]; scripts=[]
for t in TARGETS:
    st,fin,body,err=get(t)
    rec={"url":t,"finalUrl":fin,"status":st,"bytes":len(body),"error":err}
    if body:
        p=AssetParser(); p.feed(body)
        aa=[]
        for x in p.assets:
            u=urllib.parse.urljoin(fin,x)
            if u not in aa: aa.append(u)
        rec["assets"]=aa; rec["inspection"]=inspect(body)
        for u in aa:
            if ".js" not in u.lower(): continue
            if any(x["url"]==u for x in scripts): continue
            sst,sfin,sbody,serr=get(u)
            sr={"url":u,"finalUrl":sfin,"status":sst,"bytes":len(sbody),"error":serr}
            if sbody: sr["inspection"]=inspect(sbody)
            scripts.append(sr)
    pages.append(rec)

blob=json.dumps({"pages":pages,"scripts":scripts},ensure_ascii=False).lower()
summary={
  "pages":[{"url":x["url"],"status":x["status"],"bytes":x["bytes"],"assets":len(x.get("assets",[]))} for x in pages],
  "scriptsInspected":len(scripts),
  "mentions":{
    "api":"/api/" in blob or "api." in blob,
    "tariff":"tariff" in blob, "price":"price" in blob, "evse":"evse" in blob,
    "connector":"connector" in blob, "countryCode":"countrycode" in blob,
    "bemo":"bemo" in blob or "be-mo" in blob, "woosmap":"woosmap" in blob
  }
}
payload={"operator":"TotalEnergies","country":"BE","surface":"chargingservices.totalenergies.com","summary":summary,"pages":pages,"scripts":scripts}
(OUT/"chargingservices-backend-probe-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))