#!/usr/bin/env python3
"""Capture the request/data transition caused by opening NextCharge connectors.

This probe targets one PUN-confirmed Go Electric coordinate (Spoltore) and is
strictly fail-closed:
- anonymous public web map only;
- GET/HEAD/OPTIONS are allowed on the public frontend/CDN hosts;
- during bootstrap, POST is allowed only to the two previously validated public
  read endpoints `stationsGrid` and `station`;
- immediately before opening the connector panel, the probe switches to capture
  mode and blocks EVERY non-GET request, including calls to the known endpoints;
- no charging/payment/reservation/account action can therefore execute.

The goal is to reveal either (a) the blocked request that populates
`currentConnectorsList`, or (b) that the list is populated entirely from already
loaded client-side data.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = "https://nextcharge.app/map?nextcharge=only&userCountry=IT"
GRID_ENDPOINT = "https://nextcharge.app/apps/map/apis/stationsGrid"
STATION_ENDPOINT = "https://nextcharge.app/apps/map/apis/station"
BOOTSTRAP_POST_ALLOWLIST = {GRID_ENDPOINT, STATION_ENDPOINT}
TARGET_LAT = 42.444429
TARGET_LON = 14.176838
TARGET_NC_STATION_ID = "gir.vat.mx.0245db"
ALLOWED_HOST_SUFFIXES = (
    "nextcharge.app",
    "goelectricstations.com",
    "kxcdn.com",
    "googleapis.com",
    "gstatic.com",
    "google.com",
    "maptiler.com",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in ALLOWED_HOST_SUFFIXES)


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    blocked = {"authorization", "cookie", "set-cookie", "proxy-authorization"}
    return {k: v for k, v in headers.items() if k.lower() not in blocked}


async def main() -> None:
    requests: list[dict[str, object]] = []
    responses: list[dict[str, object]] = []
    console: list[dict[str, str]] = []
    interaction: dict[str, object] = {}
    capture_mode = {"value": False}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="it-IT")
        page = await context.new_page()

        async def route_handler(route, request):
            method = request.method.upper()
            url = request.url
            record: dict[str, object] = {
                "time": now_iso(),
                "phase": "connector_capture" if capture_mode["value"] else "bootstrap",
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
            if (not capture_mode["value"]) and method == "POST" and url in BOOTSTRAP_POST_ALLOWLIST:
                record["allowed"] = True
                record["reason"] = "validated_bootstrap_read_post"
                requests.append(record)
                await route.continue_()
                return
            record["reason"] = "non_get_blocked_in_connector_capture"
            requests.append(record)
            await route.abort()

        async def response_handler(response):
            req = response.request
            if req.url in BOOTSTRAP_POST_ALLOWLIST:
                item: dict[str, object] = {"url": req.url, "method": req.method, "status": response.status}
                try:
                    body = await response.text()
                    item["bodyPrefix"] = body[:6000]
                except Exception as exc:
                    item["bodyError"] = f"{type(exc).__name__}: {exc}"
                responses.append(item)

        await page.route("**/*", route_handler)
        page.on("response", response_handler)
        page.on("console", lambda msg: console.append({"type": msg.type, "text": msg.text[:3000]}))

        nav_error = None
        try:
            await page.goto(ROOT, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(10000)

            interaction["runtimeBeforeMove"] = await page.evaluate(
                """() => ({
                  mapDefined: typeof map !== 'undefined',
                  showConnectorsType: typeof showConnectors,
                  selectStationType: typeof selectStation,
                  currentConnectorsListType: typeof currentConnectorsList,
                  currentConnectorsListLength: Array.isArray(currentConnectorsList) ? currentConnectorsList.length : null
                })"""
            )

            interaction["moveResult"] = await page.evaluate(
                f"""() => {{
                  try {{
                    if (typeof map === 'undefined') return {{ok:false, reason:'map_missing'}};
                    if (typeof map.setView === 'function') map.setView([{TARGET_LAT}, {TARGET_LON}], 15);
                    if (typeof filterStations !== 'undefined') {{
                      filterStations.filterIsReady = true;
                      filterStations.includeNextcharge = 'only';
                    }}
                    if (typeof mapIsInitialized !== 'undefined') mapIsInitialized = true;
                    if (typeof country !== 'undefined') country = 'IT';
                    if (typeof getStations === 'function') getStations();
                    return {{ok:true}};
                  }} catch(e) {{ return {{ok:false, reason:String(e)}}; }}
                }}"""
            )
            await page.wait_for_timeout(9000)

            interaction["markerState"] = await page.evaluate(
                f"""() => {{
                  if (typeof markersArray === 'undefined') return {{count:null, matches:[]}};
                  const rows=[];
                  for (const m of markersArray || []) {{
                    const s=m?.options?.station;
                    if (!s?.idStation) continue;
                    if (s.idStation === '{TARGET_NC_STATION_ID}' || rows.length < 12)
                      rows.push({{idStation:s.idStation, provider:s.provider, isPartial:s.isPartial, status:s.status, lat:s.latitude ?? s.lat, lon:s.longitude ?? s.lng}});
                  }}
                  return {{count:(markersArray||[]).length, matches:rows}};
                }}"""
            )

            interaction["selectionResult"] = await page.evaluate(
                f"""() => {{
                  if (typeof markersArray === 'undefined' || typeof selectStation !== 'function')
                    return {{ok:false, reason:'selection_globals_missing'}};
                  let marker=(markersArray||[]).find(m => m?.options?.station?.idStation === '{TARGET_NC_STATION_ID}');
                  if (!marker) marker=(markersArray||[]).find(m => m?.options?.station?.idStation);
                  if (!marker) return {{ok:false, reason:'no_station_marker'}};
                  const sid=marker.options.station.idStation;
                  try {{ selectStation(marker); return {{ok:true,idStation:sid}}; }}
                  catch(e) {{ return {{ok:false,idStation:sid,reason:String(e)}}; }}
                }}"""
            )
            await page.wait_for_timeout(8000)

            interaction["beforeConnectorOpen"] = await page.evaluate(
                """() => ({
                  selectedId: (typeof stationSelected !== 'undefined' && stationSelected?.[0]?.station?.idStation) || null,
                  showConnectorsType: typeof showConnectors,
                  currentConnectorsListLength: Array.isArray(currentConnectorsList) ? currentConnectorsList.length : null,
                  currentConnectorsListPreview: Array.isArray(currentConnectorsList) ? currentConnectorsList.slice(0,3) : null,
                  buttonCount: document.querySelectorAll('.buttonConnectors').length,
                  visibleButtonCount: [...document.querySelectorAll('.buttonConnectors')].filter(e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)).length,
                  stationKeys: (typeof stationSelected !== 'undefined' && stationSelected?.[0]?.station) ? Object.keys(stationSelected[0].station).sort() : []
                })"""
            )

            # From this point onward, every non-GET request is blocked and captured.
            capture_mode["value"] = True

            interaction["connectorOpenResult"] = await page.evaluate(
                """() => {
                  try {
                    const buttons=[...document.querySelectorAll('.buttonConnectors')];
                    const visible=buttons.find(e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length));
                    if (visible) {
                      visible.click();
                      return {ok:true, via:'visible_button_click', className:visible.className};
                    }
                    if (typeof showConnectors === 'function') {
                      showConnectors();
                      return {ok:true, via:'showConnectors_direct'};
                    }
                    return {ok:false, reason:'no_visible_button_or_function'};
                  } catch(e) { return {ok:false, reason:String(e)}; }
                }"""
            )
            await page.wait_for_timeout(10000)

            interaction["afterConnectorOpen"] = await page.evaluate(
                """() => ({
                  currentConnectorsListLength: Array.isArray(currentConnectorsList) ? currentConnectorsList.length : null,
                  currentConnectorsListPreview: Array.isArray(currentConnectorsList) ? currentConnectorsList.slice(0,5) : null,
                  connectorPanelCandidates: [...document.querySelectorAll('[class*=connector], [id*=connector]')].slice(0,40).map(e => ({tag:e.tagName,id:e.id,className:e.className,text:(e.innerText||'').slice(0,300)}))
                })"""
            )
        except Exception as exc:
            nav_error = f"{type(exc).__name__}: {exc}"

        interaction["finalUrl"] = page.url
        await browser.close()

    blocked_capture = [r for r in requests if r.get("phase") == "connector_capture" and r["method"] not in {"GET","HEAD","OPTIONS"}]
    bootstrap_posts = [r for r in requests if r.get("reason") == "validated_bootstrap_read_post"]
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "policy": {
            "publicFrontendOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "bootstrapAllowedPostEndpoints": sorted(BOOTSTRAP_POST_ALLOWLIST),
            "allNonGetBlockedAfterConnectorCaptureStarts": True,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
            "accountActionsAllowed": False,
            "targetPUNOperator": "Go Electric Stations SRLS",
            "targetNextChargeStationId": TARGET_NC_STATION_ID,
        },
        "navigationError": nav_error,
        "interaction": interaction,
        "requestCount": len(requests),
        "bootstrapReadPostCount": len(bootstrap_posts),
        "blockedConnectorCaptureNonGetCount": len(blocked_capture),
        "blockedConnectorCaptureNonGetRequests": blocked_capture,
        "bootstrapReadPosts": bootstrap_posts,
        "readResponses": responses,
        "console": console[-250:],
    }
    out=Path("artifacts/go_electric_nextcharge_connector_click_capture.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "navigationError": nav_error,
        "interaction": interaction,
        "bootstrapReadPostCount": len(bootstrap_posts),
        "blockedConnectorCaptureNonGetCount": len(blocked_capture),
    },ensure_ascii=False,indent=2))
    for r in blocked_capture[:50]:
        print("BLOCKED_CONNECTOR_CAPTURE",r["method"],r["url"],(r.get("postData") or "")[:2500])


if __name__ == "__main__":
    asyncio.run(main())
