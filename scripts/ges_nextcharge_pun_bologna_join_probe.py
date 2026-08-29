#!/usr/bin/env python3
"""PUN-driven GES -> NextCharge join probe around Bologna.

PUN partyId GES is authoritative for which EVSE belong to Go Electric Stations.
For a bounded sample of GES stations in Bologna, query tiny NextCharge map boxes
around the PUN coordinates, then inspect at most three nearby station candidates.
No candidate becomes rankable here: exact-ID evidence and geo/power evidence are
reported separately so later national logic can fail closed.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
SENSITIVE_RE = re.compile(r"(token|cookie|session|email|phone|password|secret|card|payment|user.?id|device.?key)", re.I)
EVSE_RE = re.compile(r"IT\*GES\*[A-Za-z0-9*_.:-]+", re.I)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def haversine_m(a, b):
    if not a or not b:
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2-lat1, lon2-lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def sanitize(x: Any, depth=0):
    if depth > 8:
        return "<depth-limit>"
    if isinstance(x, dict):
        out = {}
        for k, v in list(x.items())[:250]:
            out[str(k)] = "<redacted>" if SENSITIVE_RE.search(str(k)) else sanitize(v, depth+1)
        return out
    if isinstance(x, list):
        return [sanitize(v, depth+1) for v in x[:120]]
    if isinstance(x, str):
        return x[:1200]
    if isinstance(x, (int, float, bool)) or x is None:
        return x
    return str(x)[:1200]


def recursive_strings(x: Any):
    if isinstance(x, dict):
        for k, v in x.items():
            yield str(k)
            yield from recursive_strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from recursive_strings(v)
    elif isinstance(x, str):
        yield x


def explicit_ges_ids(x: Any):
    found = set()
    for s in recursive_strings(x):
        for m in EVSE_RE.finditer(s):
            found.add(m.group(0).upper())
    return sorted(found)


def pun_coords(e):
    c = e.get("coordinates")
    if isinstance(c, list) and len(c) >= 2:
        lat, lon = fnum(c[0]), fnum(c[1])
        return [lat, lon] if lat is not None and lon is not None else None
    if isinstance(c, dict):
        lat = fnum(c.get("lat") or c.get("latitude")); lon = fnum(c.get("lon") or c.get("lng") or c.get("longitude"))
        return [lat, lon] if lat is not None and lon is not None else None
    return None


def pwr(e):
    for k in ("maxPowerKw", "powerKw", "maxPower", "power"):
        x = fnum(e.get(k))
        if x is not None:
            return round(x, 3)
    return None


def normalize_powers(values):
    return sorted(round(float(x), 1) for x in values if x is not None)


ASYNC_FETCH = r"""
const done = arguments[arguments.length - 1];
const path = arguments[0];
const params = arguments[1];
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 20000);
fetch('/apps/map/apis/' + path, {
  method:'POST', credentials:'same-origin', signal:controller.signal,
  headers:{'client-type':'webapp','Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
  body:new URLSearchParams(params).toString()
}).then(async r=>{clearTimeout(timer);const t=await r.text();let j=null;try{j=JSON.parse(t)}catch(e){};
  done({ok:r.ok,httpStatus:r.status,json:j,textPrefix:j?null:t.slice(0,800)});
}).catch(e=>{clearTimeout(timer);done({error:String(e&&e.name||e),message:String(e).slice(0,300)});});
"""


def captcha(x):
    try: return "CAPTCHA_REQUIRED" in json.dumps(x, ensure_ascii=False).upper()
    except Exception: return False


def api(driver, path, params):
    return driver.execute_async_script(ASYNC_FETCH, path, params)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pun", required=True)
    ap.add_argument("--out", default="data/reports/ges_nextcharge_pun_bologna_join_probe.json")
    args = ap.parse_args()

    with gzip.open(args.pun, "rt", encoding="utf-8") as fh:
        pun = json.load(fh)

    # Broad Bologna sample; PUN decides CPO ownership.
    ges = []
    for e in pun.get("evses", []):
        if str(e.get("partyId") or "").upper() != "GES":
            continue
        c = pun_coords(e)
        if not c:
            continue
        if 44.40 <= c[0] <= 44.60 and 11.20 <= c[1] <= 11.50:
            ges.append(e)

    grouped = defaultdict(list)
    for e in ges:
        c = pun_coords(e)
        key = str(e.get("stationId") or "") or f"{c[0]:.5f},{c[1]:.5f}"
        grouped[key].append(e)

    targets = []
    for key, evses in grouped.items():
        coords = pun_coords(evses[0])
        targets.append({
            "stationKey": key,
            "coordinates": coords,
            "evseIds": sorted(str(e.get("evseId")) for e in evses if e.get("evseId")),
            "powersKw": normalize_powers(pwr(e) for e in evses),
            "operationalStates": dict(Counter(str(e.get("operationalState") or "unknown") for e in evses)),
            "sourceStatuses": dict(Counter(str(e.get("sourceStatus") or "unknown") for e in evses)),
        })
    targets.sort(key=lambda x: (x["coordinates"][0], x["coordinates"][1], x["stationKey"]))
    targets = targets[:12]

    opts = Options(); opts.page_load_strategy = "none"
    for x in ("--headless=new","--no-sandbox","--disable-dev-shm-usage","--window-size=1440,1600","--lang=it-IT","--disable-geolocation"):
        opts.add_argument(x)
    driver = webdriver.Chrome(options=opts)
    driver.set_script_timeout(30)
    browser_errors=[]
    results=[]
    stopped=None
    try:
        driver.set_page_load_timeout(20)
        try: driver.get(MAP_URL)
        except TimeoutException: browser_errors.append("page_load_timeout")
        time.sleep(7)
        runtime = driver.execute_script("""
          const safe=n=>{try{return typeof window[n]==='undefined'?null:window[n]}catch(e){return null}};
          return {osType:safe('osType'),appVersion:safe('appVersion'),owner:safe('owner')};
        """) or {}
        os_type = runtime.get("osType") or "desktop"; app_version = runtime.get("appVersion") or "6.1.4"

        for target in targets:
            lat, lon = target["coordinates"]
            # ~350m box, small enough to avoid grid truncation in normal urban density.
            dlat, dlon = 0.0032, 0.0045
            grid_params={
                "lonSW":str(lon-dlon),"lonNE":str(lon+dlon),"latSW":str(lat-dlat),"latNE":str(lat+dlat),
                "favorites":"false","userCountry":"IT","owner":"ITGES","osType":str(os_type),"appVersion":str(app_version),"idGroupProvider":"",
            }
            grid=api(driver,"stationsGrid",grid_params)
            row={"pun":target,"gridMeta":sanitize({k:v for k,v in (grid or {}).items() if k != 'json'}),"candidates":[]}
            if captcha(grid): stopped="CAPTCHA_REQUIRED"; results.append(row); break
            grid_rows=[]
            try:
                grid_rows=(grid.get("json") or {}).get("data") or []
            except Exception: pass
            near=[]
            for g in grid_rows if isinstance(grid_rows,list) else []:
                gc=[fnum(g.get("latitude")),fnum(g.get("longitude"))]
                if None in gc: continue
                d=haversine_m([lat,lon],gc)
                if d is not None and d <= 180:
                    near.append((d,g))
            near.sort(key=lambda x:x[0])
            for d,g in near[:3]:
                sid=g.get("idStation")
                if sid is None: continue
                common={"idStation":str(sid),"osType":str(os_type),"appVersion":str(app_version)}
                detail=api(driver,"station",common)
                if captcha(detail): stopped="CAPTCHA_REQUIRED"; break
                conns=api(driver,"stationConnectors",{**common,"reservable":"0","limit":"50","offset":"0"})
                if captcha(conns): stopped="CAPTCHA_REQUIRED"; break
                detail_data=((detail.get("json") or {}).get("data") or {}) if isinstance(detail,dict) else {}
                conn_rows=((conns.get("json") or {}).get("data") or []) if isinstance(conns,dict) else []
                cpowers=normalize_powers(fnum(c.get("powerMax")) for c in conn_rows if isinstance(c,dict))
                explicit=explicit_ges_ids({"detail":detail_data,"connectors":conn_rows})
                target_ids={x.upper() for x in target["evseIds"]}
                exact=sorted(target_ids.intersection(explicit))
                # Report, don't promote, a deterministic geo+power candidate.
                row["candidates"].append({
                    "idStation":str(sid),"distanceM":round(d,2),
                    "provider":detail_data.get("provider"),"status":detail_data.get("status"),
                    "coordinates":[detail_data.get("latitude"),detail_data.get("longitude")],
                    "connectorPowersKw":cpowers,
                    "punPowersKw":target["powersKw"],
                    "powerSignatureExact":cpowers==target["powersKw"],
                    "explicitGesEvseIds":explicit,
                    "exactPunEvseIds":exact,
                    "connectors":sanitize(conn_rows),
                })
            row["candidateCountWithin180m"]=len(near)
            results.append(row)
            if stopped: break

    finally:
        driver.quit()

    exact_target_count=sum(1 for r in results if any(c.get("exactPunEvseIds") for c in r.get("candidates",[])))
    unique_geo_power=sum(1 for r in results if len([c for c in r.get("candidates",[]) if c.get("distanceM",999)<=80 and c.get("powerSignatureExact")])==1)
    report={
        "generatedAt":now_iso(),
        "policy":"PUN selects partyId GES; geography only selects nearby NextCharge candidates; exact EVSE IDs and geo+power evidence are reported separately; nothing is rankable in this probe.",
        "security":{"accountCredentialsUsed":False,"sessionTokenSent":False,"captchaBypassed":False,"paymentWalletChargeEndpointsCalled":False},
        "diagnostics":{"browserErrors":browser_errors,"stoppedReason":stopped},
        "counts":{"punGesEvseInBolognaBox":len(ges),"punGesStationsInBolognaBox":len(grouped),"targetsProbed":len(results),"targetsWithExactEvseEvidence":exact_target_count,"targetsWithUniqueGeoPowerCandidateWithin80m":unique_geo_power},
        "results":results,
    }
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:180000])

if __name__=="__main__":
    main()
