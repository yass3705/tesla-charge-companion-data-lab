#!/usr/bin/env python3
"""Validate exact connector tariffs across representative Go Electric PUN stations.

Four Go Electric Stations SRLS PUN locations previously matched to NextCharge at
0.0 metres are queried at the public `stationConnectors` read endpoint. The
probe verifies whether returned connector ids map exactly to PUN EVSE suffixes
and records connector-level tariff components.

This remains a validation sample, not a national scrape. It performs no charging,
payment, reservation or account action.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

ROOT = "https://nextcharge.app/map?nextcharge=only&userCountry=IT"
CONNECTORS_ENDPOINT = "https://nextcharge.app/apps/map/apis/stationConnectors"
ALLOWED_GET_SUFFIXES = ("nextcharge.app", "kxcdn.com", "googleapis.com", "gstatic.com", "google.com", "maptiler.com")

TARGETS = [
    {
        "powerClass": "AC_22_or_less",
        "punStationId": "6a0449d0b96b9b5d5bb9285d",
        "name": "Località Casale S.S. 150 km, 17. – Canzano",
        "nextChargeStationId": "INGE-6S0A222A3335",
        "lat": 42.629231,
        "lon": 13.831692,
        "punEvses": ["ITGESE810210680", "ITGESE810210682", "ITGESE810373479", "ITGESE810373480"],
    },
    {
        "powerClass": "DC_23_60",
        "punStationId": "6a04774ab96b9b5d5bbb1033",
        "name": "Via Mare Ionio – Spoltore",
        "nextChargeStationId": "gir.vat.mx.0245db",
        "lat": 42.444429,
        "lon": 14.176838,
        "punEvses": ["ITGESE812715456", "ITGESE812715457", "ITGESE812715458"],
    },
    {
        "powerClass": "DC_61_150",
        "punStationId": "6a047792b96b9b5d5bbb14a7",
        "name": "Strada Statale 18 Tirrena Inferiore – Pagani",
        "nextChargeStationId": "A475006001",
        "lat": 40.747963,
        "lon": 14.606109,
        "punEvses": ["ITGESE852011861", "ITGESE852011862"],
    },
    {
        "powerClass": "HPC_over_150",
        "punStationId": "6a044812b96b9b5d5bb9145a",
        "name": "Strada Statale 372 Telesina",
        "nextChargeStationId": "DC-000607",
        "lat": 41.24425,
        "lon": 14.440299,
        "punEvses": ["ITGESE844643496", "ITGESE844643497"],
    },
]
TARGET_IDS = {x["nextChargeStationId"] for x in TARGETS}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed_get(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in ALLOWED_GET_SUFFIXES)


def evse_suffix(evse: str) -> str:
    return evse.removeprefix("ITGESE")


def normalize_connectors(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []


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


async def main() -> None:
    requests: list[dict] = []
    results: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="it-IT")
        page = await context.new_page()

        async def route_handler(route, request):
            method = request.method.upper()
            url = request.url
            rec = {"method": method, "url": url, "postData": request.post_data, "allowed": False, "reason": ""}
            if method in {"GET", "HEAD", "OPTIONS"} and allowed_get(url):
                rec["allowed"] = True
                rec["reason"] = "public_read"
                requests.append(rec)
                await route.continue_()
                return
            if method == "POST" and url == CONNECTORS_ENDPOINT:
                form = parse_qs(request.post_data or "", keep_blank_values=True)
                station_id = form.get("idStation", [""])[0]
                valid = station_id in TARGET_IDS and form.get("reservable", [""])[0] == "0"
                if valid:
                    rec["allowed"] = True
                    rec["reason"] = "validated_station_connectors_read"
                    requests.append(rec)
                    await route.continue_()
                    return
                rec["reason"] = "station_connectors_out_of_scope"
                requests.append(rec)
                await route.abort()
                return
            rec["reason"] = "blocked_non_read_or_unknown_host"
            requests.append(rec)
            await route.abort()

        await page.route("**/*", route_handler)
        navigation_error = None
        try:
            await page.goto(ROOT, wait_until="domcontentloaded", timeout=70000)
            await page.wait_for_timeout(5000)
        except Exception as exc:
            navigation_error = f"{type(exc).__name__}: {exc}"

        if navigation_error is None:
            for target in TARGETS:
                station_id = target["nextChargeStationId"]
                response = await page.evaluate(
                    """async ({endpoint, stationId}) => {
                      const body = new URLSearchParams({
                        idStation: stationId,
                        reservable: '0',
                        limit: '30',
                        offset: '0',
                        osType: 'desktop',
                        appVersion: '6.1.4'
                      });
                      try {
                        const r = await fetch(endpoint, {
                          method: 'POST',
                          headers: {'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
                          body: body.toString()
                        });
                        const text = await r.text();
                        let json = null;
                        try { json = JSON.parse(text); } catch (_) {}
                        return {status:r.status, textBytes:new TextEncoder().encode(text).length, json};
                      } catch (e) {
                        return {status:null, error:String(e), json:null};
                      }
                    }""",
                    {"endpoint": CONNECTORS_ENDPOINT, "stationId": station_id},
                )
                connectors = normalize_connectors(response.get("json"))
                expected = {evse_suffix(x) for x in target["punEvses"]}
                rows = []
                returned = set()
                for c in connectors:
                    uid = str(c.get("uidConnector") or "")
                    if uid:
                        returned.add(uid)
                    rows.append({
                        "uidConnector": c.get("uidConnector"),
                        "matchesPunEvseSuffix": uid in expected,
                        "matchedPunEvse": next((x for x in target["punEvses"] if evse_suffix(x) == uid), None),
                        "status": c.get("status"),
                        "powerMax": c.get("powerMax"),
                        "current": c.get("current"),
                        "standard": c.get("standard"),
                        "physicalReference": c.get("physicalReference"),
                        "tariff": tariff_summary(c),
                    })
                results.append({
                    **target,
                    "httpStatus": response.get("status"),
                    "responseBytes": response.get("textBytes"),
                    "error": response.get("error"),
                    "connectorCount": len(connectors),
                    "expectedPunEvseSuffixes": sorted(expected),
                    "returnedConnectorIds": sorted(returned),
                    "exactConnectorIdMatches": sorted(expected & returned),
                    "unmatchedExpectedPunEvseSuffixes": sorted(expected - returned),
                    "unexpectedReturnedConnectorIds": sorted(returned - expected),
                    "connectors": rows,
                })

        await browser.close()

    successful = [x for x in results if x.get("httpStatus") == 200 and x.get("connectorCount", 0) > 0]
    exact_matches = sum(len(x.get("exactConnectorIdMatches", [])) for x in successful)
    tariffed = sum(1 for x in successful for c in x.get("connectors", []) if (c.get("tariff") or {}).get("prices"))
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "nationalScrape": False,
            "representativeStationCount": len(TARGETS),
            "allowedPostEndpoint": CONNECTORS_ENDPOINT,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
            "accountActionsAllowed": False,
            "officialGoElectricB2CChannel": "https://nextcharge.app",
            "operatorAuthorizedPlatformAttributionCandidate": True,
            "nationalPublicationAllowed": False,
        },
        "navigationError": navigation_error,
        "targets": results,
        "summary": {
            "targetStations": len(TARGETS),
            "successfulStations": len(successful),
            "exactConnectorIdMatches": exact_matches,
            "tariffedConnectors": tariffed,
            "allSuccessfulStationsHaveExactConnectorMatch": bool(successful) and all(x.get("exactConnectorIdMatches") for x in successful),
        },
        "blockedRequests": [x for x in requests if not x.get("allowed")],
    }
    out = Path("artifacts/go_electric_nextcharge_multi_station_tariff_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "navigationError": navigation_error,
        "summary": report["summary"],
        "stations": [
            {
                "powerClass": x.get("powerClass"),
                "nextChargeStationId": x.get("nextChargeStationId"),
                "httpStatus": x.get("httpStatus"),
                "connectorCount": x.get("connectorCount"),
                "exactMatches": x.get("exactConnectorIdMatches"),
                "unmatched": x.get("unmatchedExpectedPunEvseSuffixes"),
                "tariffs": [{"uid": c.get("uidConnector"), "power": c.get("powerMax"), **(c.get("tariff") or {})} for c in x.get("connectors", [])],
            }
            for x in results
        ],
    }, ensure_ascii=False, indent=2))
    if navigation_error:
        raise SystemExit(navigation_error)
    if len(successful) < 3:
        raise SystemExit(f"insufficient successful representative stations: {len(successful)}")
    if not all(x.get("exactConnectorIdMatches") for x in successful):
        raise SystemExit("a successful station has no exact PUN EVSE suffix match")


if __name__ == "__main__":
    asyncio.run(main())
