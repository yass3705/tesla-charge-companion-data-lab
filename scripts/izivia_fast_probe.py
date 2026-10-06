#!/usr/bin/env python3
"""Probe station-specific IZIVIA FAST prices exposed by IZIVIA's public map."""
import gzip
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = "https://fronts-map.izivia.com/api/"
NETWORK_ID = "67aa03c96b14f13fac39a81e"
FILTERS = {
    "chargingConnectors": [],
    "supportsAutocharge": False,
    "onlyTwentyFourSeven": False,
    "onlyAvailable": False,
    "capabilityTypes": [],
    "marketingNetworkIds": [NETWORK_ID],
}
HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "fr",
    "Content-Type": "application/json",
    "x-device-id": str(uuid.uuid4()),
    "User-Agent": "Mozilla/5.0 TCC-IZIVIA-FAST-public-audit",
}


def request(path, method="GET", body=None):
    data = None if body is None else json.dumps(body, separators=(",", ":")).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method=method)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                return exc.code, raw[:500]
        except Exception as exc:
            if attempt == 2:
                return 0, repr(exc)
        time.sleep(attempt + 1)


def distance_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(min(1, math.sqrt(a)))


def main():
    source = Path("reports/france/izivia/pan-national-pricing.json.gz")
    all_stations = json.load(gzip.open(source, "rt"))["stations"]
    fast = [s for s in all_stations if s.get("network") == "IZIVIA FAST"]
    wanted = os.environ.get("FAST_PROBE_IDS", "FRIZFPFAST422,FRIZFPFAST1,FRIZFPFAST100")
    selected = [s for s in fast if s["stationId"] in wanted.split(",")]
    if len(selected) != len(wanted.split(",")):
        raise RuntimeError("Missing requested FAST station in national inventory")
    status, markers = request("map/markers", "POST", {
        "square": {"centerLng": 2.2, "centerLat": 46.2, "zoom": 5}, "filters": FILTERS,
    })
    if status != 200 or not isinstance(markers, list):
        raise RuntimeError(f"Official FAST markers HTTP {status}: {str(markers)[:300]}")
    rows = []
    for station in selected:
        nearby = sorted(
            ((distance_m(station["lat"], station["lon"], m["pos"][1], m["pos"][0]), m)
             for m in markers if isinstance(m, dict) and len(m.get("pos") or []) == 2),
            key=lambda x: x[0],
        )[:4]
        candidates = []
        for distance, marker in nearby:
            if distance > 800:
                continue
            status, detail = request(f"charging-locations/{marker['id']}", "POST", {"filters": FILTERS})
            item = {"mapId": marker["id"], "distanceM": round(distance, 1), "detailStatus": status}
            if status == 200 and isinstance(detail, dict):
                item["name"] = detail.get("name")
                item["legacyId"] = detail.get("legacyId")
                item["firstStationEmipId"] = detail.get("firstStationEmipId")
                params = {}
                if detail.get("legacyId") is not None:
                    params["legacyId"] = detail["legacyId"]
                if detail.get("firstStationEmipId"):
                    params["stationEmipId"] = detail["firstStationEmipId"]
                if params:
                    path = f"charging-locations/{marker['id']}/pricing-info-items?" + urllib.parse.urlencode(params)
                    pst, pricing = request(path)
                    item["pricingStatus"] = pst
                    item["pricing"] = pricing
            candidates.append(item)
        rows.append({"stationId": station["stationId"], "stationName": station["name"], "nearest": candidates})
    report = {"capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "source": BASE, "fastInventoryStations": len(fast), "filteredMarkerCount": len(markers),
              "rows": rows}
    Path("out").mkdir(exist_ok=True)
    Path("out/izivia-fast-probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for row in rows:
        print(row["stationId"], row["stationName"])
        for item in row["nearest"]:
            direct = []
            for p in item.get("pricing") if isinstance(item.get("pricing"), list) else []:
                if p.get("itemType") == "charging_location":
                    direct += p.get("rawPricingInfos") or p.get("pricingInfos") or []
            print("  ", item["distanceM"], item.get("name"), item.get("legacyId"), item.get("firstStationEmipId"),
                  "HTTP", item.get("pricingStatus"), "DIRECT", repr(direct)[:1600])
    if not any(isinstance(i.get("pricing"), list) and i["pricing"] for r in rows for i in r["nearest"]):
        raise RuntimeError("No official FAST pricing captured")


if __name__ == "__main__":
    main()
