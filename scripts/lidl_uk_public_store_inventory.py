#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures
import gzip
import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE="https://www.lidl.co.uk"
STORE_ROOT="/s/en-GB/store-finder/"
UA="Mozilla/5.0 TeslaChargeCompanion/9 Lidl-GB-public-store-inventory"

def get(url_or_path,retries=3):
    url=url_or_path if url_or_path.startswith("http") else BASE+url_or_path
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    last=None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=40) as r:
                return r.read().decode("utf-8","replace"),r.geturl()
        except Exception as e:
            last=e
            time.sleep(1+i)
    raise last

def links(base,body):
    out=set()
    for h in re.findall(r'href=["\']([^"\']+)["\']',body,re.I):
        u=urllib.parse.urljoin(base,html.unescape(h).split("#")[0])
        p=urllib.parse.urlparse(u)
        if p.netloc in ("www.lidl.co.uk","lidl.co.uk") and p.path.startswith(STORE_ROOT):
            out.add(urllib.parse.urlunparse(("https","www.lidl.co.uk",p.path,"","","")))
    return out

def clean(body):
    body=re.sub(r"<script\b[^>]*>.*?</script>"," ",body,flags=re.I|re.S)
    body=re.sub(r"<style\b[^>]*>.*?</style>"," ",body,flags=re.I|re.S)
    body=re.sub(r"<[^>]+>"," ",body)
    return re.sub(r"\s+"," ",html.unescape(body)).strip()

def parse_store(url):
    body,final=get(url)
    txt=clean(body)
    if "Lidl Store" not in txt and "Lidl store" not in txt:
        return None
    ev=bool(re.search(r"\bEV Charging\b",txt,re.I))
    title=None
    m=re.search(r"Lidl Store\s+(.+?)(?:Navigate me to store|Opening hours|Store Details)",txt,re.I)
    if m: title=m.group(1).strip()
    postcode=None
    pm=re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b",txt,re.I)
    if pm: postcode=pm.group(1).upper()
    lat=lon=None
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',body,re.I|re.S):
        try:
            payload=json.loads(m.group(1))
            objs=payload if isinstance(payload,list) else [payload]
            for o in objs:
                if isinstance(o,dict):
                    g=o.get("geo") or {}
                    if isinstance(g,dict) and g.get("latitude") is not None:
                        lat=g.get("latitude"); lon=g.get("longitude")
        except Exception:
            pass
    return {
      "url":final,
      "name":title,
      "postcode":postcode,
      "evCharging":ev,
      "lat":lat,
      "lon":lon
    }

def main():
    sitemap_root=BASE+"/static/sitemap.xml"
    sitemap_seen=set()
    sitemap_errors=[]
    store_urls=set()

    def crawl_sitemap(url,depth=0):
        if url in sitemap_seen or depth>3:
            return
        sitemap_seen.add(url)
        try:
            body,_=get(url)
        except Exception as e:
            sitemap_errors.append({"url":url,"error":f"{type(e).__name__}: {e}"})
            return
        locs=[html.unescape(x.strip()) for x in re.findall(r"<loc>(.*?)</loc>",body,re.I|re.S)]
        for loc in locs:
            p=urllib.parse.urlparse(loc)
            if p.netloc not in ("www.lidl.co.uk","lidl.co.uk"):
                continue
            if p.path.endswith(".xml"):
                crawl_sitemap(loc,depth+1)
                continue
            if not p.path.startswith(STORE_ROOT):
                continue
            rel=p.path[len(STORE_ROOT):].strip("/")
            if len(rel.split("/"))>=2:
                store_urls.add(urllib.parse.urlunparse(("https","www.lidl.co.uk",p.path if p.path.endswith("/") else p.path+"/","","","")))

    crawl_sitemap(sitemap_root)
    if len(store_urls)<500:
        raise SystemExit(f"Fail closed: only {len(store_urls)} store pages discovered from official sitemap")

    stores=[]; failures=[]
    def store_one(u):
        try: return parse_store(u),None
        except Exception as e: return None,{"url":u,"error":f"{type(e).__name__}: {e}"}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for row,err in ex.map(store_one,sorted(store_urls)):
            if row: stores.append(row)
            if err: failures.append(err)

    stores.sort(key=lambda x:x["url"])
    ev=[x for x in stores if x["evCharging"]]
    if len(stores)<500:
        raise SystemExit(f"Fail closed: only {len(stores)} stores parsed")
    if len(ev)<50:
        raise SystemExit(f"Fail closed: only {len(ev)} EV charging stores found")
    failure_ratio=(len(failures)/len(store_urls)) if store_urls else 1
    if failure_ratio>0.05:
        raise SystemExit(f"Fail closed: store fetch failure ratio {failure_ratio:.2%}")

    now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    report={
      "schemaVersion":2,
      "country":"GB",
      "network":"Lidl GB",
      "retrievedAt":now,
      "source":BASE+STORE_ROOT,
      "sourceType":"official_public_store_finder",
      "sitemapsCrawled":len(sitemap_seen),
      "sitemapFetchErrors":len(sitemap_errors),
      "storePagesDiscovered":len(store_urls),
      "storePagesParsed":len(stores),
      "evChargingStores":len(ev),
      "geocodedEvStores":sum(1 for x in ev if x["lat"] is not None and x["lon"] is not None),
      "failureCount":len(failures),
      "failureRatio":failure_ratio,
      "status":"official_store_level_inventory_complete",
      "remainingGap":"Store Finder proves store-level EV charging presence only. Exact charger/EVSE count, connector power and live status require Lidl Plus/charging backend; never infer them from store services.",
      "policy":{
        "readOnly":True,
        "noLogin":True,
        "noMutation":True,
        "doNotInferConnectorPower":True,
        "doNotInferEvseCount":True
      },
      "sitemapErrors":sitemap_errors[:50],
      "failures":failures[:100]
    }
    (ROOT/"reports/uk").mkdir(parents=True,exist_ok=True)
    (ROOT/"data/national").mkdir(parents=True,exist_ok=True)
    (ROOT/"reports/uk/lidl-public-ev-stores-latest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with gzip.open(ROOT/"data/national/uk_lidl_public_ev_stores.json.gz","wt",encoding="utf-8") as g:
        json.dump({"schemaVersion":2,"country":"GB","network":"Lidl GB","retrievedAt":now,"stores":ev},g,ensure_ascii=False,separators=(",",":"))
    print(json.dumps({k:report[k] for k in ("sitemapsCrawled","storePagesDiscovered","storePagesParsed","evChargingStores","geocodedEvStores","failureCount")},ensure_ascii=False))

if __name__=="__main__":
    main()
