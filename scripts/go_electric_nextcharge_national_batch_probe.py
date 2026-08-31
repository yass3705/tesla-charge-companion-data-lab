#!/usr/bin/env python3
"""Bounded national-scale Go Electric / NextCharge tariff attribution probe.

Purpose
-------
Scale the already validated connector-identity method beyond the four-station
sample without publishing or mutating any TCC runtime data.

Safety / attribution rules
--------------------------
- Download the published Italy V9 physical catalogue from the TCC stable repo.
- Select at most 24 OPERATIONAL Go Electric Stations SRLS stations, stratified
  over four station power classes and spread by latitude within each class.
- Query only NextCharge public map read endpoints (stationsGrid and
  stationConnectors). These endpoints use POST in the public web app but are
  treated here strictly as anonymous read requests.
- Every stationConnectors request must target an idStation discovered by a
  bounded stationsGrid query around one selected PUN coordinate.
- A CPO tariff is attributable only when a returned NextCharge uidConnector is
  exactly the numeric suffix of a PUN ITGESE EVSE id. Coordinate proximity is
  discovery evidence only and can never establish tariff attribution alone.
- No charge, payment, reservation, account, session or remote mutation action
  is allowed. Publication remains disabled regardless of coverage.
"""
from __future__ import annotations

import asyncio
import gzip
import io
import json
import math
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

SOURCE = "https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable/refactor/unified-data-engine-v9/data/v9/italy-static/all.json.gz"
TARGET_OPERATOR = "Go Electric Stations SRLS"
ROOT = "https://nextcharge.app/map?nextcharge=only&userCountry=IT"
GRID_ENDPOINT = "https://nextcharge.app/apps/map/apis/stationsGrid"
CONNECTORS_ENDPOINT = "https://nextcharge.app/apps/map/apis/stationConnectors"
OWNER = "ITGES"
APP_VERSION = "6.1.4"
BBOX_DEGREES = 0.012
MAX_MATCH_DISTANCE_M = 1200.0
MAX_CANDIDATES_PER_TARGET = 8
DEFAULT_LIMIT = 24
TARGET_CLASSES = ("AC_22_or_less", "DC_23_60", "DC_61_150", "HPC_over_150")
ALLOWED_GET_SUFFIXES = (
    "nextcharge.app", "kxcdn.com", "googleapis.com", "gstatic.com", "google.com",
    "maptiler.com",
)
UA = "TeslaChargeCompanion-DataLab/1.0 (+bounded read-only Italy V9 validation)"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def power_bucket(kw: float) -> str:
    if kw <= 22:
        return "AC_22_or_less"
    if kw <= 60:
        return "DC_23_60"
    if kw <= 150:
        return "DC_61_150"
    return "HPC_over_150"


