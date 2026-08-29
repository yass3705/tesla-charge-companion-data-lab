#!/usr/bin/env python3
"""Bounded read-only validation of public NextCharge station endpoints.

Loads the public web map and issues the same-origin station-list/detail/connector
requests used by the frontend, without account credentials or session tokens.
The probe is intentionally tiny (Bologna bbox, max 3 station details). If the
service requests CAPTCHA, the probe records that state and stops; it never
attempts to bypass challenges.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
OUT = Path("data/reports/ges_nextcharge_bologna_data_probe.json")
SENSITIVE_RE = re.compile(r"(token|cookie|session|email|phone|password|secret|card|payment|user.?id|device.?key)", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize(x: Any, depth: int = 0) -> Any:
    if depth > 7:
        return "<depth-limit>"
    if isinstance(x, dict):
        out = {}
        for k, v in list(x.items())[:200]:
            if SENSITIVE_RE.search(str(k)):
                out[str(k)] = "<redacted>"
            else:
                out[str(k)] = sanitize(v, depth + 1)
        return out
    if isinstance(x, list):
        return [sanitize(v, depth + 1) for v in x[:80]]
    if isinstance(x, str):
        return x[:1000]
    if isinstance(x, (int, float, bool)) or x is None:
        return x
    return str(x)[:1000]


ASYNC_FETCH = r"""
const done = arguments[arguments.length - 1];
const path = arguments[0];
const params = arguments[1];
const method = arguments[2] || 'POST';
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 20000);
const options = {
  method,
  headers: {'client-type':'webapp', 'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
  signal: controller.signal,
  credentials: 'same-origin'
};
let url = '/apps/map/apis/' + path;
if (method === 'GET') {
  url += '?' + new URLSearchParams(params).toString();
} else {
  options.body = new URLSearchParams(params).toString();
}
fetch(url, options).then(async r => {
  clearTimeout(timer);
  const text = await r.text();
  let parsed = null;
  try { parsed = JSON.parse(text); } catch(e) {}
  done({ok:r.ok, httpStatus:r.status, urlPath:new URL(r.url).pathname, json:parsed,
        textPrefix: parsed ? null : text.slice(0,1200)});
}).catch(e => {clearTimeout(timer); done({error:String(e && e.name || e), message:String(e).slice(0,400)});});
"""


def flatten_station_candidates(data: Any) -> list[dict]:
    candidates = []
    seen = set()
    def walk(x: Any):
        if isinstance(x, dict):
            # Most NextCharge map station rows expose idStation directly.
            sid = x.get("idStation") or x.get("id_station") or x.get("stationId")
            if sid is not None and str(sid) not in seen:
                seen.add(str(sid))
                candidates.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    return candidates


def is_captcha(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    text = json.dumps(payload, ensure_ascii=False).upper()
    return "CAPTCHA_REQUIRED" in text


def main() -> None:
    opts = Options()
    opts.page_load_strategy = "none"
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1600", "--lang=it-IT", "--disable-geolocation"):
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
        os_type = runtime.get("osType") if isinstance(runtime, dict) else None
        app_version = runtime.get("appVersion") if isinstance(runtime, dict) else None
        params = {
            "lonSW": "11.28", "lonNE": "11.40", "latSW": "44.45", "latNE": "44.55",
            "favorites": "false", "userCountry": "IT", "owner": "",
            "osType": "" if os_type is None else str(os_type),
            "appVersion": "" if app_version is None else str(app_version),
            "idGroupProvider": "",
        }

        grid = driver.execute_async_script(ASYNC_FETCH, "stationsGrid", params, "POST")
        payload = {
            "generatedAt": now_iso(),
            "scope": {"name":"Bologna", "latSW":44.45, "latNE":44.55, "lonSW":11.28, "lonNE":11.40},
            "runtime": sanitize(runtime),
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
            "details": [],
        }

        if is_captcha(grid):
            payload["stoppedReason"] = "CAPTCHA_REQUIRED"
        else:
            grid_json = grid.get("json") if isinstance(grid, dict) else None
            stations = flatten_station_candidates(grid_json)
            payload["stationCandidateCount"] = len(stations)
            payload["stationCandidatesSample"] = sanitize(stations[:10])
            for station in stations[:3]:
                sid = station.get("idStation") or station.get("id_station") or station.get("stationId")
                detail_params = {
                    "idStation": str(sid),
                    "osType": "" if os_type is None else str(os_type),
                    "appVersion": "" if app_version is None else str(app_version),
                }
                detail = driver.execute_async_script(ASYNC_FETCH, "station", detail_params, "POST")
                row = {"idStation": str(sid), "station": sanitize(detail)}
                if is_captcha(detail):
                    row["connectorsSkipped"] = "CAPTCHA_REQUIRED"
                    payload["details"].append(row)
                    continue
                connectors_params = {
                    "idStation": str(sid), "reservable": "0", "limit": "30", "offset": "0",
                    "osType": "" if os_type is None else str(os_type),
                    "appVersion": "" if app_version is None else str(app_version),
                }
                connectors = driver.execute_async_script(ASYNC_FETCH, "stationConnectors", connectors_params, "POST")
                row["connectors"] = sanitize(connectors)
                payload["details"].append(row)
                if is_captcha(connectors):
                    payload["stoppedReason"] = "CAPTCHA_REQUIRED"
                    break

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:150000])
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
