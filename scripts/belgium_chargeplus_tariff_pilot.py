#!/usr/bin/env python3
from __future__ import annotations
import gzip,json,math,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path

PAGES=Path("data/belgium/pages")
OUT=Path("reports/belgium/totalenergies"); OUT.mkdir(parents=True,exist_ok=True)
COLL="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v2/pois"
TARIFF="https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v1/pois/tariff"

rows=[]
for path in sorted(PAGES.glob("nap-belgium-*.json.gz")):
    with gzip.open(path,"rt",encoding="utf-8") as f: page=json.load(f)
    for loc in page.get("locations") or []:
        if loc.get("operator")!="TotalEnergies": continue
        for st in loc.get("stations") or []:
            for ev in st.get("evses") or []:
                ext=ev.get("externalIdentifiers") or []
                if not ext: continue
                pw=max(ev.get("availableChargingPowerW") or [0])
                rows.append({
                  "locationId":loc.get("id"),"name":loc.get("brand"),"city":loc.get("city"),
                  "latitude":loc.get("latitude"),"longitude":loc.get("longitude"),
                  "stationId":st.get("id"),"evseId":ev.get("id"),"externalId":ext[0],
                  "powerW":pw,"napPrices":ev.get("prices") or []
                })

def bucket(w):
    kw=w/1000
    if kw<=7.4:return "ac7"
    if kw<=22:return "ac22"
    if kw<=50:return "dc50"
    if kw<=150:return "dc150"
    return "hpc"

def pick(kind,limit=5):
    chosen=[]; seen=set()
    candidates=[r for r in rows if bool(r["napPrices"])==(kind=="priced")]
    # deterministic but maximize power/category and locations
    for r in sorted(candidates,key=lambda x:(bucket(x["powerW"]),x["locationId"],x["externalId"])):
        b=bucket(r["powerW"])
        if b in seen: continue
        seen.add(b); chosen.append(r)
        if len(chosen)>=limit: return chosen
    for r in candidates:
        if r["locationId"] not in {x["locationId"] for x in chosen}:
            chosen.append(r)
            if len(chosen)>=limit: break
    return chosen

sample=[("priced",r) for r in pick("priced",5)]+[("missing",r) for r in pick("missing",5)]

def get_json(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"tesla-charge-companion-data-lab/1.0"})
    try:
        with urllib.request.urlopen(req,timeout=35) as resp:
            text=resp.read().decode("utf-8","replace")
            try:return resp.status,json.loads(text)
            except:return resp.status,{"raw":text[:3000]}
    except urllib.error.HTTPError as e:
        text=e.read().decode("utf-8","replace")
        try:return e.code,json.loads(text)
        except:return e.code,{"raw":text[:3000]}
    except Exception as e:
        return 0,{"error":type(e).__name__+": "+str(e)}

def sqdist(p,r):
    return (float(p.get("latitude",0))-float(r["latitude"]))**2+(float(p.get("longitude",0))-float(r["longitude"]))**2

results=[]
for kind,row in sample:
    q=urllib.parse.urlencode({"latitude":row["latitude"],"longitude":row["longitude"],"poiType":2,"radius":2})
    cs,cp=get_json(COLL+"?"+q)
    pois=(cp.get("data") or []) if isinstance(cp,dict) else []
    candidates=sorted(pois,key=lambda p:sqdist(p,row))[:10]
    matched=None; detail_attempts=[]
    for p in candidates:
        pid=p.get("id")
        if not pid: continue
        ds,dp=get_json(f"https://public.mycardprd.alzp.tgscloud.net/chargeplus-bff/v2/pois/2-{urllib.parse.quote(str(pid),safe='')}/details")
        data=dp.get("data") if isinstance(dp,dict) else None
        detail_attempts.append({"poiId":pid,"status":ds,"name":data.get("name") if isinstance(data,dict) else None,"networkId":data.get("networkId") if isinstance(data,dict) else None})
        if not isinstance(data,dict): continue
        if data.get("networkId")!="BE*TCB" and data.get("networkName")!="TotalEnergies": continue
        cp_match=next((x for x in data.get("chargePoints") or [] if str(x.get("id","")).lower()==str(row["externalId"]).lower()),None)
        if cp_match:
            matched={"poi":data,"chargePoint":cp_match}
            break
    tariff_results=[]
    if matched:
        for con in matched["chargePoint"].get("connectors") or []:
            cid=con.get("id")
            if not cid: continue
            ts,tp=get_json(TARIFF+"?"+urllib.parse.urlencode({"connectorId":cid}))
            tariff_results.append({"connector":con,"status":ts,"response":tp})
    results.append({
      "kind":kind,"nap":row,"collectionStatus":cs,"collectionCount":len(pois),
      "detailAttempts":detail_attempts,"matchedPoiId":matched["poi"].get("id") if matched else None,
      "matchedPoiName":matched["poi"].get("name") if matched else None,
      "matchedChargePoint":matched["chargePoint"] if matched else None,
      "tariffs":tariff_results
    })
    time.sleep(0.35)

def extract_energy(resp):
    data=(resp or {}).get("data") if isinstance(resp,dict) else None
    vals=[]
    if isinstance(data,dict):
        for el in data.get("elements") or []:
            for pc in el.get("priceComponents") or []:
                if pc.get("type")=="Energy":
                    vals.append({"price":pc.get("price"),"stepSize":pc.get("stepSize"),"vat":pc.get("vat")})
    return vals

summary=[]
for r in results:
    energy=[]
    for t in r["tariffs"]: energy += extract_energy(t.get("response"))
    nap_kwh=[p for p in r["nap"]["napPrices"] if p.get("priceType")=="pricePerKWh"]
    summary.append({
      "kind":r["kind"],"externalId":r["nap"]["externalId"],"locationId":r["nap"]["locationId"],
      "name":r["nap"]["name"],"powerW":r["nap"]["powerW"],"matchedPoiId":r["matchedPoiId"],
      "connectorCount":len(r["tariffs"]),"chargePlusEnergy":energy,"napPerKWh":nap_kwh
    })

payload={"sampleSize":len(results),"summary":summary,"results":results,
 "notes":["Pilot only; no canonical prices modified.","POI match requires TotalEnergies/BE*TCB plus exact external EVSE/chargePoint ID."]}
(OUT/"chargeplus-tariff-pilot-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(summary,ensure_ascii=False,indent=2))
