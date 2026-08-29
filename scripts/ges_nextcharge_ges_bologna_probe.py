#!/usr/bin/env python3
"""Bounded GES-only validation of public NextCharge station and connector data.

Uses the public NextCharge web-map endpoints with owner=ITGES, no account,
credentials or session token. At most 10 station detail/connector calls are
made. CAPTCHA is never bypassed; if requested, the probe stops.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
OUT = Path("data/reports/ges_nextcharge_ges_bologna_probe.json")
SENSITIVE_RE = re.compile(r"(token|cookie|session|email|phone|password|secret|card|payment|user.?id|device.?key)", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize(x: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "<depth-limit>"
    if isinstance(x, dict):
        out = {}
        for k, v in list(x.items())[:250]:
            if SENSITIVE_RE.search(str(k)):
                out[str(k)] = "<redacted>"
            else:
                out[str(k)] = sanitize(v, depth + 1)
        return out
    if isinstance(x, list):
        return [sanitize(v, depth + 1) for v in x[:120]]
    if isinstance(x, str):
        return x[:1200]
    if isinstance(x, (int, float, bool)) or x is None:
        return x
    return str(x)[:1200]


ASYNC_FETCH = r"""
const done = arguments[arguments.length - 1];
const path = arguments[0];
const params = arguments[1];
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 20000);
const options = {
  method: 'POST',
  headers: {'client-type':'webapp', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
  signal: controller.signal,
  credentials: 'same-origin',
  body: new URLSearchParams(params).toString()
};
fetch('/apps/map/apis/' + path, options).then(async r => {
  clearTimeout(timer);
  const text = await r.text();
  let parsed = null;
  try { parsed = JSON.parse(text); } catch(e) {}
  done({ok:r.ok, httpStatus:r.status, urlPath:new URL(r.url).pathname, json:parsed,
        textPrefix: parsed ? null : text.slice(0,1200)});
}).catch(e => {clearTimeout(timer); done({error:String(e && e.name || e), message:String(e).slice(0,400)});});
"""


def is_captcha(payload: Any) -> bool:
    try:
        return "CAPTCHA_REQUIRED" in json.dumps(payload, ensure_ascii=False).upper()
    except Exception:
        return False


def station_rows(payload: Any) -> list[dict]:
    try:
        rows = payload["json"]["data"]
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def main() -> None:
    opts = Options()
    opts.page_load_strategy = "none"
    for arg in (
        "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
        "--window-size=1440,1600", "--lang=it-IT", "--disable-geolocation",
    ):
        opts.add_argument(arg)

    driver = webdriver.Chrome(options=opts)
    driver.set_script_timeout(30)
    browser_errors = []
    try:
        driver.set_page_load_timeout(20)
        try:
            driver.get(MAP_URL)
        except TimeoutException:
            browser_errors.append("page_load_timeout")
        time.sleep(8)

        runtime = driver.execute_script("""
          const safe = n => { try { return typeof window[n] === 'undefined' ? null : window[n]; } catch(e) { return null; } };
          return {origin: location.origin, osType: safe('osType'), appVersion: safe('appVersion'), country: safe('country'), owner: safe('owner')};
        """)
        os_type = (runtime or {}).get("osType") or "desktop"
        app_version = (runtime or {}).get("appVersion") or "6.1.4"
        owner = (runtime or {}).get("owner") or "ITGES"
        # Fail closed: this probe is specifically for the NextCharge/Go Electric owner.
        if str(owner).upper() != "ITGES":
            owner = "ITGES"

        grid_params = {
            "lonSW": "11.28", "lonNE": "11.40", "latSW": "44.45", "latNE": "44.55",
            "favorites": "false", "userCountry": "IT", "owner": str(owner),
            "osType": str(os_type), "appVersion": str(app_version), "idGroupProvider": "",
        }
        grid = driver.execute_async_script(ASYNC_FETCH, "stationsGrid", grid_params)
        rows = station_rows(grid)

        result = {
            "generatedAt": now_iso(),
            "scope": {"name":"Bologna", "latSW":44.45, "latNE":44.55, "lonSW":11.28, "lonNE":11.40},
            "runtime": sanitize(runtime),
            "requestPolicy": {"owner":"ITGES", "maxStationDetails":10, "userCountry":"IT"},
            "security": {
                "accountCredentialsUsed": False,
                "sessionTokenSent": False,
                "loginOrRegistrationPerformed": False,
                "paymentWalletChargeEndpointsCalled": False,
                "captchaBypassed": False,
                "headersCookiesStoragePersisted": False,
            },
            "diagnostics": {"browserErrors": browser_errors},
            "grid": sanitize(grid),
            "counts": {"gridStations": len(rows), "hasMore": bool(((grid.get('json') or {}).get('hasMore')) if isinstance(grid, dict) else False)},
            "details": [],
        }
        if is_captcha(grid):
            result["stoppedReason"] = "CAPTCHA_REQUIRED"
        else:
            provider_counter = Counter()
            tariff_component_counter = Counter()
            connector_count = 0
            priced_connector_count = 0
            for item in rows[:10]:
                sid = item.get("idStation")
                if sid is None:
                    continue
                common = {"idStation": str(sid), "osType": str(os_type), "appVersion": str(app_version)}
                detail = driver.execute_async_script(ASYNC_FETCH, "station", common)
                row = {"idStation": str(sid), "grid": sanitize(item), "station": sanitize(detail)}
                if is_captcha(detail):
                    row["connectorsSkipped"] = "CAPTCHA_REQUIRED"
                    result["details"].append(row)
                    result["stoppedReason"] = "CAPTCHA_REQUIRED"
                    break
                try:
                    provider = detail["json"]["data"].get("provider")
                    if provider:
                        provider_counter[str(provider)] += 1
                except Exception:
                    pass
                conn_params = {**common, "reservable":"0", "limit":"50", "offset":"0"}
                connectors = driver.execute_async_script(ASYNC_FETCH, "stationConnectors", conn_params)
                row["connectors"] = sanitize(connectors)
                result["details"].append(row)
                if is_captcha(connectors):
                    result["stoppedReason"] = "CAPTCHA_REQUIRED"
                    break
                try:
                    conn_rows = connectors["json"].get("data") or []
                    if isinstance(conn_rows, list):
                        connector_count += len(conn_rows)
                        for c in conn_rows:
                            prices = (((c.get("tariff") or {}).get("charge") or {}).get("prices") or {})
                            if isinstance(prices, dict) and prices:
                                priced_connector_count += 1
                                for key, val in prices.items():
                                    if val is not None:
                                        tariff_component_counter[str(key)] += 1
                except Exception:
                    pass
            result["counts"].update({
                "detailsFetched": len(result["details"]),
                "connectorsObserved": connector_count,
                "pricedConnectorsObserved": priced_connector_count,
                "providersInSample": dict(provider_counter),
                "tariffComponentsInSample": dict(tariff_component_counter),
            })

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:180000])
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
