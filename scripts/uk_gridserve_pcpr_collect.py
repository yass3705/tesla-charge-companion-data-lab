#!/usr/bin/env python3
import gzip, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE="https://api.gridserve.com/ocpi/v1"
KEY=os.environ.get("GRIDSERVE_PCPR_API_KEY","").strip()
if not KEY: raise SystemExit("GRIDSERVE_PCPR_API_KEY is missing")
UA="TeslaChargeCompanion/9 Gridserve-PCPR"

def request_json(url):
    req=urllib.request.Request(url,headers={"ec-subscription-key":KEY,"Accept":"application/json","User-Agent":UA},method="GET")
    try:
        with urllib.request.urlopen(req,timeout=60) as r:
            data=json.loads(r.read().decode("utf-8"))
            return r.status,data,dict(r.headers.items())
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8",errors="replace")
        print(f"HTTP {e.code} for {url}: {body[:500]}",file=sys.stderr); raise

def items_from_payload(payload):
    if isinstance(payload,list): return payload
    if isinstance(payload,dict):
        for k in ("data","results","items","locations","tariffs"):
            if isinstance(payload.get(k),list): return payload[k]
    return []

def next_url(payload,headers,current):
    link=headers.get("Link") or headers.get("link")
    if link:
        m=re.search(r'<([^>]+)>;\s*rel="?next"?',link)
        if m: return urllib.parse.urljoin(current,m.group(1))
    if isinstance(payload,dict):
        for k in ("next","next_url","nextUrl"):
            if isinstance(payload.get(k),str) and payload[k]: return urllib.parse.urljoin(current,payload[k])
        p=payload.get("pagination")
        if isinstance(p,dict):
            for k in ("next","next_url","nextUrl"):
                if isinstance(p.get(k),str) and p[k]: return urllib.parse.urljoin(current,p[k])
    return None

def collect(path,max_pages=500):
    url=BASE+path; rows=[]; pages=0; seen=set(); first=None; first_headers={}
    while url:
        if url in seen: raise RuntimeError(f"pagination loop detected: {url}")
        seen.add(url)
        status,payload,headers=request_json(url)
        if status!=200: raise RuntimeError(f"unexpected status {status}: {url}")
        if first is None: first,first_headers=payload,headers
        rows.extend(items_from_payload(payload)); pages+=1
        url=next_url(payload,headers,url)
        if pages>=max_pages and url: raise RuntimeError("pagination exceeded max_pages")
        if url: time.sleep(0.05)
    return rows,pages,first,first_headers

def keyset(x): return sorted(x.keys()) if isinstance(x,dict) else []

def nested_stats(locations):
    evses=connectors=0; statuses={}; refs=set(); lk=[]; ek=[]; ck=[]
    for loc in locations:
        if not isinstance(loc,dict): continue
        if not lk: lk=keyset(loc)
        for evse in (loc.get("evses") or []):
            if not isinstance(evse,dict): continue
            evses+=1
            if not ek: ek=keyset(evse)
            st=evse.get("status")
            if st is not None: statuses[str(st)]=statuses.get(str(st),0)+1
            tids=evse.get("tariff_ids")
            if isinstance(tids,list): refs.update(str(x) for x in tids if x is not None)
            if evse.get("tariff_id") is not None: refs.add(str(evse["tariff_id"]))
            for conn in (evse.get("connectors") or []):
                if not isinstance(conn,dict): continue
                connectors+=1
                if not ck: ck=keyset(conn)
                tids=conn.get("tariff_ids")
                if isinstance(tids,list): refs.update(str(x) for x in tids if x is not None)
                if conn.get("tariff_id") is not None: refs.add(str(conn["tariff_id"]))
    return {"evses":evses,"connectors":connectors,"statuses":statuses,"distinctTariffReferences":len(refs),
            "sampleLocationKeys":lk,"sampleEvseKeys":ek,"sampleConnectorKeys":ck},refs

def tariff_stats(tariffs):
    ids=set(); currencies={}; types={}; component_types={}; tk=[]
    for t in tariffs:
        if not isinstance(t,dict): continue
        if not tk: tk=keyset(t)
        if t.get("id") is not None: ids.add(str(t["id"]))
        cur=t.get("currency")
        if cur is not None: currencies[str(cur)]=currencies.get(str(cur),0)+1
        typ=t.get("type")
        if typ is not None: types[str(typ)]=types.get(str(typ),0)+1
        for el in (t.get("elements") or []):
            if isinstance(el,dict):
                for pc in (el.get("price_components") or []):
                    if isinstance(pc,dict) and pc.get("type") is not None:
                        k=str(pc["type"]); component_types[k]=component_types.get(k,0)+1
    return {"distinctTariffIds":len(ids),"currencies":currencies,"types":types,
            "priceComponentTypes":component_types,"sampleTariffKeys":tk},ids

locations,lp,first_loc,loc_headers=collect("/locations")
tariffs,tp,first_tariff,tariff_headers=collect("/tariffs")
loc_stats,refs=nested_stats(locations)
tar_stats,tariff_ids=tariff_stats(tariffs)
missing=sorted(refs-tariff_ids)
now=datetime.now(timezone.utc).isoformat()
os.makedirs("data/national",exist_ok=True); os.makedirs("reports/uk",exist_ok=True)

with gzip.open("data/national/uk_gridserve_pcpr_locations.json.gz","wt",encoding="utf-8") as f:
    json.dump({"source":"GRIDSERVE PCPR Open Data API","endpoint":BASE+"/locations","collectedAt":now,"pages":lp,"locations":locations},f,ensure_ascii=False,separators=(",",":"))
with gzip.open("data/national/uk_gridserve_pcpr_tariffs.json.gz","wt",encoding="utf-8") as f:
    json.dump({"source":"GRIDSERVE PCPR Open Data API","endpoint":BASE+"/tariffs","collectedAt":now,"pages":tp,"tariffs":tariffs},f,ensure_ascii=False,separators=(",",":"))

report={"provider":"GRIDSERVE","country":"GB","collectedAt":now,"baseUrl":BASE+"/","authHeader":"ec-subscription-key",
        "locations":{"pages":lp,"count":len(locations),**loc_stats},
        "tariffs":{"pages":tp,"count":len(tariffs),**tar_stats},
        "join":{"distinctReferencedTariffs":len(refs),"resolvedReferencedTariffs":len(refs&tariff_ids),
                "missingReferencedTariffIdsCount":len(missing),"missingReferencedTariffIds":missing[:100]},
        "firstResponseShapes":{"locationsTopLevel":keyset(first_loc),"tariffsTopLevel":keyset(first_tariff),
            "locationsContentType":loc_headers.get("Content-Type") or loc_headers.get("content-type"),
            "tariffsContentType":tariff_headers.get("Content-Type") or tariff_headers.get("content-type")},
        "secretPresent":True,"secretValuePersisted":False}
with open("reports/uk/gridserve-pcpr-latest.json","w",encoding="utf-8") as f:
    json.dump(report,f,ensure_ascii=False,indent=2); f.write("\n")

if not locations: raise SystemExit("GRIDSERVE /locations returned no locations")
if not tariffs: raise SystemExit("GRIDSERVE /tariffs returned no tariffs")
print(json.dumps({"locations":len(locations),"locationPages":lp,"evses":loc_stats["evses"],
                  "connectors":loc_stats["connectors"],"tariffs":len(tariffs),"tariffPages":tp,
                  "referencedTariffs":len(refs),"missingTariffRefs":len(missing)},indent=2))
