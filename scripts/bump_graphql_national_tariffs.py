#!/usr/bin/env python3
"""Build a conservative national Bump direct-CPO tariff dataset from public Bump sources.

Sources:
1. Bump's own official IRVE dataset on data.gouv.fr defines the physical direct-CPO perimeter.
2. Bump's unauthenticated read-only GraphQL map search maps those stations to app EVSE/tariff groups.
3. Bump's anonymous tariff detail returns the driver-facing tariff description and price components.

No roaming locations, account data, sessions, payments or mutations are queried. Ambiguous station
matches are quarantined instead of assigned a price.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import time
import urllib.error
import urllib.request
import unicodedata
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bump_direct_inventory import DATASET_API, decode_csv, get_bytes, get_json, is_bump_operator, norm, resolve_csv_resource, station_key

ENDPOINT = "https://api.bump-charge.com/graphql"
UA = "TeslaChargeCompanionDataLab/1.0 (public Bump direct tariff harvester)"
OUT_GZ = Path("data/national/bump_direct_tariffs_graphql_france.json.gz")
OUT_REPORT = Path("reports/bump_direct_tariffs_graphql_france.md")
OUT_SUMMARY = Path("reports/bump/national_tariff_harvest_latest.json")
TILE_DEGREES = 0.50
TILE_MARGIN = 0.008
MAX_WORKERS = 4
MATCH_RADIUS_M = 120.0

PRICE_FIELDS = "currency amount formattedPrice"
VAT_PRICE_FIELDS = f"includingVat {{ {PRICE_FIELDS} }} excludingVat {{ {PRICE_FIELDS} }} vat"
MAP_QUERY = '''query TccNationalBumpMap($input: LocationSearchInput!) {
  chargePoints { locations { search(input: $input) {
    locations { id name isRoaming coordinates { latitude longitude }
      evses { id identifier isRoaming tariffGroup { id } }
    }
  } } }
}'''
TARIFF_QUERY = f'''query TccNationalBumpTariff($tariffGroupId: TariffGroupId!, $evseId: EvseId!, $hasAnonymous: Boolean) {{
  tariffs {{ detail(tariffGroupId: $tariffGroupId, evseId: $evseId, hasAnonymous: $hasAnonymous) {{
    id name currency type alternativeText alternativeUrl
    generatedDescription {{
      tariffGroupId tariffId quick short long isTariffChangingInTime parking
      quickDetail {{ priceType price {{ {VAT_PRICE_FIELDS} }} }}
      shortDetail {{
        flatFee {{ {VAT_PRICE_FIELDS} }}
        pricePerKWh {{ {VAT_PRICE_FIELDS} }}
        pricePerHour {{ {VAT_PRICE_FIELDS} }}
        minPrice {{ {VAT_PRICE_FIELDS} }}
      }}
    }}
  }} }}
}}'''


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fold(v: Any) -> str:
    s = unicodedata.normalize("NFKD", norm(v)).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.casefold().split())


def coords(v: Any) -> tuple[float, float] | None:
    s = norm(v)
    if not s:
        return None
    try:
        a = json.loads(s)
        if isinstance(a, list) and len(a) >= 2:
            lon, lat = float(a[0]), float(a[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    except Exception:
        pass
    return None


def suffix(v: Any) -> str:
    s = norm(v)
    m = re.search(r"([0-9]+)$", s)
    return m.group(1) if m else fold(s)


def distance_m(a: tuple[float,float], b: tuple[float,float]) -> float:
    lat1, lon1 = a; lat2, lon2 = b
    dy = (lat2-lat1) * 111_320.0
    dx = (lon2-lon1) * 111_320.0 * math.cos(math.radians((lat1+lat2)/2.0))
    return math.hypot(dx,dy)


def post(query: str, variables: dict[str, Any], attempts: int = 4) -> tuple[int | str, dict[str, Any]]:
    body = json.dumps({"query": query, "variables": variables}).encode()
    for i in range(attempts):
        req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={"User-Agent": UA, "Accept":"application/json", "Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                obj = json.load(r)
                return int(r.status), obj if isinstance(obj, dict) else {}
        except urllib.error.HTTPError as e:
            try: obj = json.loads(e.read(500_000))
            except Exception: obj = {}
            if int(e.code) not in (429, 500, 502, 503, 504) or i == attempts-1:
                return int(e.code), obj if isinstance(obj, dict) else {}
        except Exception as e:
            if i == attempts-1:
                return "network_error", {"errorType": type(e).__name__}
        time.sleep(0.7 * (2**i))
    return "network_error", {}


def gql_errors(obj: dict[str,Any]) -> list[str]:
    return [str(x.get("message"))[:300] for x in (obj.get("errors") or []) if isinstance(x, dict)]


def official_stations(limit: int | None = None) -> tuple[list[dict[str,Any]], dict[str,Any]]:
    dataset = get_json(DATASET_API); resource = resolve_csv_resource(dataset)
    rows, headers = decode_csv(get_bytes(str(resource.get("url") or resource.get("latest"))))
    rows = [r for r in rows if is_bump_operator(r.get("nom_operateur")) and coords(r.get("coordonneesXY"))]
    grouped: dict[str,list[dict[str,str]]] = defaultdict(list)
    for r in rows: grouped[station_key(r)].append(r)
    stations=[]
    for key, rs in grouped.items():
        first=rs[0]; c=coords(first.get("coordonneesXY"))
        if not c: continue
        points=[]
        for r in rs:
            iid=norm(r.get("id_pdc_itinerance"))
            points.append({"idPdcItinerance":iid,"suffix":suffix(iid),"powerKw":norm(r.get("puissance_nominale"))})
        stations.append({"stationKey":key,"idStationItinerance":norm(first.get("id_station_itinerance")),"name":norm(first.get("nom_station")),"address":norm(first.get("adresse_station")),"latitude":c[0],"longitude":c[1],"points":points})
    stations.sort(key=lambda s:(s["latitude"],s["longitude"],s["stationKey"]))
    if limit: stations=stations[:limit]
    meta={"datasetApi":DATASET_API,"datasetId":dataset.get("id"),"resourceId":resource.get("id"),"resourceModified":resource.get("last_modified") or resource.get("modified"),"headers":headers}
    return stations, meta


def tile_key(lat: float, lon: float) -> tuple[int,int]:
    return math.floor(lat/TILE_DEGREES), math.floor(lon/TILE_DEGREES)


def build_tiles(stations: list[dict[str,Any]]) -> list[dict[str,Any]]:
    grouped: dict[tuple[int,int],list[dict[str,Any]]] = defaultdict(list)
    for s in stations: grouped[tile_key(s["latitude"],s["longitude"])].append(s)
    tiles=[]
    for key, members in grouped.items():
        lats=[x["latitude"] for x in members]; lons=[x["longitude"] for x in members]
        zone={"topLeft":{"latitude":max(lats)+TILE_MARGIN,"longitude":min(lons)-TILE_MARGIN},"bottomRight":{"latitude":min(lats)-TILE_MARGIN,"longitude":max(lons)+TILE_MARGIN}}
        tiles.append({"key":f"{key[0]}:{key[1]}","zone":zone,"officialStationCount":len(members)})
    return tiles


def fetch_tile(tile: dict[str,Any]) -> dict[str,Any]:
    status,obj=post(MAP_QUERY,{"input":{"searchZone":tile["zone"],"isRoaming":False}})
    locs=((((obj.get("data") or {}).get("chargePoints") or {}).get("locations") or {}).get("search") or {}).get("locations") if isinstance(obj,dict) else []
    safe=[]
    for loc in locs or []:
        if not isinstance(loc,dict) or loc.get("isRoaming") is True: continue
        c=loc.get("coordinates") if isinstance(loc.get("coordinates"),dict) else {}
        if not isinstance(c.get("latitude"),(int,float)) or not isinstance(c.get("longitude"),(int,float)): continue
        evses=[]
        for e in loc.get("evses") or []:
            if not isinstance(e,dict) or e.get("isRoaming") is True: continue
            tg=e.get("tariffGroup") if isinstance(e.get("tariffGroup"),dict) else {}
            evses.append({"evseId":e.get("id"),"identifier":norm(e.get("identifier")),"suffix":suffix(e.get("identifier")),"tariffGroupId":tg.get("id")})
        safe.append({"locationId":loc.get("id"),"name":norm(loc.get("name")),"latitude":float(c["latitude"]),"longitude":float(c["longitude"]),"evses":evses})
    return {"key":tile["key"],"status":status,"errors":gql_errors(obj),"locations":safe}


def match_station(s: dict[str,Any], locations: list[dict[str,Any]]) -> dict[str,Any]:
    official_suffixes={p["suffix"] for p in s["points"] if p["suffix"]}
    candidates=[]
    for loc in locations:
        d=distance_m((s["latitude"],s["longitude"]),(loc["latitude"],loc["longitude"]))
        if d > MATCH_RADIUS_M: continue
        api_suffixes={e["suffix"] for e in loc.get("evses") or [] if e.get("suffix")}
        overlap=official_suffixes & api_suffixes
        name_equal=fold(s["name"])==fold(loc["name"])
        candidates.append((len(overlap),name_equal,d,loc,overlap))
    candidates.sort(key=lambda x:(-x[0],-int(x[1]),x[2]))
    if not candidates:
        return {"status":"unmatched","reason":"no_public_location_within_radius"}
    best=candidates[0]
    tied=[x for x in candidates if x[0]==best[0] and x[1]==best[1] and abs(x[2]-best[2])<2]
    accepted=False; method=None
    if best[0] > 0 and len(tied)==1:
        accepted=True; method="evse_suffix_plus_geo"
    elif best[1] and best[2] <= 20 and len(tied)==1:
        accepted=True; method="exact_name_plus_geo"
    if not accepted:
        return {"status":"ambiguous","reason":"no_unique_strong_match","candidateCount":len(candidates),"bestDistanceMeters":round(best[2],1),"bestSuffixOverlap":best[0],"bestNameEqual":best[1]}
    loc=best[3]
    evse_by_suffix={e["suffix"]:e for e in loc.get("evses") or [] if e.get("suffix")}
    mapped=[]
    for p in s["points"]:
        e=evse_by_suffix.get(p["suffix"])
        mapped.append({**p,"appEvseId":e.get("evseId") if e else None,"appEvseIdentifier":e.get("identifier") if e else None,"tariffGroupId":e.get("tariffGroupId") if e else None,"mapped":bool(e)})
    return {"status":"matched","method":method,"distanceMeters":round(best[2],1),"locationId":loc.get("locationId"),"locationName":loc.get("name"),"points":mapped}


def price_amount(v: Any) -> float | None:
    if not isinstance(v,dict): return None
    inc=v.get("includingVat") if isinstance(v.get("includingVat"),dict) else None
    a=inc.get("amount") if inc else None
    return float(a) if isinstance(a,(int,float)) else None


def normalize_tariff(t: dict[str,Any] | None) -> dict[str,Any] | None:
    if not isinstance(t,dict): return None
    gd=t.get("generatedDescription") if isinstance(t.get("generatedDescription"),dict) else {}
    sd=gd.get("shortDetail") if isinstance(gd.get("shortDetail"),dict) else {}
    qd=gd.get("quickDetail") if isinstance(gd.get("quickDetail"),dict) else {}
    return {"tariffId":t.get("id"),"name":t.get("name"),"currency":t.get("currency"),"type":t.get("type"),"energyEurPerKwh":price_amount(sd.get("pricePerKWh")),"timeEurPerHour":price_amount(sd.get("pricePerHour")),"flatFeeEur":price_amount(sd.get("flatFee")),"minPriceEur":price_amount(sd.get("minPrice")),"quickPriceType":qd.get("priceType"),"quickPriceEur":price_amount(qd.get("price")),"isTariffChangingInTime":gd.get("isTariffChangingInTime"),"parkingText":gd.get("parking"),"quick":gd.get("quick"),"short":gd.get("short"),"long":gd.get("long")}


def fetch_tariff(pair: tuple[str,str]) -> tuple[tuple[str,str],dict[str,Any]]:
    group,evse=pair
    status,obj=post(TARIFF_QUERY,{"tariffGroupId":group,"evseId":evse,"hasAnonymous":True})
    raw=(((obj.get("data") or {}).get("tariffs") or {}).get("detail")) if isinstance(obj,dict) else None
    return pair,{"status":status,"errors":gql_errors(obj),"tariff":normalize_tariff(raw)}


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int,default=0); args=ap.parse_args()
    stations,source=official_stations(args.limit or None); tiles=build_tiles(stations)
    print(f"officialStations={len(stations)} tiles={len(tiles)}")

    tile_results=[]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures={ex.submit(fetch_tile,t):t for t in tiles}
        for i,f in enumerate(as_completed(futures),1):
            tile_results.append(f.result())
            if i%25==0 or i==len(futures): print(f"mapTiles={i}/{len(futures)}")
    locations_by_id={}
    for tr in tile_results:
        for loc in tr["locations"]: locations_by_id[str(loc["locationId"])]=loc
    locations=list(locations_by_id.values())

    # Match against all returned direct locations; geographic radius keeps the comparison bounded.
    records=[]
    for s in stations:
        m=match_station(s,locations)
        records.append({**s,"match":m})
    counts=Counter(r["match"]["status"] for r in records)
    matched=counts.get("matched",0)
    print(f"matched={matched}/{len(records)} ambiguous={counts.get('ambiguous',0)} unmatched={counts.get('unmatched',0)}")
    if stations and matched/len(stations) < 0.50:
        raise RuntimeError("Bump public-map match rate below 50%; refusing national tariff harvest")

    pairs={}
    for r in records:
        if r["match"].get("status")!="matched": continue
        for p in r["match"].get("points") or []:
            if p.get("tariffGroupId") and p.get("appEvseId"):
                pairs.setdefault(str(p["tariffGroupId"]),(str(p["tariffGroupId"]),str(p["appEvseId"])))
    tariff_results={}
    pair_values=list(pairs.values())
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures={ex.submit(fetch_tariff,p):p for p in pair_values}
        for i,f in enumerate(as_completed(futures),1):
            pair,res=f.result(); tariff_results[pair[0]]=res
            if i%50==0 or i==len(futures): print(f"tariffGroups={i}/{len(futures)}")

    station_price_count=0; point_price_count=0; changing_count=0
    for r in records:
        priced=False
        if r["match"].get("status")=="matched":
            for p in r["match"].get("points") or []:
                tr=tariff_results.get(str(p.get("tariffGroupId"))) if p.get("tariffGroupId") else None
                p["tariff"]=(tr or {}).get("tariff")
                if p["tariff"]:
                    point_price_count+=1; priced=True
                    if p["tariff"].get("isTariffChangingInTime"): changing_count+=1
        if priced: station_price_count+=1

    unique_tariffs={}
    for gid,res in tariff_results.items():
        t=res.get("tariff")
        if t: unique_tariffs[gid]=t

    payload={"schemaVersion":"1.0.0","dataset":"bump-direct-public-graphql-tariffs-france","generatedAt":now_iso(),"operator":"Bump","country":"FR","scope":{"directCpoOnly":True,"roamingIncluded":False,"anonymousDriverTariff":True,"ambiguousMatchesPriced":False},"source":source,"method":{"officialInventory":"Bump IRVE data.gouv","mapApi":"Bump public GraphQL chargePoints.locations.search isRoaming=false","tariffApi":"Bump public GraphQL tariffs.detail hasAnonymous=true","tileDegrees":TILE_DEGREES,"matchRadiusMeters":MATCH_RADIUS_M,"maxWorkers":MAX_WORKERS},"counts":{"officialStations":len(stations),"officialPoints":sum(len(s["points"]) for s in stations),"mapTiles":len(tiles),"publicDirectLocations":len(locations),"matchedStations":matched,"ambiguousStations":counts.get("ambiguous",0),"unmatchedStations":counts.get("unmatched",0),"uniqueTariffGroupsRequested":len(pair_values),"uniqueTariffGroupsWithTariff":len(unique_tariffs),"stationsWithTariff":station_price_count,"pointsWithTariff":point_price_count,"timeChangingPricedPoints":changing_count},"tariffGroups":unique_tariffs,"stations":records}
    rendered=json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n"
    OUT_GZ.parent.mkdir(parents=True,exist_ok=True); OUT_GZ.write_bytes(gzip.compress(rendered.encode(),compresslevel=9,mtime=0))
    OUT_SUMMARY.parent.mkdir(parents=True,exist_ok=True); OUT_SUMMARY.write_text(json.dumps({"generatedAt":payload["generatedAt"],"counts":payload["counts"],"failedMapTiles":[{"key":x["key"],"status":x["status"],"errors":x["errors"]} for x in tile_results if x["status"]!=200 or x["errors"]],"tariffGroupsWithoutTariff":[gid for gid,res in tariff_results.items() if not res.get("tariff")]},ensure_ascii=False,indent=2)+"\n")
    c=payload["counts"]
    lines=["# Bump direct France — public GraphQL tariff harvest","",f"Generated: `{payload['generatedAt']}`","","## Coverage","",f"- Official Bump stations: **{c['officialStations']}**",f"- Official Bump charge points: **{c['officialPoints']}**",f"- Stations matched to Bump public map: **{c['matchedStations']}**",f"- Ambiguous stations quarantined: **{c['ambiguousStations']}**",f"- Unmatched stations: **{c['unmatchedStations']}**",f"- Unique tariff groups queried: **{c['uniqueTariffGroupsRequested']}**",f"- Unique tariff groups with an anonymous tariff: **{c['uniqueTariffGroupsWithTariff']}**",f"- Stations with a usable tariff object: **{c['stationsWithTariff']}**",f"- Charge points with a usable tariff object: **{c['pointsWithTariff']}**","","## Safety rule","","Only Bump-operated, non-roaming locations matched to Bump's official IRVE inventory are priced. Ambiguous matches are retained for review but never given an inferred price.",""]
    OUT_REPORT.parent.mkdir(parents=True,exist_ok=True); OUT_REPORT.write_text("\n".join(lines))
    print(json.dumps(payload["counts"],indent=2))


if __name__=="__main__": main()
