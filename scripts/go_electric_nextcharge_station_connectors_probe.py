#!/usr/bin/env python3
"""Read one public NextCharge stationConnectors payload for an exact PUN coordinate.

The target is the Spoltore station previously matched by coordinate to the Go Electric
PUN inventory. This probe is deliberately attribution-neutral: any tariff returned by
NextCharge is evidence of a NextCharge/eMSP presentation until a direct Go Electric CPO
price is independently attributable to the physical EVSE.

Safety:
- anonymous public web map only;
- GET/HEAD/OPTIONS allowed only on public frontend/CDN hosts;
- POST allowed only to stationsGrid, station and stationConnectors;
- stationConnectors is allowed only for the single known station id and reservable=0;
- every other non-GET request is blocked;
- no charge/payment/reservation/account/session mutation can execute.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

ROOT = "https://nextcharge.app/map?nextcharge=only&userCountry=IT"
GRID_ENDPOINT = "https://nextcharge.app/apps/map/apis/stationsGrid"
STATION_ENDPOINT = "https://nextcharge.app/apps/map/apis/station"
CONNECTORS_ENDPOINT = "https://nextcharge.app/apps/map/apis/stationConnectors"
POST_ALLOWLIST = {GRID_ENDPOINT, STATION_ENDPOINT, CONNECTORS_ENDPOINT}
TARGET_LAT = 42.444429
TARGET_LON = 14.176838
TARGET_NC_STATION_ID = "gir.vat.mx.0245db"
TARGET_PUN_OPERATOR = "Go Electric Stations SRLS"
TARGET_PUN_EVSES = ["ITGESE812715456", "ITGESE812715457", "ITGESE812715458"]
ALLOWED_HOST_SUFFIXES = (
    "nextcharge.app", "goelectricstations.com", "kxcdn.com", "googleapis.com",
    "gstatic.com", "google.com", "maptiler.com",
)
SENSITIVE_PARTS = (
    "token", "secret", "password", "cookie", "authorization", "card", "pan",
    "paymentmethod", "clientsecret", "accesskey", "nonce",
)
TARIFF_TERMS = (
    "tariff", "price", "currency", "energy", "time", "session", "parking",
    "preauth", "restriction", "connector", "evse", "uid", "power", "current",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in ALLOWED_HOST_SUFFIXES)


def safe_key(key: str) -> bool:
    low = key.lower().replace("_", "")
    return not any(x in low for x in SENSITIVE_PARTS)


def redact(value, depth: int = 0, list_limit: int = 50):
    if depth > 12:
        return "<depth-limit>"
    if isinstance(value, dict):
        return {str(k): (redact(v, depth + 1, list_limit) if safe_key(str(k)) else "<redacted>") for k, v in value.items()}
    if isinstance(value, list):
        out = [redact(v, depth + 1, list_limit) for v in value[:list_limit]]
        if len(value) > list_limit:
            out.append({"_truncatedItems": len(value) - list_limit})
        return out
    if isinstance(value, str):
        return value[:6000]
    return value


def tariff_fields(value, prefix: str = "", depth: int = 0, out: dict | None = None):
    if out is None:
        out = {}
    if depth > 12 or len(out) >= 1000:
        return out
    if isinstance(value, dict):
        for k, v in value.items():
            sk = str(k)
            path = f"{prefix}.{sk}" if prefix else sk
            low = sk.lower().replace("_", "")
            if safe_key(sk) and any(term in low for term in TARIFF_TERMS):
                out[path] = redact(v, list_limit=30)
            tariff_fields(v, path, depth + 1, out)
    elif isinstance(value, list):
        for i, v in enumerate(value[:50]):
            tariff_fields(v, f"{prefix}[{i}]", depth + 1, out)
    return out


def connector_count(value) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in ("connectors", "data", "items", "results"):
            if isinstance(value.get(key), list):
                return len(value[key])
    return 0


async def main() -> None:
    requests: list[dict] = []
    connector_responses: list[dict] = []
    interaction: dict = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="it-IT")
        page = await context.new_page()

        async def route_handler(route, request):
            method = request.method.upper()
            url = request.url
            rec = {"time": now_iso(), "method": method, "url": url, "postData": request.post_data, "allowed": False, "reason": ""}
            if not allowed_host(url):
                rec["reason"] = "host_not_allowed"
                requests.append(rec)
                await route.abort()
                return
            if method in {"GET", "HEAD", "OPTIONS"}:
                rec["allowed"] = True
                rec["reason"] = "read_only_method"
                requests.append(rec)
                await route.continue_()
                return
            if method == "POST" and url in POST_ALLOWLIST:
                if url == CONNECTORS_ENDPOINT:
                    form = parse_qs(request.post_data or "", keep_blank_values=True)
                    valid = (
                        form.get("idStation", [""])[0] == TARGET_NC_STATION_ID
                        and form.get("reservable", [""])[0] == "0"
                        and form.get("limit", [""])[0] in {"10", ""}
                    )
                    if not valid:
                        rec["reason"] = "station_connectors_payload_out_of_scope"
                        requests.append(rec)
                        await route.abort()
                        return
                rec["allowed"] = True
                rec["reason"] = "validated_public_read_post"
                requests.append(rec)
                await route.continue_()
                return
            rec["reason"] = "non_get_not_in_read_allowlist"
            requests.append(rec)
            await route.abort()

        async def response_handler(response):
            if response.request.url != CONNECTORS_ENDPOINT:
                return
            item = {"url": response.request.url, "status": response.status, "postData": response.request.post_data}
            try:
                text = await response.text()
                item["responseBytes"] = len(text.encode("utf-8"))
                payload = json.loads(text)
                item["json"] = True
                item["connectorCount"] = connector_count(payload)
                item["tariffFields"] = tariff_fields(payload)
                item["redactedPayload"] = redact(payload)
            except Exception as exc:
                item["json"] = False
                item["error"] = f"{type(exc).__name__}: {exc}"
            connector_responses.append(item)

        await page.route("**/*", route_handler)
        page.on("response", response_handler)

        nav_error = None
        try:
            await page.goto(ROOT, wait_until="domcontentloaded", timeout=70000)
            await page.wait_for_timeout(9000)
            interaction["move"] = await page.evaluate(
                f"""() => {{
                  try {{
                    map.setView([{TARGET_LAT}, {TARGET_LON}], 15);
                    filterStations.filterIsReady = true;
                    filterStations.includeNextcharge = 'only';
                    mapIsInitialized = true;
                    country = 'IT';
                    getStations();
                    return {{ok:true}};
                  }} catch(e) {{ return {{ok:false,reason:String(e)}}; }}
                }}"""
            )
            await page.wait_for_timeout(9000)
            interaction["selection"] = await page.evaluate(
                f"""() => {{
                  try {{
                    const marker=(markersArray||[]).find(m => m?.options?.station?.idStation === '{TARGET_NC_STATION_ID}');
                    if (!marker) return {{ok:false,reason:'target_marker_not_found',markerCount:(markersArray||[]).length}};
                    selectStation(marker);
                    return {{ok:true,idStation:marker.options.station.idStation}};
                  }} catch(e) {{ return {{ok:false,reason:String(e)}}; }}
                }}"""
            )
            await page.wait_for_timeout(7000)
            interaction["station"] = await page.evaluate(
                """() => ({
                  idStation: stationSelected?.[0]?.station?.idStation ?? null,
                  provider: stationSelected?.[0]?.station?.provider ?? null,
                  connectorsSummary: stationSelected?.[0]?.station?.connectorsSummary ?? null,
                  priceRateMin: stationSelected?.[0]?.station?.priceRateMin ?? null,
                  priceRateMax: stationSelected?.[0]?.station?.priceRateMax ?? null
                })"""
            )
            interaction["open"] = await page.evaluate(
                """() => {
                  try {
                    const visible=[...document.querySelectorAll('.buttonConnectors')].find(e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length));
                    if (visible) { visible.click(); return {ok:true,via:'button'}; }
                    if (typeof showConnectors === 'function') { showConnectors(); return {ok:true,via:'function'}; }
                    return {ok:false,reason:'connector_open_unavailable'};
                  } catch(e) { return {ok:false,reason:String(e)}; }
                }"""
            )
            await page.wait_for_timeout(12000)
            interaction["currentConnectorsList"] = await page.evaluate(
                """() => Array.isArray(currentConnectorsList) ? currentConnectorsList.slice(0,10) : null"""
            )
        except Exception as exc:
            nav_error = f"{type(exc).__name__}: {exc}"

        interaction["finalUrl"] = page.url
        await browser.close()

    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "allowedPostEndpoints": sorted(POST_ALLOWLIST),
            "stationConnectorsOnlyForTarget": TARGET_NC_STATION_ID,
            "reservable": 0,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
            "accountActionsAllowed": False,
            "sessionMutationAllowed": False,
            "targetPUNOperator": TARGET_PUN_OPERATOR,
            "targetPUNEvses": TARGET_PUN_EVSES,
            "directCpoTariffAttributionEstablished": False,
            "publicationAllowed": False,
        },
        "navigationError": nav_error,
        "interaction": redact(interaction),
        "connectorResponses": connector_responses,
        "blockedNonGetRequests": [r for r in requests if r["method"] not in {"GET", "HEAD", "OPTIONS"} and not r["allowed"]],
        "allowedReadPosts": [r for r in requests if r.get("reason") == "validated_public_read_post"],
    }
    out = Path("artifacts/go_electric_nextcharge_station_connectors_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "navigationError": nav_error,
        "selection": interaction.get("selection"),
        "station": interaction.get("station"),
        "open": interaction.get("open"),
        "connectorResponses": [{k:v for k,v in x.items() if k in {"status","json","connectorCount","responseBytes"}} for x in connector_responses],
        "tariffFieldCounts": [len(x.get("tariffFields") or {}) for x in connector_responses],
        "currentConnectorsListLength": len(interaction.get("currentConnectorsList") or []),
    }, ensure_ascii=False, indent=2))

    if not any(x.get("status") == 200 and x.get("json") for x in connector_responses):
        raise SystemExit("no successful stationConnectors JSON response captured")


if __name__ == "__main__":
    asyncio.run(main())
