#!/usr/bin/env python3
"""Build the UK IONITY Direct station/connector tariff map.

Reuses the validated TCC IONITY Direct method without modifying the existing
France/Italy producer. Only locations operated by IONITY_CPO, hydrated as GB,
with public IONITY DIRECT GBP/kWh prices are published.
"""
from __future__ import annotations
import gzip, hashlib, json, math, time, urllib.error, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_URL="https://adhoc-bff.ionity.cloud/api"
STATIC_URL=f"{BASE_URL}/v1/location/static"
DETAIL_URL=f"{BASE_URL}/v3/location/{{uuid}}"
CANONICAL_CPO="IONITY_CPO"
TARGET_COUNTRY="GB"
COUNTRY_BOUNDS=(49.5,-8.8,61.2,2.2)
APP_FEATURE_VERSION="v2.428.0"
OUT=Path("data/national/ionity_direct_stations_uk.json.gz")
HEADERS={
 "User-Agent":"IONITY/2.428.0 (Android; TeslaChargeCompanion data validation)",
 "Accept":"application/json",
 "x-adhoc-platform":"ANDROID_V2",
 "x-adhoc-app-feature-version":APP_FEATURE_VERSION,
 "x-adhoc-device-country":"GB",
 "x-adhoc-device-language":"en",
}

def now_iso():
 return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def request_json(url, attempts=4):
 last=None
 for attempt in range(attempts):
  try:
   req=urllib.request.Request(url,headers=HEADERS,method="GET")
   with urllib.request.urlopen(req,timeout=35) as r:
    if int(getattr(r,"status",200))!=200: raise RuntimeError(f"unexpected HTTP status for {url}")
    return json.loads(r.read().decode("utf-8"))
  except (OSError,ValueError,urllib.error.HTTPError) as exc:
   last=exc
   if attempt+1<attempts: time.sleep(0.75*(2**attempt))
 raise RuntimeError(f"IONITY request failed after {attempts} attempts: {url}: {last}")

def finite(v):
 try: n=float(v)
 except (TypeError,ValueError): return None
 return n if math.isfinite(n) else None

def parse_connector(raw):
 p=raw.get("adhocPrice") or {}
 amount=finite(p.get("amount")); watts=finite(raw.get("maxPower"))
 if (str(p.get("name") or "").strip().upper()!="IONITY DIRECT"
  or str(p.get("unit") or "").strip().lower()!="kwh"
  or str(p.get("currency") or "").strip().upper()!="GBP"
  or amount is None or amount<=0 or watts is None or watts<=0):
  return None
 ctype=str(raw.get("type") or "").strip()
 return {
  "uuid":str(raw.get("uuid") or "").strip(),
  "number":raw.get("number"),
  "physicalReference":str(raw.get("physicalReference") or "").strip(),
  "sourceEvseId":str(raw.get("sourceEvseId") or "").strip(),
  "type":ctype,
  "kind":"AC" if ctype.lower() in {"type 2","type2"} else "DC",
  "powerKw":round(watts/1000.0,3),
  "pricePerKwhGbp":round(amount,6),
 }

