#!/usr/bin/env python3
"""Probe Duferco public station detail endpoint directly from the public web context.

Research-only/read-only:
- loads the public D-Mobility map;
- calls only known public GET Chargepoints/{id} detail URLs for station ids already
  observed in the public map response;
- sends no account credentials or copied request headers;
- never calls user/session/reservation/start-charge endpoints;
- persists only public station/connector fields useful for PUN reconciliation.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

PAGE = "https://mobility.dufercoenergia.com/"
API = "https://prod-apimp400.dufercoenergia.com/api/v4.0/Chargepoints"
STATION_IDS = [24808, 37078, 37088]
OUT = Path("data/reports/duferco_station_detail_direct_probe.json")


def safe_detail(j):
    if not isinstance(j, dict):
        return {"type": type(j).__name__}
    allow = (
        "id", "guid", "name", "address", "city", "prov", "lat", "long",
        "latitude", "longitude", "classType", "idChargeType", "poolType",
        "isInRoaming", "currentChargePointStatus", "maxPower", "power",
        "operator", "cpo", "provider", "parkingFee", "parkingFeeUnit", "currency",
    )
    out = {k: j.get(k) for k in allow if k in j}
    arrays = []
    for k, v in j.items():
        if not (isinstance(v, list) and v and isinstance(v[0], dict)):
            continue
        # Retain connector-like public arrays only.
        if not any(x in str(k).lower() for x in ("connector", "plug", "socket", "evse")):
            continue
        arrays.append(k)
        out[k] = [
            {x: c.get(x) for x in (
                "id", "connectorEVSEID", "evseId", "evseID", "plugId", "plugType",
                "status", "power", "maxPower", "current", "voltage", "price", "tariff",
                "parkingFee", "parkingFeeUnit", "currency",
            ) if x in c}
            for c in v[:30]
        ]
    out["_topKeys"] = sorted(j.keys())
    out["_connectorArrayKeys"] = arrays
    return out


def browser_get(driver, url):
    script = """
      const url=arguments[0], done=arguments[1];
      fetch(url,{method:'GET'}).then(async r=>{
        const t=await r.text(); let d=null;
        try{d=JSON.parse(t)}catch(_){}
        done({ok:r.ok,status:r.status,contentType:r.headers.get('content-type'),data:d,textPrefix:d===null?t.slice(0,300):null});
      }).catch(e=>done({ok:false,status:null,error:String(e)}));
    """
    driver.set_script_timeout(45)
    r = driver.execute_async_script(script, url)
    return r if isinstance(r, dict) else {"ok": False, "error": "unexpected_browser_result"}


def main():
    o = Options()
    for a in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=1440,1100", "--lang=it-IT"):
        o.add_argument(a)
    d = webdriver.Chrome(options=o)
    attempts = []
    try:
        d.set_page_load_timeout(60)
        d.get(PAGE)
        time.sleep(8)
        for sid in STATION_IDS:
            url = f"{API}/{sid}?lang=it"
            r = browser_get(d, url)
            item = {
                "stationId": sid,
                "urlPath": f"/api/v4.0/Chargepoints/{sid}",
                "ok": bool(r.get("ok")),
                "status": r.get("status"),
                "contentType": r.get("contentType"),
            }
            if r.get("ok") and isinstance(r.get("data"), dict):
                item["detail"] = safe_detail(r["data"])
            else:
                item["error"] = r.get("error") or r.get("textPrefix")
            attempts.append(item)
    finally:
        d.quit()

    evse_ids = []
    for a in attempts:
        detail = a.get("detail") or {}
        for k in detail.get("_connectorArrayKeys") or []:
            for c in detail.get(k) or []:
                x = c.get("connectorEVSEID") or c.get("evseId") or c.get("evseID")
                if x:
                    evse_ids.append(str(x))

    payload = {
        "source": {"page": PAGE, "apiRoot": API, "sampleStationIds": STATION_IDS},
        "security": {
            "accountCredentialsUsed": False,
            "copiedRequestHeadersUsed": False,
            "cookiesRead": False,
            "storageRead": False,
            "requestBodiesRead": False,
            "startChargeOrUserEndpointsCalled": False,
        },
        "counts": {
            "attempted": len(attempts),
            "successful": sum(1 for x in attempts if x.get("ok")),
            "connectorEvseIds": len(evse_ids),
        },
        "connectorEvseIds": evse_ids,
        "attempts": attempts,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": payload["counts"], "connectorEvseIds": evse_ids[:30], "statuses": [x.get("status") for x in attempts]}, ensure_ascii=False, indent=2))
    if payload["counts"]["successful"] == 0:
        raise RuntimeError("No public station detail call succeeded")
    if not evse_ids:
        raise RuntimeError("Public detail calls succeeded but no connector EVSE identifier was found")


if __name__ == "__main__":
    main()
