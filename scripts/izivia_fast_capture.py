#!/usr/bin/env python3
"""Capture exact IZIVIA FAST direct tariffs from the public IZIVIA station map."""
import concurrent.futures
import gzip
import json
import re
import time
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

from izivia_fast_probe import BASE, FILTERS, distance_m, request

SOURCE = Path("reports/france/izivia/pan-national-pricing.json.gz")
OUTPUT = Path("out/izivia-fast-national-capture.json.gz")
SUMMARY = Path("out/izivia-fast-national-summary.json")


def official_code(station_id):
    match = re.fullmatch(r"FRIZFPFAST(\d+)", station_id or "")
    return match.group(1) if match else None


def map_code(legacy_id):
    match = re.fullmatch(r"FR\*SOD\*P\*FAST\*(\d+)\*[^*]*\*[^*]*\*[^*]*", legacy_id or "")
    return match.group(1) if match else None


def direct_texts(items):
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict) or item.get("itemType") != "charging_location":
            continue
        for text in item.get("rawPricingInfos") or item.get("pricingInfos") or []:
            if isinstance(text, str) and text.strip() and text not in out:
                out.append(text)
    return out


def main():
    stations = json.load(gzip.open(SOURCE, "rt"))["stations"]
    fast = {official_code(s["stationId"]): s for s in stations if s.get("network") == "IZIVIA FAST"}
    if len(fast) < 600 or None in fast:
        raise RuntimeError(f"Unexpected FAST national inventory size or identifier: {len(fast)}")
    status, markers = request("map/markers", "POST", {
        "square": {"centerLng": 2.2, "centerLat": 46.2, "zoom": 5}, "filters": FILTERS,
    })
    if status != 200 or not isinstance(markers, list):
        raise RuntimeError(f"Official map markers HTTP {status}: {str(markers)[:200]}")

    def detail_one(marker):
        mid = marker.get("id")
        pos = marker.get("pos")
        if not mid or not isinstance(pos, list) or len(pos) != 2:
            return None
        st, detail = request(f"charging-locations/{mid}", "POST", {"filters": FILTERS})
        if st != 200 or not isinstance(detail, dict):
            return {"mapId": mid, "status": st}
        code = map_code(detail.get("legacyId"))
        return {"mapId": mid, "status": st, "pos": pos, "code": code, "detail": detail}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        details = list(pool.map(detail_one, markers))
    by_code = defaultdict(list)
    detail_failures = []
    for row in details:
        if not row:
            continue
        if row.get("status") != 200:
            detail_failures.append({"mapId": row["mapId"], "status": row["status"]})
        elif row.get("code"):
            by_code[row["code"]].append(row)

    def price_one(item):
        code, station = item
        candidates = by_code.get(code, [])
        result = {"stationId": station["stationId"], "name": station["name"], "address": station["address"],
                  "lat": station["lat"], "lon": station["lon"], "pdcIds": station["pdcIds"],
                  "candidateCount": len(candidates)}
        if not candidates:
            result["status"] = "missing_map_station"
            return result
        measured = sorted(
            ((distance_m(station["lat"], station["lon"], c["pos"][1], c["pos"][0]), c) for c in candidates),
            key=lambda x: x[0],
        )
        if len(measured) != 1 or measured[0][0] > 100:
            result["status"] = "ambiguous_or_distant_map_station"
            result["candidates"] = [{"mapId": c["mapId"], "distanceM": round(d, 1)} for d, c in measured]
            return result
        dist, match = measured[0]
        detail = match["detail"]
        result.update({"mapId": match["mapId"], "distanceM": round(dist, 1),
                       "legacyId": detail.get("legacyId"), "mapName": detail.get("name"),
                       "mapDetail": detail})
        params = {}
        if detail.get("legacyId") is not None:
            params["legacyId"] = detail["legacyId"]
        if detail.get("firstStationEmipId"):
            params["stationEmipId"] = detail["firstStationEmipId"]
        if not params:
            result["status"] = "missing_pricing_identifiers"
            return result
        path = f"charging-locations/{match['mapId']}/pricing-info-items?" + urllib.parse.urlencode(params)
        st, pricing = request(path)
        result["pricingStatus"] = st
        if st != 200 or not isinstance(pricing, list):
            result["status"] = "pricing_request_failed"
            return result
        result["directRawPricing"] = direct_texts(pricing)
        result["pricingItems"] = pricing
        result["status"] = "direct_price_published" if result["directRawPricing"] else "no_direct_price"
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(price_one, sorted(fast.items(), key=lambda x: int(x[0]))))
    texts = Counter(text for row in rows for text in row.get("directRawPricing", []))
    summary = {
        "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": BASE, "network": "IZIVIA FAST", "networkId": "67aa03c96b14f13fac39a81e",
        "inventoryStations": len(fast), "mapMarkers": len(markers), "mapFastCodes": len(by_code),
        "statuses": dict(Counter(row["status"] for row in rows)),
        "uniqueDirectTexts": len(texts),
        "directTexts": [{"count": n, "text": t} for t, n in texts.most_common()],
        "detailFailureCount": len(detail_failures),
        "detailFailures": detail_failures[:50],
        "unmatchedMapCodes": sorted(set(by_code) - set(fast)),
        "exceptions": [{"stationId": row["stationId"], "status": row["status"]} for row in rows if row["status"] != "direct_price_published"],
    }
    dole = next(row for row in rows if row["stationId"] == "FRIZFPFAST422")
    summary["doleMapDetail"] = dole.get("mapDetail")
    summary["exceptionDetails"] = [
        {"stationId": row["stationId"], "name": row["name"], "candidates": row.get("candidates")}
        for row in rows if row["status"] != "direct_price_published"
    ]
    OUTPUT.parent.mkdir(exist_ok=True)
    with gzip.open(OUTPUT, "wt", encoding="utf-8") as file:
        json.dump({"summary": summary, "stations": rows}, file, ensure_ascii=False, separators=(",", ":"))
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("detailFailures", "exceptions", "unmatchedMapCodes", "doleMapDetail", "exceptionDetails")}, ensure_ascii=False, indent=2))
    print("DOLE_DETAIL", json.dumps(dole.get("mapDetail"), ensure_ascii=False)[:12000])
    print("EXCEPTION_DETAILS", json.dumps(summary["exceptionDetails"], ensure_ascii=False)[:16000])
    print("EXCEPTIONS", json.dumps(summary["exceptions"], ensure_ascii=False))
    if len(rows) != len(fast):
        raise RuntimeError("National FAST capture lost station rows")


if __name__ == "__main__":
    main()