def hydrate(static):
 uuid=str(static.get("uuid") or "").strip()
 if not uuid: raise ValueError("IONITY static location without UUID")
 d=request_json(DETAIL_URL.format(uuid=uuid))
 if static.get("cpoIdentifier")!=CANONICAL_CPO or d.get("cpoIdentifier")!=CANONICAL_CPO: return None
 if str(d.get("country") or "").strip().upper()!=TARGET_COUNTRY: return None
 if str(static.get("uuid") or "")!=str(d.get("uuid") or ""): raise ValueError(f"UUID mismatch {uuid}")
 lat=finite(d.get("latitude")); lon=finite(d.get("longitude"))
 if lat is None or lon is None: raise ValueError(f"invalid coordinates {uuid}")
 raw=d.get("connectors") or []
 connectors=[x for c in raw if (x:=parse_connector(c))]
 if not connectors: raise ValueError(f"GB IONITY location has no usable Direct GBP price: {uuid}")
 return {
  "uuid":uuid,
  "locationId":str(static.get("locationId") or ""),
  "cpoIdentifier":CANONICAL_CPO,
  "name":str(d.get("name") or static.get("name") or "").strip(),
  "address":str(d.get("address") or "").strip(),
  "postalCode":str(d.get("postalCode") or "").strip(),
  "city":str(d.get("city") or "").strip(),
  "country":"GB",
  "latitude":lat,"longitude":lon,
  "connectors":sorted(connectors,key=lambda x:(x["kind"],x["powerKw"],x["number"] or 0,x["uuid"])),
  "connectorCount":len(raw),
  "pricedConnectorCount":len(connectors),
  "unpricedConnectorCount":len(raw)-len(connectors),
 }

def main():
 static_payload=request_json(STATIC_URL)
 all_locs=static_payload.get("locations") or []
 if len(all_locs)<500: raise RuntimeError(f"static inventory unexpectedly small: {len(all_locs)}")
 operated=[x for x in all_locs if x.get("cpoIdentifier")==CANONICAL_CPO]
 south,west,north,east=COUNTRY_BOUNDS
 candidates=[]
 for x in operated:
  lat=finite(x.get("latitude")); lon=finite(x.get("longitude"))
  if lat is not None and lon is not None and south<=lat<=north and west<=lon<=east: candidates.append(x)
 if len(candidates)<10: raise RuntimeError(f"UK geographic candidate inventory unexpectedly small: {len(candidates)}")
 locs=[]
 with ThreadPoolExecutor(max_workers=16) as pool:
  fs={pool.submit(hydrate,x):x for x in candidates}
  for f in as_completed(fs):
   v=f.result()
   if v: locs.append(v)
 if not locs: raise RuntimeError("UK IONITY operated result empty")
 locs=sorted(locs,key=lambda x:(x["name"].lower(),x["uuid"]))
 conns=[c for l in locs for c in l["connectors"]]
 prices=Counter(f"{c['pricePerKwhGbp']:.3f}" for c in conns)
 payload={
  "schemaVersion":"1.0.0","dataset":"ionity-direct-operated-stations-gb",
  "generatedAt":now_iso(),"operator":"IONITY","country":"GB",
  "scope":{"requiredCpoIdentifier":CANONICAL_CPO,"onlyOperatedLocations":True,
   "tariffFamily":"IONITY DIRECT","subscriberTariffsIncluded":False,
   "roamingTariffsIncluded":False,"priceGranularity":"connector","currency":"GBP"},
  "source":{"staticUrl":STATIC_URL,"detailUrlTemplate":DETAIL_URL,
   "platform":HEADERS["x-adhoc-platform"],"appFeatureVersion":APP_FEATURE_VERSION},
  "counts":{"staticLocationCount":len(all_locs),"operatedStaticLocationCount":len(operated),
   "geographicCandidateLocationCount":len(candidates),"ukLocationCount":len(locs),
   "ukConnectorCount":len(conns),"ukUnpricedConnectorCount":sum(x["unpricedConnectorCount"] for x in locs),
   "priceCounts":dict(sorted(prices.items()))},
  "locations":locs,
 }
 OUT.parent.mkdir(parents=True,exist_ok=True)
 rendered=json.dumps(payload,ensure_ascii=False,indent=2)+"\n"
 OUT.write_bytes(gzip.compress(rendered.encode("utf-8"),compresslevel=9,mtime=0))
 digest=hashlib.sha256(rendered.encode()).hexdigest()
 print(json.dumps(payload["counts"],indent=2))
 print(f"IONITY Direct GB: {len(locs)} locations / {len(conns)} priced connectors / sha256={digest}")

if __name__=="__main__": main()
