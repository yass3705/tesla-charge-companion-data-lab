#!/usr/bin/env python3
"""Collect exact AVIA Picoty France prices from Deftpower guest backend.

Uses the existing Picoty national station index as the coverage skeleton, locates
backend locations around each known station, requires exact FR*PY2 EVSE matches,
then calls simulate-pricing per matched connector. No tariff extrapolation.
"""
from __future__ import annotations
import json, os, subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode

API=os.environ.get("AVIA_API_BASE","https://pdefweushaapiam01.azure-api.net").rstrip("/")
TENANT=os.environ.get("AVIA_PICOTY_TENANT_ID","9439c762-3ce1-45fc-a9ea-a92ed5e06489")
KEY=os.environ.get("AVIA_APIM_SUBSCRIPTION_KEY","").strip()
INDEX=Path("data/national/avia_volt_picoty_station_index.json")
OUT=Path("data/operator_direct/avia_picoty_deftpower_exact_france.json")
TIMEOUT=int(os.environ.get("AVIA_TIMEOUT","40"))
SLEEP=float(os.environ.get("AVIA_SLEEP","0.12"))
DELTA=float(os.environ.get("AVIA_PICOTY_BBOX_DELTA","0.035"))

def norm(v):
    return "".join(ch for ch in str(v or "").upper() if ch.isalnum())

def request_json(method,path,query=None,body=None):
    url=API+path
    if query: url += "?" + urlencode(query, doseq=True)
    cmd=["curl","-sS","--fail-with-body","--max-time",str(TIMEOUT),
         "-X",method,
         "-H","accept: */*",
         "-H","content-type: application/json; charset=utf-8",
         "-H","accept-language: fr",
         "-H","x-app-platform: ios",
         "-H","x-app-version: 2.3.0",
         "-H","user-agent: RechargeEtVous/1 CFNetwork",
         "-H",f"ocp-apim-subscription-key: {KEY}",url]
    if body is not None:
        cmd += ["--data-binary",json.dumps(body,separators=(",",":"))]
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode!=0:
        raise RuntimeError((p.stderr or p.stdout or "curl failed")[:500])
    return json.loads(p.stdout)

def station_coords(raw):
    if isinstance(raw,(list,tuple)) and len(raw)>=2:
        lon,lat=raw[0],raw[1]
        return float(lat),float(lon)
    s=str(raw or "").strip().strip("[]")
    a=[x.strip() for x in s.split(",")]
    if len(a)>=2:
        return float(a[1]),float(a[0])
    raise ValueError("bad coordinates")

def map_candidates(lat,lon,filter_value=None):
    q={
      "latLongBottomLeft":f"{lat-DELTA:.6f},{lon-DELTA:.6f}",
      "latLongTopRight":f"{lat+DELTA:.6f},{lon+DELTA:.6f}",
      "evseTypes":"AC,DC,HPC",
      "connectorTypes":"TYPE2,CCS",
    }
    if filter_value:
        q["includeCpos"]=filter_value
    p=request_json("GET",f"/app-backend/v1/tenants/{TENANT}/map-locations",q)
    return p.get("locations") or []

def detail(lid):
    return request_json("GET",f"/app-backend/v1/tenants/{TENANT}/locations/{lid}")

def sim_body(evse,conn):
    start=datetime.now(timezone.utc).replace(microsecond=0)
    duration=1800
    return {
      "startTime":start.isoformat().replace("+00:00","Z"),
      "departureTime":(start+timedelta(seconds=duration)).isoformat().replace("+00:00","Z"),
      "energyConsumedInKwh":20,
      "baseOnChargeLimit":True,
      "chargingDurationInSeconds":duration,
      "expectedChargingDurationInSeconds":duration,
      "parkingDurationInSeconds":0,
      "chargingSpeedInKw":float(conn.get("max_electric_power") or 0),
      "locationIdentifiers":{"connectorId":conn["evseConnectorId"],"evseId":evse["id"]},
    }

def simulate(lid,evse,conn):
    return request_json("POST",f"/app-backend/v1/tenants/{TENANT}/locations/{lid}/simulate-pricing",body=sim_body(evse,conn))

