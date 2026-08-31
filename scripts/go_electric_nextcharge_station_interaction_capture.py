#!/usr/bin/env python3
"""Reveal the next public station-data request emitted by the NextCharge map.

Safety model:
- load the public NextCharge map anonymously;
- allow GET/HEAD/OPTIONS;
- allow POST only to the two already validated read endpoints: stationsGrid and station;
- reposition the public map to Rome and select one returned station marker;
- record and abort every other POST/PUT/PATCH/DELETE request.

This lets us discover the connector/tariff read endpoint and payload without
executing that newly discovered request or any charging/payment action.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = "https://nextcharge.app/map?nextcharge=only"
GRID_ENDPOINT = "https://nextcharge.app/apps/map/apis/stationsGrid"
STATION_ENDPOINT = "https://nextcharge.app/apps/map/apis/station"
READ_POST_ALLOWLIST = {GRID_ENDPOINT, STATION_ENDPOINT}
ALLOWED_HOST_SUFFIXES = (
    "nextcharge.app",
    "goelectricstations.com",
    "kxcdn.com",
    "googleapis.com",
    "gstatic.com",
    "google.com",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    blocked = {"authorization", "cookie", "set-cookie", "proxy-authorization"}
    return {k: v for k, v in headers.items() if k.lower() not in blocked}


async def main() -> None:
    requests: list[dict[str, object]] = []
    responses: list[dict[str, object]] = []
    console: list[dict[str, str]] = []
    interaction: dict[str, object] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="it-IT")
        page = await context.new_page()

        async def route_handler(route, request):
            method = request.method.upper()
            url = request.url
            record: dict[str, object] = {
                "time": now_iso(),
                "method": method,
                "url": url,
                "resourceType": request.resource_type,
                "headers": redact_headers(await request.all_headers()),
                "postData": request.post_data,
                "allowed": False,
                "reason": "",
            }
            if not allowed_host(url):
                record["reason"] = "host_not_in_public_frontend_allowlist"
                requests.append(record)
                await route.abort()
                return
            if method in {"GET", "HEAD", "OPTIONS"}:
                record["allowed"] = True
                record["reason"] = "read_only_method"
                requests.append(record)
                await route.continue_()
                return
            if method == "POST" and url in READ_POST_ALLOWLIST:
                record["allowed"] = True
                record["reason"] = "validated_public_read_post_endpoint"
                requests.append(record)
                await route.continue_()
                return
            record["reason"] = "new_non_get_recorded_and_blocked"
            requests.append(record)
            await route.abort()

        async def response_handler(response):
            req = response.request
            if req.url in READ_POST_ALLOWLIST:
                item: dict[str, object] = {
                    "url": req.url,
                    "method": req.method,
                    "status": response.status,
                }
                try:
                    body = await response.text()
                    item["bodyPrefix"] = body[:4000]
                except Exception as exc:
                    item["bodyError"] = f"{type(exc).__name__}: {exc}"
                responses.append(item)

        await page.route("**/*", route_handler)
        page.on("response", response_handler)
        page.on("console", lambda msg: console.append({"type": msg.type, "text": msg.text[:2000]}))

        nav_error = None
        try:
            await page.goto(ROOT, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(12000)

            interaction["preMapState"] = await page.evaluate(
                """() => ({
                    mapDefined: typeof map !== 'undefined',
                    getStationsDefined: typeof getStations === 'function',
                    selectStationDefined: typeof selectStation === 'function',
                    markersArrayDefined: typeof markersArray !== 'undefined',
                    mapIsInitialized: typeof mapIsInitialized !== 'undefined' ? mapIsInitialized : null,
                    filterReady: typeof filterStations !== 'undefined' ? filterStations.filterIsReady : null
                })"""
            )

            interaction["moveResult"] = await page.evaluate(
                """() => {
                    if (typeof map === 'undefined') return {ok:false, reason:'map_missing'};
                    try {
                        if (typeof map.setView === 'function') map.setView([41.90, 12.50], 12);
                        else if (typeof map.setCenter === 'function') map.setCenter({lat:41.90,lng:12.50});
                        if (typeof filterStations !== 'undefined') {
                            filterStations.filterIsReady = true;
                            filterStations.includeNextcharge = 'only';
                        }
                        if (typeof mapIsInitialized !== 'undefined') mapIsInitialized = true;
                        if (typeof country !== 'undefined') country = 'IT';
                        if (typeof getStations === 'function') getStations();
                        return {ok:true};
                    } catch (e) {
                        return {ok:false, reason:String(e)};
                    }
                }"""
            )
            await page.wait_for_timeout(9000)

            interaction["markerState"] = await page.evaluate(
                """() => {
                    if (typeof markersArray === 'undefined') return {count:null, ids:[]};
                    const rows = [];
                    for (const m of markersArray || []) {
                        const s = m && m.options && m.options.station;
                        if (s && s.idStation) rows.push({idStation:s.idStation, isPartial:s.isPartial, status:s.status});
                        if (rows.length >= 20) break;
                    }
                    return {count:(markersArray || []).length, ids:rows};
                }"""
            )

            interaction["selectionResult"] = await page.evaluate(
                """() => {
                    if (typeof markersArray === 'undefined' || typeof selectStation !== 'function')
                        return {ok:false, reason:'selection_globals_missing'};
                    const marker = (markersArray || []).find(m => m && m.options && m.options.station && m.options.station.idStation);
                    if (!marker) return {ok:false, reason:'no_station_marker'};
                    const sid = marker.options.station.idStation;
                    try {
                        selectStation(marker);
                        return {ok:true, idStation:sid};
                    } catch (e) {
                        try {
                            if (typeof marker.fire === 'function') {
                                marker.fire('click');
                                return {ok:true, idStation:sid, via:'marker.fire'};
                            }
                        } catch (_) {}
                        return {ok:false, idStation:sid, reason:String(e)};
                    }
                }"""
            )
            await page.wait_for_timeout(12000)
        except Exception as exc:
            nav_error = f"{type(exc).__name__}: {exc}"

        interaction["finalUrl"] = page.url
        await browser.close()

    blocked_new = [
        r for r in requests
        if r["method"] not in {"GET", "HEAD", "OPTIONS"} and r["url"] not in READ_POST_ALLOWLIST
    ]
    allowed_read_posts = [r for r in requests if r.get("reason") == "validated_public_read_post_endpoint"]
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "policy": {
            "publicFrontendOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "allowedPostEndpoints": sorted(READ_POST_ALLOWLIST),
            "newNonGetRequestsBlocked": True,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
        },
        "navigationError": nav_error,
        "interaction": interaction,
        "requestCount": len(requests),
        "allowedReadPostCount": len(allowed_read_posts),
        "blockedNewNonGetCount": len(blocked_new),
        "allowedReadPosts": allowed_read_posts,
        "blockedNewNonGetRequests": blocked_new,
        "readResponses": responses,
        "console": console[-200:],
    }
    out = Path("artifacts/go_electric_nextcharge_station_interaction_capture.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "navigationError": nav_error,
        "interaction": interaction,
        "allowedReadPostCount": len(allowed_read_posts),
        "blockedNewNonGetCount": len(blocked_new),
    }, ensure_ascii=False, indent=2))
    for r in blocked_new[:50]:
        print("BLOCKED", r["method"], r["url"], (r.get("postData") or "")[:1500])


if __name__ == "__main__":
    asyncio.run(main())
