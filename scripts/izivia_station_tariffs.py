#!/usr/bin/env python3
"""Watch direct IZIVIA FAST and Express station cards on the official map."""

import argparse
import concurrent.futures
import hashlib
import json
import re
import time
import urllib.parse
from collections import Counter
from pathlib import Path

from izivia_fast_probe import BASE, request

NETWORKS = {
    "IZIVIA FAST": {"id": "67aa03c96b14f13fac39a81e", "legacy": r"FR\*SOD\*P\*FAST\*(\d+)\*"},
    "IZIVIA Express": {"id": "67ab64d36b14f13fac39a82d", "legacy": r"FR\*SOD\*P\*OAZS\*(\d+)\*"},
}
FILTERS = {
    "chargingConnectors": [], "supportsAutocharge": False,
    "onlyTwentyFourSeven": False, "onlyAvailable": False,
    "capabilityTypes": [], "marketingNetworkIds": [],
}


def direct_texts(items):
    if not isinstance(items, list):
        raise ValueError("Pricing response is not a list")
    texts = []
    for item in items:
        if not isinstance(item, dict) or item.get("itemType") != "charging_location":
            continue
        values = item.get("rawPricingInfos") or item.get("pricingInfos") or []
        if not isinstance(values, list):
            raise ValueError("Direct pricing text is not a list")
        for value in values:
            if isinstance(value, str):
                value = " ".join(value.split())
                if value and value not in texts:
                    texts.append(value)
    return texts


def connector_stats(detail):
    out = []
    for row in detail.get("chargingConnectorsStats") or []:
        if not isinstance(row, dict):
            continue
        out.append({
            "standard": row.get("standard"),
            "maxPowerInW": row.get("maxPowerInW"),
            "totalConnectorCount": row.get("totalConnectorCount"),
        })
    return sorted(out, key=lambda x: (str(x["standard"]), str(x["maxPowerInW"])))


def capture_network(network, spec, workers, minimum=None):
    filters = {**FILTERS, "marketingNetworkIds": [spec["id"]]}
    status, markers = request("map/markers", "POST", {
        "square": {"centerLng": 2.2, "centerLat": 46.2, "zoom": 5}, "filters": filters,
    })
    if status != 200 or not isinstance(markers, list):
        raise RuntimeError(f"{network}: marker request failed (HTTP {status})")
    if minimum is None:
        minimum = 600 if network == "IZIVIA FAST" else 150
    if len(markers) < minimum:
        raise RuntimeError(f"{network}: only {len(markers)} markers, expected at least {minimum}")
    ids = [m.get("id") for m in markers if isinstance(m, dict)]
    if len(ids) != len(markers) or len(set(ids)) != len(ids) or None in ids:
        raise RuntimeError(f"{network}: missing or duplicate marker IDs")

    def capture_one(marker):
        map_id = marker["id"]
        status, detail = request(f"charging-locations/{map_id}", "POST", {"filters": filters})
        if status != 200 or not isinstance(detail, dict):
            return {"mapId": map_id, "status": "detail_failed", "httpStatus": status}
        legacy_id = detail.get("legacyId") or ""
        code = re.search(spec["legacy"], legacy_id)
        if not code:
            return {"mapId": map_id, "status": "unexpected_network", "legacyId": legacy_id}
        params = {}
        if detail.get("legacyId") is not None:
            params["legacyId"] = detail["legacyId"]
        if detail.get("firstStationEmipId"):
            params["stationEmipId"] = detail["firstStationEmipId"]
        if not params:
            return {"mapId": map_id, "status": "missing_pricing_identifiers", "legacyId": legacy_id}
        path = f"charging-locations/{map_id}/pricing-info-items?" + urllib.parse.urlencode(params)
        status, pricing = request(path)
        if status != 200 or not isinstance(pricing, list):
            return {"mapId": map_id, "status": "pricing_failed", "httpStatus": status,
                    "legacyId": legacy_id}
        try:
            texts = direct_texts(pricing)
        except ValueError:
            return {"mapId": map_id, "status": "invalid_pricing", "legacyId": legacy_id}
        return {
            "mapId": map_id, "legacyId": legacy_id, "code": code.group(1),
            "name": detail.get("name"), "address": detail.get("address"),
            "directRawPricing": texts, "connectorStats": connector_stats(detail),
            "status": "direct_price_published" if texts else "no_direct_price",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        stations = sorted(pool.map(capture_one, markers), key=lambda x: str(x["mapId"]))
    failures = [x for x in stations if x["status"] not in ("direct_price_published", "no_direct_price")]
    if failures:
        raise RuntimeError(f"{network}: {len(failures)} incomplete station cards: {failures[:5]}")
    return stations


def semantic_payload(networks):
    return {network: [{key: station[key] for key in (
        "mapId", "legacyId", "code", "name", "address", "directRawPricing", "connectorStats", "status"
    )} for station in stations] for network, stations in networks.items()}


def build_capture(networks):
    semantic = semantic_payload(networks)
    encoded = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    summaries = {}
    for network, stations in networks.items():
        texts = Counter(text for station in stations for text in station["directRawPricing"])
        summaries[network] = {
            "mapStations": len(stations),
            "withDirectPrice": sum(bool(station["directRawPricing"]) for station in stations),
            "withoutDirectPrice": sum(not station["directRawPricing"] for station in stations),
            "distinctDirectTexts": len(texts),
            "directTexts": [{"text": text, "stations": count} for text, count in texts.most_common()],
        }
    return {
        "schemaVersion": 1, "source": BASE,
        "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "semanticSha256": hashlib.sha256(encoded).hexdigest(),
        "summary": summaries, "networks": semantic,
    }


def compare(previous, current):
    changes = {}
    for network in NETWORKS:
        before = {row["mapId"]: row for row in (previous or {}).get("networks", {}).get(network, [])}
        after = {row["mapId"]: row for row in current["networks"][network]}
        removed = sorted(before.keys() - after.keys())
        added = sorted(after.keys() - before.keys())
        tariff_changed = sorted(key for key in before.keys() & after.keys()
                                if before[key].get("directRawPricing") != after[key]["directRawPricing"])
        details_changed = sorted(key for key in before.keys() & after.keys()
                                 if before[key] != after[key] and key not in tariff_changed)
        changes[network] = {
            "addedMapIds": added, "removedMapIds": removed,
            "tariffChangedMapIds": tariff_changed, "otherChangedMapIds": details_changed,
        }
        if before and len(after) < max(1, int(len(before) * .98)):
            raise RuntimeError(f"{network}: station coverage fell from {len(before)} to {len(after)}")
    return changes


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out/izivia-station-tariffs-latest.json")
    parser.add_argument("--previous", default="data/operator_direct/izivia_station_tariffs_latest.json")
    parser.add_argument("--report", default="out/izivia-station-tariff-changes.json")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 16:
        parser.error("workers must be between 1 and 16")
    networks = {name: capture_network(name, spec, args.workers) for name, spec in NETWORKS.items()}
    result = build_capture(networks)
    if result["summary"]["IZIVIA FAST"]["withDirectPrice"] < 620:
        raise RuntimeError("FAST direct-price coverage fell below the last verified capture")
    if result["summary"]["IZIVIA Express"]["withDirectPrice"] < 146:
        raise RuntimeError("Express direct-price coverage fell below the last verified capture")
    previous_path = Path(args.previous)
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else None
    changes = compare(previous, result)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"capturedAt": result["capturedAt"], "semanticSha256": result["semanticSha256"],
                                  "changes": changes}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"semanticSha256": result["semanticSha256"], "summary": result["summary"],
                      "changes": changes}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