def load_catalogue() -> list[list]:
    req = urllib.request.Request(SOURCE, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as response:
        raw = response.read()
    return json.loads(gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode("utf-8"))


def parse_go_electric(rows: list[list]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        if len(row) < 12:
            continue
        if str(row[5]).strip() != TARGET_OPERATOR and str(row[11]).strip() != TARGET_OPERATOR:
            continue
        station_id, name, address, lat, lon, operator, _, _, configs, generated_at, status, _ = row[:12]
        evses: list[dict] = []
        for cfg in configs or []:
            if not isinstance(cfg, list) or len(cfg) < 4:
                continue
            try:
                kw = float(cfg[3])
            except (TypeError, ValueError):
                kw = 0.0
            evses.append({"evseId": str(cfg[0]), "kind": str(cfg[2]), "maxPowerKw": kw})
        try:
            flat = float(lat)
            flon = float(lon)
        except (TypeError, ValueError):
            continue
        station_max = max((x["maxPowerKw"] for x in evses), default=0.0)
        if not evses or station_max <= 0:
            continue
        out.append({
            "stationId": str(station_id),
            "name": str(name),
            "address": str(address),
            "lat": flat,
            "lon": flon,
            "operator": str(operator),
            "status": str(status),
            "generatedAt": generated_at,
            "stationMaxPowerKw": station_max,
            "powerClass": power_bucket(station_max),
            "evses": evses,
        })
    return out


def evenly_spread(rows: list[dict], count: int) -> list[dict]:
    if count <= 0 or not rows:
        return []
    ordered = sorted(rows, key=lambda x: (x["lat"], x["lon"], x["stationId"]))
    if len(ordered) <= count:
        return ordered
    if count == 1:
        return [ordered[len(ordered) // 2]]
    indices = [round(i * (len(ordered) - 1) / (count - 1)) for i in range(count)]
    return [ordered[i] for i in dict.fromkeys(indices)]


def choose_targets(stations: list[dict], limit: int) -> list[dict]:
    limit = max(4, min(limit, 24))
    groups: dict[str, list[dict]] = defaultdict(list)
    for station in stations:
        if station["status"].upper() == "OPERATIONAL":
            groups[station["powerClass"]].append(station)
    base = limit // len(TARGET_CLASSES)
    extra = limit % len(TARGET_CLASSES)
    selected: list[dict] = []
    for idx, cls in enumerate(TARGET_CLASSES):
        selected.extend(evenly_spread(groups.get(cls, []), base + (1 if idx < extra else 0)))
    return selected[:limit]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def as_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def station_candidates(payload) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    def walk(node, depth: int = 0):
        if depth > 8 or len(found) >= 500:
            return
        if isinstance(node, dict):
            station_id = str(node.get("idStation") or node.get("stationId") or node.get("station_id") or "").strip()
            lat = as_number(node.get("latitude", node.get("lat")))
            lon = as_number(node.get("longitude", node.get("lng", node.get("lon"))))
            if station_id and lat is not None and lon is not None and station_id not in seen:
                seen.add(station_id)
                found.append({"idStation": station_id, "lat": lat, "lon": lon})
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node[:2000]:
                walk(value, depth + 1)

    walk(payload)
    return found


def normalize_connectors(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []


def evse_suffix(evse_id: str) -> str:
    return evse_id.removeprefix("ITGESE")


def tariff_summary(connector: dict) -> dict:
    tariff = connector.get("tariff") if isinstance(connector.get("tariff"), dict) else {}
    charge = tariff.get("charge") if isinstance(tariff.get("charge"), dict) else {}
    prices = charge.get("prices") if isinstance(charge.get("prices"), dict) else {}
    return {
        "currency": tariff.get("currency"),
        "prices": prices,
        "paymentRequired": charge.get("paymentRequired"),
        "preAuth": charge.get("preAuth"),
        "restrictions": charge.get("restrictions"),
    }


def power_compatible(expected_kw: float, returned_kw) -> bool | None:
    actual = as_number(returned_kw)
    if actual is None or expected_kw <= 0:
        return None
    return abs(actual - expected_kw) <= max(5.0, expected_kw * 0.12)


def allowed_get(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_GET_SUFFIXES)


async def main() -> None:
    requested_limit = int(os.environ.get("GO_ELECTRIC_BATCH_LIMIT", str(DEFAULT_LIMIT)))
    catalogue = parse_go_electric(load_catalogue())
    targets = choose_targets(catalogue, requested_limit)
    if len(targets) < 4:
        raise SystemExit(f"insufficient bounded targets: {len(targets)}")

    requests: list[dict] = []
    results: list[dict] = []
    connector_station_allowlist: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="it-IT")
        page = await context.new_page()

        async def route_handler(route, request):
            method = request.method.upper()
            url = request.url
            record = {"method": method, "url": url, "allowed": False, "reason": ""}
            if method in {"GET", "HEAD", "OPTIONS"} and allowed_get(url):
                record["allowed"] = True
                record["reason"] = "public_read"
                requests.append(record)
                await route.continue_()
                return
            if method == "POST" and url == GRID_ENDPOINT:
                form = parse_qs(request.post_data or "", keep_blank_values=True)
                valid = (
                    form.get("owner", [""])[0] == OWNER
                    and form.get("includeNextcharge", [""])[0] == "only"
                    and form.get("userCountry", [""])[0] == "IT"
                )
                if valid:
                    record["allowed"] = True
                    record["reason"] = "bounded_stations_grid_read"
                    requests.append(record)
                    await route.continue_()
                    return
            if method == "POST" and url == CONNECTORS_ENDPOINT:
                form = parse_qs(request.post_data or "", keep_blank_values=True)
                station_id = form.get("idStation", [""])[0]
                valid = station_id in connector_station_allowlist and form.get("reservable", [""])[0] == "0"
                if valid:
                    record["allowed"] = True
                    record["reason"] = "discovered_station_connectors_read"
                    requests.append(record)
                    await route.continue_()
                    return
            record["reason"] = "blocked_non_read_or_out_of_scope"
            requests.append(record)
            await route.abort()

        await page.route("**/*", route_handler)
        navigation_error = None
        try:
            await page.goto(ROOT, wait_until="commit", timeout=70000)
            await page.wait_for_timeout(4000)
        except Exception as exc:
            navigation_error = f"{type(exc).__name__}: {exc}"

        if navigation_error is None:
            for target in targets:
                lat, lon = target["lat"], target["lon"]
                grid_form = {
                    "lonSW": lon - BBOX_DEGREES,
                    "lonNE": lon + BBOX_DEGREES,
                    "latSW": lat - BBOX_DEGREES,
                    "latNE": lat + BBOX_DEGREES,
                    "filterIsReady": "true",
                    "includeNextcharge": "only",
                    "favorites": "0",
                    "userCountry": "IT",
                    "owner": OWNER,
                    "osType": "desktop",
                    "appVersion": APP_VERSION,
                    "idGroupProvider": "",
                }
                grid_response = await page.evaluate(
                    """async ({endpoint, form}) => {
                      const body = new URLSearchParams();
                      for (const [k,v] of Object.entries(form)) body.set(k, String(v));
                      try {
                        const r = await fetch(endpoint, {
                          method:'POST',
                          headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
                          body:body.toString()
                        });
                        const text=await r.text(); let json=null;
                        try { json=JSON.parse(text); } catch (_) {}
                        return {status:r.status,json,error:null};
                      } catch(e) { return {status:null,json:null,error:String(e)}; }
                    }""",
                    {"endpoint": GRID_ENDPOINT, "form": grid_form},
                )
                candidates = station_candidates(grid_response.get("json")) if grid_response.get("status") == 200 else []
                ranked: list[dict] = []
                for candidate in candidates:
                    distance = haversine_m(lat, lon, candidate["lat"], candidate["lon"])
                    if distance <= MAX_MATCH_DISTANCE_M:
                        ranked.append({**candidate, "distanceM": round(distance, 1)})
                ranked.sort(key=lambda x: (x["distanceM"], x["idStation"]))
                ranked = ranked[:MAX_CANDIDATES_PER_TARGET]
                connector_station_allowlist.update(x["idStation"] for x in ranked)

                expected_by_suffix = {evse_suffix(x["evseId"]): x for x in target["evses"]}
                candidate_results: list[dict] = []
                for candidate in ranked:
                    connector_response = await page.evaluate(
                        """async ({endpoint, stationId}) => {
                          const body=new URLSearchParams({idStation:stationId,reservable:'0',limit:'30',offset:'0',osType:'desktop',appVersion:'6.1.4'});
                          try {
                            const r=await fetch(endpoint,{
                              method:'POST',
                              headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
                              body:body.toString()
                            });
                            const text=await r.text(); let json=null;
                            try { json=JSON.parse(text); } catch (_) {}
                            return {status:r.status,json,error:null};
                          } catch(e) { return {status:null,json:null,error:String(e)}; }
                        }""",
                        {"endpoint": CONNECTORS_ENDPOINT, "stationId": candidate["idStation"]},
                    )
                    connectors = normalize_connectors(connector_response.get("json"))
                    mapped: list[dict] = []
                    for connector in connectors:
                        uid = str(connector.get("uidConnector") or "")
                        expected = expected_by_suffix.get(uid)
                        if not expected:
                            continue
                        mapped.append({
                            "punEvseId": expected["evseId"],
                            "uidConnector": uid,
                            "expectedPowerKw": expected["maxPowerKw"],
                            "powerMax": connector.get("powerMax"),
                            "powerCompatible": power_compatible(expected["maxPowerKw"], connector.get("powerMax")),
                            "status": connector.get("status"),
                            "current": connector.get("current"),
                            "standard": connector.get("standard"),
                            "tariff": tariff_summary(connector),
                        })
                    candidate_results.append({
                        **candidate,
                        "httpStatus": connector_response.get("status"),
                        "connectorCount": len(connectors),
                        "exactMatches": mapped,
                    })

                exact_candidates = [x for x in candidate_results if x["exactMatches"]]
                unique_exact = len(exact_candidates) == 1
                chosen = exact_candidates[0] if unique_exact else None
                matched_suffixes = {x["uidConnector"] for x in (chosen or {}).get("exactMatches", [])}
                expected_suffixes = set(expected_by_suffix)
                results.append({
                    "pun": target,
                    "gridHttpStatus": grid_response.get("status"),
                    "gridError": grid_response.get("error"),
                    "candidateCountWithinThreshold": len(ranked),
                    "candidates": candidate_results,
                    "exactCandidateCount": len(exact_candidates),
                    "uniqueExactStationMatch": unique_exact,
                    "matchedNextChargeStationId": chosen.get("idStation") if chosen else None,
                    "matchedDistanceM": chosen.get("distanceM") if chosen else None,
                    "exactConnectorMatches": (chosen or {}).get("exactMatches", []),
                    "expectedPunEvseSuffixes": sorted(expected_suffixes),
                    "unmatchedPunEvseSuffixes": sorted(expected_suffixes - matched_suffixes),
                    "attributionAllowedForStation": bool(chosen),
                })

        await browser.close()

    exact_stations = [x for x in results if x.get("uniqueExactStationMatch")]
    all_exact_connectors = [c for x in exact_stations for c in x.get("exactConnectorMatches", [])]
    tariffed = [c for c in all_exact_connectors if (c.get("tariff") or {}).get("prices")]
    power_checked = [c for c in all_exact_connectors if c.get("powerCompatible") is not None]
    power_compatible_count = sum(c.get("powerCompatible") is True for c in power_checked)
    classes = defaultdict(lambda: {"targets": 0, "exactStations": 0, "exactConnectors": 0, "tariffedConnectors": 0})
    for result in results:
        cls = result["pun"]["powerClass"]
        classes[cls]["targets"] += 1
        if result.get("uniqueExactStationMatch"):
            classes[cls]["exactStations"] += 1
            classes[cls]["exactConnectors"] += len(result.get("exactConnectorMatches", []))
            classes[cls]["tariffedConnectors"] += sum(bool((c.get("tariff") or {}).get("prices")) for c in result.get("exactConnectorMatches", []))

    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "source": SOURCE,
        "targetOperator": TARGET_OPERATOR,
        "catalogue": {
            "goElectricStationCount": len(catalogue),
            "goElectricEvseCount": sum(len(x["evses"]) for x in catalogue),
        },
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "boundedNationalProbe": True,
            "nationalScrape": False,
            "batchLimit": min(max(requested_limit, 4), 24),
            "allowedReadPostEndpoints": [GRID_ENDPOINT, CONNECTORS_ENDPOINT],
            "connectorReadRequiresPriorBoundedGridDiscovery": True,
            "exactPunEvseSuffixRequiredForAttribution": True,
            "coordinateOnlyAttributionAllowed": False,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
            "accountActionsAllowed": False,
            "sessionMutationAllowed": False,
            "officialGoElectricB2CChannel": "https://nextcharge.app",
            "directCpoPublicationAllowed": False,
            "publicationReason": "bounded_batch_only_no_full_national_qa",
        },
        "navigationError": navigation_error,
        "summary": {
            "targetStations": len(targets),
            "queriedStations": len(results),
            "exactMatchedStations": len(exact_stations),
            "exactStationMatchRate": round(len(exact_stations) / len(results), 4) if results else 0.0,
            "targetPunEvses": sum(len(x["pun"]["evses"]) for x in results),
            "exactConnectorMatches": len(all_exact_connectors),
            "tariffedExactConnectors": len(tariffed),
            "tariffCoverageOnExactConnectors": round(len(tariffed) / len(all_exact_connectors), 4) if all_exact_connectors else 0.0,
            "powerCheckedExactConnectors": len(power_checked),
            "powerCompatibleExactConnectors": power_compatible_count,
            "classBreakdown": dict(classes),
        },
        "targets": results,
        "blockedRequests": [x for x in requests if not x.get("allowed")],
    }
    out = Path("artifacts/go_electric_nextcharge_national_batch_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "catalogue": report["catalogue"],
        "summary": report["summary"],
        "publicationAllowed": report["policy"]["directCpoPublicationAllowed"],
        "blockedRequestCount": len(report["blockedRequests"]),
        "matchedStations": [
            {
                "punStationId": x["pun"]["stationId"],
                "class": x["pun"]["powerClass"],
                "nextChargeStationId": x.get("matchedNextChargeStationId"),
                "distanceM": x.get("matchedDistanceM"),
                "exactConnectors": len(x.get("exactConnectorMatches", [])),
                "tariffed": sum(bool((c.get("tariff") or {}).get("prices")) for c in x.get("exactConnectorMatches", [])),
            }
            for x in exact_stations
        ],
    }, ensure_ascii=False, indent=2))

    if navigation_error:
        raise SystemExit(navigation_error)
    if len(results) != len(targets):
        raise SystemExit("not every bounded target was queried")
    if not exact_stations:
        raise SystemExit("bounded batch produced no exact PUN EVSE / NextCharge connector identity match")


if __name__ == "__main__":
    asyncio.run(main())
