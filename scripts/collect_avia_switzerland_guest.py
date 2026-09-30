#!/usr/bin/env python3
"""
Collect exact AVIA VOLT Switzerland guest-session prices from the Deftpower app backend.

Secrets:
  AVIA_APIM_SUBSCRIPTION_KEY   required; never written to output/logs
Optional:
  AVIA_API_BASE                default app backend host
  AVIA_TENANT_ID               default AVIA VOLT tenant id
  AVIA_WORKERS                 bounded parallel location workers (default 8)
  AVIA_REQUEST_ATTEMPTS        retries for transient backend failures (default 3)

Outputs sanitized public JSON with no request headers or credentials.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit

API_BASE=os.environ.get("AVIA_API_BASE","https://pdefweushaapiam01.azure-api.net").rstrip("/")
TENANT_ID=os.environ.get("AVIA_TENANT_ID","fdcb995a-8234-42ed-826f-3f2c7499d7f8")
KEY=os.environ.get("AVIA_APIM_SUBSCRIPTION_KEY","").strip()
OUT=Path(os.environ.get("AVIA_OUT","data/switzerland/avia-guest-direct-tariffs.json"))
TIMEOUT=int(os.environ.get("AVIA_TIMEOUT","45"))
SLEEP=float(os.environ.get("AVIA_SLEEP","0.08"))
WORKERS=max(1,min(int(os.environ.get("AVIA_WORKERS","8")),12))
ATTEMPTS=max(1,min(int(os.environ.get("AVIA_REQUEST_ATTEMPTS","3")),5))
RESOLVE_IP=os.environ.get("AVIA_RESOLVE_IP","").strip()
TLS_INSECURE=os.environ.get("AVIA_TLS_INSECURE","0")=="1"

LAT_MIN,LAT_MAX=45.75,47.90
LON_MIN,LON_MAX=5.80,10.60
LAT_STEP=float(os.environ.get("AVIA_LAT_STEP","0.45"))
LON_STEP=float(os.environ.get("AVIA_LON_STEP","0.70"))

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def request_json(method,path,query=None,body=None):
    url=API_BASE+path
    if query:
        url += "?" + urlencode(query,doseq=True)
    host=urlsplit(API_BASE).hostname
    last=None
    for attempt in range(ATTEMPTS):
        cmd=["curl","-sS","--fail-with-body","--max-time",str(TIMEOUT)]
        if TLS_INSECURE:
            cmd.append("--insecure")
        if RESOLVE_IP:
            cmd += ["--resolve",f"{host}:443:{RESOLVE_IP}"]
        cmd += [
            "-X",method,
            "-H","accept: */*",
            "-H","content-type: application/json; charset=utf-8",
            "-H","accept-language: fr",
            "-H","x-app-platform: ios",
            "-H","x-app-version: 2.3.0",
            "-H","user-agent: AVIAVOLTSuisse/4614 CFNetwork",
            "-H",f"ocp-apim-subscription-key: {KEY}",
            url,
        ]
        if body is not None:
            cmd.extend(["--data-binary",json.dumps(body,separators=(",",":"))])
        p=subprocess.run(cmd,capture_output=True,text=True)
        if p.returncode==0:
            return json.loads(p.stdout)
        last=(p.stderr or p.stdout or "")[:500]
        if attempt+1<ATTEMPTS:
            time.sleep(0.6*(2**attempt))
    raise RuntimeError(f"curl error {path} after {ATTEMPTS} attempts: {last}")

def frange(a,b,step):
    x=a
    while x < b-1e-9:
        yield x,min(x+step,b)
        x += step

def map_task(args):
    la0,la1,lo0,lo1,status=args
    q={
        "latLongBottomLeft":f"{la0:.6f},{lo0:.6f}",
        "latLongTopRight":f"{la1:.6f},{lo1:.6f}",
        "evseTypes":"AC,DC,HPC",
        "connectorTypes":"TYPE2,CCS",
        "includeCpos":"CHAVI",
        "locationStatus":status,
    }
    try:
        payload=request_json("GET",f"/app-backend/v1/tenants/{TENANT_ID}/map-locations",q)
        rows=[loc for loc in (payload.get("locations") or []) if loc.get("partyId")=="AVI" and loc.get("id")]
        return rows,None
    except Exception as e:
        return [],{
            "bbox":[la0,lo0,la1,lo1],
            "locationStatus":status,
            "stage":"map",
            "error":str(e),
        }

def map_locations():
    tasks=[]
    for la0,la1 in frange(LAT_MIN,LAT_MAX,LAT_STEP):
        for lo0,lo1 in frange(LON_MIN,LON_MAX,LON_STEP):
            for status in ("AVAILABLE","NOT_AVAILABLE"):
                tasks.append((la0,la1,lo0,lo1,status))
    seen={}
    errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(WORKERS,8)) as ex:
        for rows,err in ex.map(map_task,tasks):
            if err:
                errors.append(err)
            for loc in rows:
                seen[loc["id"]]=loc
    return list(seen.values()),errors

def detail(location_id):
    return request_json("GET",f"/app-backend/v1/tenants/{TENANT_ID}/locations/{location_id}")

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
        "locationIdentifiers":{
            "connectorId":conn["evseConnectorId"],
            "evseId":evse["id"],
        },
    }

def simulate(location_id,evse,conn):
    return request_json(
        "POST",
        f"/app-backend/v1/tenants/{TENANT_ID}/locations/{location_id}/simulate-pricing",
        body=sim_body(evse,conn),
    )

def extract_price(sim):
    rows=sim.get("simulatedLocationPricing") or []
    if len(rows)!=1:
        return None,{"reason":"unexpected_simulated_location_count","count":len(rows)}
    r=rows[0]
    p=r.get("pricePerKwh") or {}
    if p.get("amountInclVat") is None or not p.get("currency"):
        return None,{"reason":"missing_price_per_kwh"}
    return {
        "currency":p.get("currency"),
        "pricePerKwhInclVat":p.get("amountInclVat"),
        "pricePerKwhExclVat":p.get("amountExclVat"),
        "vatPercentage":p.get("vatPercentage"),
        "tariffHasTimeBasedPrice":bool(r.get("tariffHasTimeBasedPrice")),
        "timeBasedPriceDimensions":r.get("timeBasedPriceDimensions") or [],
        "timeBasedFeeWindows":r.get("timeBasedFeeWindows") or [],
        "priceCategories":r.get("priceCategories") or [],
    },None

def process_location(loc):
    lid=loc["id"]
    out=[]
    failures=[]
    try:
        d=detail(lid)
    except Exception as e:
        return out,[{"locationId":lid,"stage":"detail","error":str(e)}]
    for evse in d.get("evses") or []:
        for conn in evse.get("connectors") or []:
            if not evse.get("id") or not conn.get("evseConnectorId"):
                continue
            try:
                sim=simulate(lid,evse,conn)
                price,err=extract_price(sim)
                if err:
                    failures.append({"locationId":lid,"evseId":evse.get("evseId"),"stage":"price","error":err})
                    continue
                out.append({
                    "locationUuid":lid,
                    "locationId":d.get("locationId"),
                    "locationName":d.get("locationName"),
                    "address":d.get("address"),
                    "postalCode":d.get("postalCode"),
                    "city":d.get("city"),
                    "coordinates":d.get("coordinates"),
                    "evseInternalId":evse.get("id"),
                    "evseId":evse.get("evseId"),
                    "connectorInternalId":conn.get("evseConnectorId"),
                    "connectorType":conn.get("evseCommonConnectorType"),
                    "powerKw":conn.get("max_electric_power"),
                    "tariffIds":sorted(set(conn.get("tariffIds") or [])),
                    "price":price,
                })
            except Exception as e:
                failures.append({"locationId":lid,"evseId":evse.get("evseId"),"stage":"simulate","error":str(e)})
            time.sleep(SLEEP)
    return out,failures

def main():
    if not KEY:
        print("Missing AVIA_APIM_SUBSCRIPTION_KEY",file=sys.stderr)
        return 2

    locations,map_errors=map_locations()
    out=[]
    failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures=[ex.submit(process_location,loc) for loc in locations]
        for fut in concurrent.futures.as_completed(futures):
            rows,errs=fut.result()
            out.extend(rows)
            failures.extend(errs)

    dedupe={}
    for row in out:
        dedupe[(row.get("evseId"),row.get("connectorInternalId"))]=row
    out=sorted(dedupe.values(),key=lambda x:(x.get("locationId") or "",x.get("evseId") or "",x.get("connectorInternalId") or ""))

    payload={
        "schemaVersion":1,
        "country":"CH",
        "cpo":"AVIA VOLT",
        "operatorId":"CH*AVI",
        "generatedAt":now_iso(),
        "source":"AVIA VOLT guest app backend simulate-pricing",
        "policy":{
            "guestSession":True,
            "exactConnectorOnly":True,
            "noTariffExtrapolation":True,
            "credentialsPersisted":False,
            "failClosed":True,
            "transientRequestRetries":ATTEMPTS,
            "boundedParallelWorkers":WORKERS,
        },
        "counts":{
            "mapLocations":len(locations),
            "pricedConnectors":len(out),
            "uniquePricedEvses":len({x.get("evseId") for x in out if x.get("evseId")}),
            "failures":len(failures),
            "mapErrors":len(map_errors),
        },
        "connectors":out,
        "failures":failures,
        "mapErrors":map_errors,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload["counts"],indent=2))
    if map_errors:
        print("First map errors:",json.dumps(map_errors[:3],ensure_ascii=False,indent=2))
    if failures:
        print("First connector failures:",json.dumps(failures[:3],ensure_ascii=False,indent=2))
    return 1 if not locations or not out else 0

if __name__=="__main__":
    raise SystemExit(main())
