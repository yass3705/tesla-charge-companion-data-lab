#!/usr/bin/env python3
from __future__ import annotations
import gzip,json,math,urllib.parse,urllib.request,urllib.error,time
from pathlib import Path

PAGES=Path("data/belgium/pages")
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
POI_BASE="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v2/pois"
TARIFF="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v1/pois/tariff"
UA="tesla-charge-companion-data-lab/1.0"

def get_json(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":UA})
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            raw=r.read().decode("utf-8","replace")
            return r.status,json.loads(raw)
    except urllib.error.HTTPError as e:
        raw=e.read().decode("utf-8","replace")
        try: obj=json.loads(raw)
        except Exception: obj={"raw":raw[:10000]}
        return e.code,obj
    except Exception as e:
        return 0,{"error":type(e).__name__+": "+str(e)}

priced=[]
for path in sorted(PAGES.glob("nap-belgium-*.json.gz")):
    with gzip.open(path,"rt",encoding="utf-8") as f: page=json.load(f)
    for loc in page.get("locations") or []:
        if loc.get("operator")!="TotalEnergies": continue
        lat=loc.get("latitude"); lon=loc.get("longitude")
        if lat is None or lon is None: continue
        for st in loc.get("stations") or []:
            for ev in st.get("evses") or []:
                prices=ev.get("prices") or []
                if not prices: continue
                ext=ev.get("externalIdentifiers") or []
                if not ext and ev.get("connectors"):
                    ext=(ev["connectors"][0] or {}).get("externalIdentifiers") or []
                if not ext: continue
                priced.append({
                  "locationId":loc.get("id"),"name":loc.get("brand"),"city":loc.get("city"),
                  "lat":lat,"lon":lon,"evseId":ext[0],"prices":prices,
                  "powerW":ev.get("availableChargingPowerW") or []
                })

# Choose diverse priced samples by rateId/power.
samples=[]; seen=set()
for x in priced:
    rid=tuple(sorted(set(p.get("rateId") for p in x["prices"] if p.get("rateId"))))
    pw=max(x["powerW"]) if x["powerW"] else None
    key=(rid, "hpc" if pw and pw>150000 else "dc" if pw and pw>22000 else "ac")
    if key in seen: continue
    seen.add(key); samples.append(x)
    if len(samples)>=4: break

def dist2(a,b,c,d): return (a-c)**2+(b-d)**2

results=[]
for s in samples:
    params={"latitude":s["lat"],"longitude":s["lon"],"poiType":2,"radius":1}
    st,listing=get_json(POI_BASE+"?"+urllib.parse.urlencode(params))
    candidates=(listing.get("data") or []) if isinstance(listing,dict) else []
    candidates=sorted(candidates,key=lambda p:dist2(s["lat"],s["lon"],p.get("latitude",99),p.get("longitude",99)))[:15]
    matched=None; inspected=[]
    for p in candidates:
        pid=p.get("id")
        if not pid: continue
        ds,dj=get_json(POI_BASE+"/2-"+urllib.parse.quote(pid,safe="")+"/details")
        data=dj.get("data") if isinstance(dj,dict) else None
        ids=[]
        if isinstance(data,dict):
            for cp in data.get("chargePoints") or []:
                ids.append(cp.get("id"))
                if cp.get("id")==s["evseId"]:
                    conns=cp.get("connectors") or []
                    guid=conns[0].get("id") if conns else None
                    matched={"poiId":pid,"details":data,"connectorGuid":guid}
                    break
        inspected.append({"poiId":pid,"status":ds,"networkId":data.get("networkId") if isinstance(data,dict) else None,"chargePointIds":ids[:20]})
        if matched: break
        time.sleep(0.05)
    tariff=None
    if matched and matched.get("connectorGuid"):
        ts,tj=get_json(TARIFF+"?"+urllib.parse.urlencode({"connectorId":matched["connectorGuid"]}))
        tariff={"status":ts,"json":tj}
    results.append({"nap":s,"listingStatus":st,"listingCount":len((listing.get("data") or []) if isinstance(listing,dict) else []),"inspected":inspected,"matched":matched,"tariff":tariff})

payload={"purpose":"Cross-validate Charge+ public tariff semantics against TotalEnergies EVSEs already priced in Belgium NAP","sampleCount":len(samples),"results":results}
(OUT/"chargeplus-priced-crosscheck-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"samples":[{"evseId":r["nap"]["evseId"],"matched":bool(r["matched"]),"tariffStatus":r["tariff"]["status"] if r["tariff"] else None} for r in results]},ensure_ascii=False,indent=2))
