#!/usr/bin/env python3
from __future__ import annotations
import gzip,json,re,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE="https://www.lidl.co.uk/s/en-GB/store-finder/"
UA="Mozilla/5.0 TeslaChargeCompanion/9 Lidl-GB-public-store-inventory"

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read(3_000_000).decode("utf-8","replace"),r.geturl()

def links(base,body):
    out=[]
    for h in re.findall(r'href=["\\\']([^"\\\']+)["\\\']',body,re.I):
        u=urllib.parse.urljoin(base,h.split("#")[0])
        if u.startswith(BASE): out.append(u)
    return out

home,final=get(BASE)
cities=[u for u in sorted(set(links(final,home))) if u.rstrip("/")!=BASE.rstrip("/")]
store_urls=set(); city_ok=0
for u in cities:
    try:
        body,fu=get(u); city_ok+=1
        for x in links(fu,body):
            if x[len(BASE):].strip("/").count("/")>=1: store_urls.add(x)
        time.sleep(.03)
    except Exception: pass

stores=[]; failures=[]
for i,u in enumerate(sorted(store_urls),1):
    try:
        body,fu=get(u)
        txt=re.sub(r"<[^>]+>"," ",body); txt=re.sub(r"\\s+"," ",txt)
        if "Lidl Store" not in body and "Lidl store" not in body: continue
        ev="EV Charging" in txt
        lat=lon=None
        for m in re.finditer(r'<script[^>]+type=["\\\']application/ld\\+json["\\\'][^>]*>(.*?)</script>',body,re.I|re.S):
            try:
                p=json.loads(m.group(1)); objs=p if isinstance(p,list) else [p]
                for o in objs:
                    if isinstance(o,dict):
                        g=o.get("geo") or {}
                        if isinstance(g,dict) and g.get("latitude") is not None:
                            lat=g.get("latitude"); lon=g.get("longitude")
            except Exception: pass
        stores.append({"url":fu,"evCharging":ev,"lat":lat,"lon":lon})
    except Exception as e:
        failures.append({"url":u,"error":f"{type(e).__name__}: {e}"})
    if i%100==0: print("progress",i,len(store_urls))
    time.sleep(.02)

ev=[x for x in stores if x["evCharging"]]
now=datetime.now(timezone.utc).isoformat()
report={"country":"GB","network":"Lidl","retrievedAt":now,"source":BASE,
        "cityPagesCrawled":city_ok,"storePagesDiscovered":len(store_urls),
        "storePagesParsed":len(stores),"evChargingStores":len(ev),
        "geocodedEvStores":sum(1 for x in ev if x["lat"] is not None and x["lon"] is not None),
        "failureCount":len(failures),"failures":failures[:100],
        "status":"location_inventory_complete_from_public_store_finder" if ev else "failed_empty"}
(ROOT/"reports/uk").mkdir(parents=True,exist_ok=True)
(ROOT/"data/national").mkdir(parents=True,exist_ok=True)
(ROOT/"reports/uk/lidl-public-ev-stores-latest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\\n")
with gzip.open(ROOT/"data/national/uk_lidl_public_ev_stores.json.gz","wt",encoding="utf-8") as g:
    json.dump({"retrievedAt":now,"stores":ev},g,ensure_ascii=False,separators=(",",":"))
print(json.dumps(report,ensure_ascii=False,indent=2))
if not ev: raise SystemExit(2)
