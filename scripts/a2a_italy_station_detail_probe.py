#!/usr/bin/env python3
"""Probe public A2A Emoving station details across infrastructure classes.

Research-only, read-only public access:
- loads the public A2A map in Chromium;
- calls only jsonGetMapDashboard and jsonGetCuFromAlias from that public page;
- selects representative A2A-owned stations across infrastructure types;
- stores normalized station/EVSE/plug fields, response shapes and price-like values;
- never calls recharge/auth/session endpoints and never persists cookies/tokens.
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE_PAGE = "https://e-movinghub.a2a.it/acEicp/publicMapCMS.action"
MAP_ENDPOINT = "jsonGetMapDashboard"
DETAIL_ENDPOINT = "jsonGetCuFromAlias"
OUT = Path("data/reports/a2a_italy_station_detail_probe.json")

PRICE_WORDS = (
    "price", "prezzo", "cost", "costo", "tariff", "tariffa", "fee", "penalty",
    "sosta", "occup", "parking", "minute", "minuto", "grace", "vat", "euro",
)
EVSE_WORDS = ("evse", "plug", "connector", "presa", "meter", "power", "kw", "status", "operator")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finite_number(value: Any) -> float | None:
    try:
        f = float(str(value).replace(",", "."))
        return f if math.isfinite(f) else None
    except Exception:
        return None


def shape(value: Any, depth: int = 0) -> Any:
    if depth >= 5:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): shape(v, depth + 1) for k, v in list(value.items())[:120]}
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "sampleShape": shape(value[0], depth + 1) if value else None,
        }
    return type(value).__name__


def walk_scalars(value: Any, path: str = "", out: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if out is None:
        out = []
    if isinstance(value, dict):
        for k, v in value.items():
            p = f"{path}.{k}" if path else str(k)
            walk_scalars(v, p, out)
    elif isinstance(value, list):
        for v in value[:20]:
            walk_scalars(v, f"{path}[]", out)
    elif value is None or isinstance(value, (str, int, float, bool)):
        out.append({"path": path, "value": value})
    return out


def relevant_scalars(value: Any, words: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for item in walk_scalars(value):
        p = item["path"].lower()
        if not any(w in p for w in words):
            continue
        key = (item["path"], json.dumps(item["value"], ensure_ascii=False, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        rows.append(item)
    return rows[:300]


def browser_post_json(driver: webdriver.Chrome, endpoint: str, payload: dict[str, Any], timeout_s: int = 30) -> dict[str, Any]:
    script = """
        const endpoint = arguments[0];
        const payload = arguments[1];
        const done = arguments[2];
        fetch(endpoint, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Content-Type': 'application/json;charset=utf-8'},
          body: JSON.stringify(payload)
        }).then(async r => {
          const text = await r.text();
          let data = null;
          try { data = JSON.parse(text); } catch (_) {}
          done({ok: r.ok, status: r.status, contentType: r.headers.get('content-type'), data: data, textPrefix: data === null ? text.slice(0,500) : null});
        }).catch(e => done({ok:false, status:null, error:String(e)}));
    """
    driver.set_script_timeout(timeout_s)
    result = driver.execute_async_script(script, endpoint, payload)
    return result if isinstance(result, dict) else {"ok": False, "error": "unexpected_browser_result"}


def is_a2a_owned(item: dict[str, Any]) -> bool:
    ap = item.get("assetProvider") if isinstance(item.get("assetProvider"), dict) else {}
    operator = str(ap.get("operatore") or item.get("operator") or "").upper()
    external = ap.get("external")
    # Public map JS treats external=false as the A2A network filter; operator name
    # is an additional guard for robustness across schema variants.
    return external is False or "A2A" in operator


def station_type(item: dict[str, Any]) -> str:
    return str(item.get("type") or item.get("typeDesc") or "UNKNOWN").upper().strip() or "UNKNOWN"


def score_station(item: dict[str, Any]) -> tuple[int, float, str]:
    status = str(item.get("statusCu") or "").upper()
    operational = status not in {"DISABLED", "MAINTENANCE", "UNREACHABLE"}
    max_power = finite_number(item.get("maxPower")) or 0.0
    return (1 if operational else 0, max_power, str(item.get("alias") or ""))


def choose_samples(items: list[dict[str, Any]], max_per_type: int = 2, max_total: int = 12) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if not isinstance(item, dict) or not is_a2a_owned(item):
            continue
        alias = str(item.get("alias") or "").strip()
        if not alias:
            continue
        groups[station_type(item)].append(item)
    selected = []
    preferred = ["SLOW", "QUICK", "FAST", "FAST_PLUS", "ULTRAFAST"]
    order = preferred + [t for t in sorted(groups) if t not in preferred]
    for typ in order:
        rows = sorted(groups.get(typ, []), key=score_station, reverse=True)
        selected.extend(rows[:max_per_type])
        if len(selected) >= max_total:
            break
    return selected[:max_total]


def normalize_plug(plug: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": plug.get("id"),
        "plugId": plug.get("plugId"),
        "uid": plug.get("uid"),
        "plugType": plug.get("plugType") or plug.get("type") or plug.get("typology"),
        "status": plug.get("status"),
        "maxPowerKw": finite_number(plug.get("maxPower")),
        "minPowerKw": finite_number(plug.get("minPower")),
        "currentPowerKw": finite_number(plug.get("currentPower")),
        "priceLikeScalars": relevant_scalars(plug, PRICE_WORDS),
    }


def normalize_detail(alias: str, detail: dict[str, Any], map_item: dict[str, Any]) -> dict[str, Any]:
    address = detail.get("address") if isinstance(detail.get("address"), dict) else {}
    provider = detail.get("assetProvider") if isinstance(detail.get("assetProvider"), dict) else {}
    groups = [g for g in (detail.get("groups") or []) if isinstance(g, dict)]
    evses = []
    for evse in detail.get("evseData") or []:
        if not isinstance(evse, dict):
            continue
        evses.append({
            "evseId": evse.get("evseId") or evse.get("id") or evse.get("uid"),
            "meterId": evse.get("meterId"),
            "status": evse.get("status"),
            "maxPowerKw": finite_number(evse.get("maxPower")),
            "plugs": [normalize_plug(p) for p in (evse.get("plugs") or []) if isinstance(p, dict)],
            "evseLikeScalars": relevant_scalars(evse, EVSE_WORDS),
            "priceLikeScalars": relevant_scalars(evse, PRICE_WORDS),
        })
    return {
        "alias": alias,
        "mapType": map_item.get("type"),
        "mapStatus": map_item.get("statusCu"),
        "mapName": map_item.get("name"),
        "mapCity": map_item.get("city"),
        "mapAddress": map_item.get("address"),
        "mapLat": map_item.get("lat"),
        "mapLon": map_item.get("long"),
        "detailName": detail.get("name") or detail.get("cuName"),
        "detailType": detail.get("type"),
        "detailTypeDesc": detail.get("typeDesc"),
        "detailStatus": detail.get("statusCu") or detail.get("status"),
        "maxPowerKw": finite_number(detail.get("maxPower")),
        "costobase": detail.get("costobase"),
        "descCostobase": detail.get("descCostobase"),
        "bookable": detail.get("bookable"),
        "isRechargeable": detail.get("isRechargeable"),
        "isBillable": detail.get("isBillable"),
        "operator": provider.get("operatore"),
        "providerId": provider.get("providerId"),
        "providerExternal": provider.get("external"),
        "address": {
            "street": address.get("street"),
            "postalCode": address.get("postalCode"),
            "city": address.get("city"),
        },
        "groups": groups,
        "evses": evses,
        "priceLikeScalars": relevant_scalars(detail, PRICE_WORDS),
        "evseLikeScalars": relevant_scalars(detail, EVSE_WORDS),
        "responseShape": shape(detail),
    }


def main() -> None:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,1600")
    opts.add_argument("--lang=it-IT")
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(BASE_PAGE)
        time.sleep(5)
        map_res = browser_post_json(driver, MAP_ENDPOINT, {"userNation": "IT"}, timeout_s=60)
        map_data = map_res.get("data")
        if not map_res.get("ok") or not isinstance(map_data, list):
            raise RuntimeError(f"A2A map endpoint failed: {map_res}")
        map_items = [x for x in map_data if isinstance(x, dict)]
        a2a_owned = [x for x in map_items if is_a2a_owned(x)]
        samples = choose_samples(map_items)
        if not samples:
            raise RuntimeError("No A2A-owned map samples selected")

        details = []
        failures = []
        for item in samples:
            alias = str(item.get("alias") or "").strip()
            res = browser_post_json(driver, DETAIL_ENDPOINT, {"aliasCu": alias}, timeout_s=45)
            data = res.get("data")
            if res.get("ok") and isinstance(data, dict):
                details.append(normalize_detail(alias, data, item))
            else:
                failures.append({
                    "alias": alias,
                    "type": item.get("type"),
                    "mapStatus": item.get("statusCu"),
                    "httpStatus": res.get("status"),
                    "error": res.get("error") or res.get("textPrefix"),
                })

        type_counts = Counter(station_type(x) for x in a2a_owned)
        status_counts = Counter(str(x.get("statusCu") or "UNKNOWN") for x in a2a_owned)
        direct_price_details = sum(1 for d in details if d.get("costobase") not in (None, ""))
        evse_count = sum(len(d.get("evses") or []) for d in details)
        plug_count = sum(len(e.get("plugs") or []) for d in details for e in (d.get("evses") or []))
        payload = {
            "generatedAt": now_iso(),
            "source": {
                "map": BASE_PAGE,
                "mapEndpoint": MAP_ENDPOINT,
                "detailEndpoint": DETAIL_ENDPOINT,
                "detailPayload": {"aliasCu": "<station alias>"},
            },
            "security": {
                "accountCredentialsUsed": False,
                "authorizationMaterialPersisted": False,
                "cookiesPersisted": False,
                "rechargeOrAuthEndpointsCalled": False,
            },
            "counts": {
                "mapRecords": len(map_items),
                "a2aOwnedMapRecords": len(a2a_owned),
                "a2aOwnedTypeCounts": dict(sorted(type_counts.items())),
                "a2aOwnedStatusCounts": dict(sorted(status_counts.items())),
                "selectedSamples": len(samples),
                "successfulDetails": len(details),
                "failedDetails": len(failures),
                "detailsWithCostobase": direct_price_details,
                "sampleEvseCount": evse_count,
                "samplePlugCount": plug_count,
            },
            "selectedMapSamples": [
                {k: x.get(k) for k in ("id", "alias", "name", "type", "statusCu", "maxPower", "city", "address", "lat", "long", "assetProvider")}
                for x in samples
            ],
            "details": details,
            "failures": failures,
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:60000])
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