def extract_price(sim):
    rows=sim.get("simulatedLocationPricing") or []
    if len(rows)!=1: return None
    r=rows[0]; p=r.get("pricePerKwh") or {}
    if p.get("amountInclVat") is None or not p.get("currency"): return None
    return {
      "currency":p.get("currency"),
      "pricePerKwhInclVat":p.get("amountInclVat"),
      "pricePerKwhExclVat":p.get("amountExclVat"),
      "vatPercentage":p.get("vatPercentage"),
      "tariffHasTimeBasedPrice":bool(r.get("tariffHasTimeBasedPrice")),
      "timeBasedPriceDimensions":r.get("timeBasedPriceDimensions") or [],
      "timeBasedFeeWindows":r.get("timeBasedFeeWindows") or [],
      "priceCategories":r.get("priceCategories") or [],
    }

def main():
    if not KEY:
        print("Missing AVIA_APIM_SUBSCRIPTION_KEY",file=sys.stderr); return 2
    src=json.loads(INDEX.read_text(encoding="utf-8"))
    stations=src.get("stations") or src.get("rows") or src.get("data") or []
    out=[]; failures=[]; matched_stations=0
    detail_cache={}
    for st in stations:
        sid=st.get("stationId")
        expected={norm(x) for x in (st.get("pdcIds") or []) if norm(x).startswith("FRPY2")}
        if not expected: continue
        try: lat,lon=station_coords(st.get("coordinatesRaw"))
        except Exception as e:
            failures.append({"stationId":sid,"stage":"coordinates","error":str(e)}); continue
        locs=[]
        for filt in ("FRPY2","PY2",None):
            try:
                locs=map_candidates(lat,lon,filt)
                if locs: break
            except Exception as e:
                if filt is None:
                    failures.append({"stationId":sid,"stage":"map","error":str(e)})
            time.sleep(SLEEP)
        station_hit=False
        for loc in locs:
            lid=loc.get("id")
            if not lid: continue
            try:
                d=detail_cache.get(lid)
                if d is None:
                    d=detail(lid); detail_cache[lid]=d
            except Exception as e:
                failures.append({"stationId":sid,"locationUuid":lid,"stage":"detail","error":str(e)}); continue
            for evse in d.get("evses") or []:
                eid=norm(evse.get("evseId"))
                if eid not in expected: continue
                station_hit=True
                for conn in evse.get("connectors") or []:
                    if not evse.get("id") or not conn.get("evseConnectorId"): continue
                    try:
                        price=extract_price(simulate(lid,evse,conn))
                        if not price:
                            failures.append({"stationId":sid,"evseId":evse.get("evseId"),"stage":"price","error":"missing_exact_price"})
                            continue
                        out.append({
                          "stationId":sid,
                          "stationName":st.get("stationName"),
                          "locationUuid":lid,
                          "locationName":d.get("locationName"),
                          "address":d.get("address"),
                          "postalCode":d.get("postalCode"),
                          "city":d.get("city"),
                          "coordinates":d.get("coordinates"),
                          "evseId":evse.get("evseId"),
                          "evseInternalId":evse.get("id"),
                          "connectorInternalId":conn.get("evseConnectorId"),
                          "connectorType":conn.get("evseCommonConnectorType"),
                          "powerKw":conn.get("max_electric_power"),
                          "tariffIds":sorted(set(conn.get("tariffIds") or [])),
                          "price":price,
                        })
                    except Exception as e:
                        failures.append({"stationId":sid,"evseId":evse.get("evseId"),"stage":"simulate","error":str(e)})
                    time.sleep(SLEEP)
        if station_hit: matched_stations += 1
    dedupe={}
    for row in out:
        dedupe[(norm(row.get("evseId")),row.get("connectorInternalId"))]=row
    out=list(dedupe.values())
    payload={
      "schemaVersion":1,"country":"FR","cpo":"AVIA Picoty","operatorId":"FR*PY2",
      "generatedAt":datetime.now(timezone.utc).isoformat(),
      "source":"Picoty Deftpower guest app backend simulate-pricing + existing national station index",
      "policy":{"guestSession":True,"exactEvseMatchRequired":True,"noTariffExtrapolation":True,
                "credentialsPersisted":False,"failClosed":True},
      "counts":{"indexStations":len(stations),"matchedStations":matched_stations,
                "pricedConnectors":len(out),"uniquePricedEvses":len({norm(x.get("evseId")) for x in out}),
                "failures":len(failures)},
      "connectors":sorted(out,key=lambda x:(x.get("stationId") or "",norm(x.get("evseId")),x.get("connectorInternalId") or "")),
      "failures":failures,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(payload["counts"],ensure_ascii=False))
    return 0 if out else 1

if __name__=="__main__":
    raise SystemExit(main())
