#!/usr/bin/env python3
"""Validate the deterministic PUN GES <-> NextCharge uidConnector join across Italy.

PUN remains authoritative for CPO membership. The probe selects GES stations
near major Italian regions/cities, queries only tiny public NextCharge map boxes,
and accepts identity evidence only when:
    PUN evseId == 'ITGESE' + str(NextCharge uidConnector)
No geographic-only candidate is promoted. Tariff/status shapes are summarized
only for exact uid matches. No account, auth token, payment or charge endpoint is used.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options

MAP_URL = "https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
UID_PREFIX = "ITGESE"
ANCHORS = [
    ("Milano", 45.4642, 9.1900),
    ("Torino", 45.0703, 7.6869),
    ("Bologna", 44.4949, 11.3426),
    ("Roma", 41.9028, 12.4964),
    ("Napoli", 40.8518, 14.2681),
    ("Bari", 41.1171, 16.8719),
    ("Palermo", 38.1157, 13.3615),
    ("Catania", 37.5079, 15.0830),
]


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fnum(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def coords(e):
    c=e.get("coordinates")
    if isinstance(c,list) and len(c)>=2:
        a,b=fnum(c[0]),fnum(c[1]); return (a,b) if a is not None and b is not None else None
    if isinstance(c,dict):
        a=fnum(c.get("lat") or c.get("latitude")); b=fnum(c.get("lon") or c.get("lng") or c.get("longitude"))
        return (a,b) if a is not None and b is not None else None
    return None


def km(a,b):
    lat1,lon1,lat2,lon2=map(math.radians,[a[0],a[1],b[0],b[1]])
    dlat,dlon=lat2-lat1,lon2-lon1
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371*2*math.asin(min(1,math.sqrt(h)))


def pwr(e):
    for k in ("maxPowerKw","powerKw","maxPower","power"):
        x=fnum(e.get(k))
        if x is not None: return round(x,2)
    return None


def parse_uid(evse_id):
    s=str(evse_id or "").upper()
    if not s.startswith(UID_PREFIX): return None
    tail=s[len(UID_PREFIX):]
    return int(tail) if tail.isdigit() else None


def captcha(x):
    try: return "CAPTCHA_REQUIRED" in json.dumps(x,ensure_ascii=False).upper()
    except Exception: return False

ASYNC_FETCH=r"""
const done=arguments[arguments.length-1];
const path=arguments[0], params=arguments[1];
const ctrl=new AbortController(); const timer=setTimeout(()=>ctrl.abort(),20000);
fetch('/apps/map/apis/'+path,{method:'POST',credentials:'same-origin',signal:ctrl.signal,
 headers:{'client-type':'webapp','Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
 body:new URLSearchParams(params).toString()}).then(async r=>{clearTimeout(timer);const t=await r.text();let j=null;try{j=JSON.parse(t)}catch(e){};
 done({ok:r.ok,httpStatus:r.status,json:j,textPrefix:j?null:t.slice(0,500)});
}).catch(e=>{clearTimeout(timer);done({error:String(e&&e.name||e),message:String(e).slice(0,300)});});
"""


def api(driver,path,params): return driver.execute_async_script(ASYNC_FETCH,path,params)


def connector_pages(driver,sid,os_type,app_version,max_pages=4):
    rows=[]; seen=set(); failures=[]
    for page in range(max_pages):
        payload=api(driver,"stationConnectors",{
            "idStation":str(sid),"reservable":"0","limit":"100","offset":str(page*100),
            "osType":str(os_type),"appVersion":str(app_version),
        })
        if captcha(payload): return rows,"CAPTCHA_REQUIRED",failures
        if not isinstance(payload,dict) or not payload.get("ok"):
            failures.append({"page":page,"payload":payload}); break
        data=((payload.get("json") or {}).get("data") or [])
        if not isinstance(data,list): break
        added=0
        for c in data:
            uid=c.get("uidConnector") if isinstance(c,dict) else None
            key=str(uid) if uid is not None else json.dumps(c,sort_keys=True,default=str)[:300]
            if key not in seen:
                seen.add(key); rows.append(c); added+=1
        has_more=bool((payload.get("json") or {}).get("hasMore"))
        if not has_more and len(data)<100: break
        if not data or added==0: break
    return rows,None,failures


def select_targets(pun,per_anchor=3):
    grouped=defaultdict(list)
    for e in pun.get("evses",[]):
        if str(e.get("partyId") or "").upper()!="GES": continue
        c=coords(e); uid=parse_uid(e.get("evseId"))
        if not c or uid is None: continue
        key=str(e.get("stationId") or "") or f"{c[0]:.6f},{c[1]:.6f}"
        grouped[key].append(e)
    stations=[]
    for key,evses in grouped.items():
        c=coords(evses[0]);
        stations.append({
            "stationKey":key,"coordinates":c,
            "evseIds":sorted(str(e.get("evseId")) for e in evses if parse_uid(e.get("evseId")) is not None),
            "uids":sorted(parse_uid(e.get("evseId")) for e in evses if parse_uid(e.get("evseId")) is not None),
            "powersKw":sorted(x for x in (pwr(e) for e in evses) if x is not None),
            "sourceStatuses":dict(Counter(str(e.get("sourceStatus") or "UNKNOWN") for e in evses)),
        })
    selected=[]; used=set()
    for name,lat,lon in ANCHORS:
        ranked=sorted(stations,key=lambda s:km((lat,lon),s["coordinates"]))
        taken=0
        for s in ranked:
            if s["stationKey"] in used: continue
            dist=km((lat,lon),s["coordinates"])
            if dist>180: continue
            row=dict(s); row["anchor"]=name; row["anchorDistanceKm"]=round(dist,1)
            selected.append(row); used.add(s["stationKey"]); taken+=1
            if taken>=per_anchor: break
    return selected,len(stations)


def tariff_signature(c):
    tariff=(c.get("tariff") or {}) if isinstance(c,dict) else {}
    charge=(tariff.get("charge") or {}) if isinstance(tariff,dict) else {}
    prices=(charge.get("prices") or {}) if isinstance(charge,dict) else {}
    restrictions=(charge.get("restrictions") or {}) if isinstance(charge,dict) else {}
    return {
        "currency":tariff.get("currency"),
        "prices":{k:prices.get(k) for k in ("energy","time","parking","session") if prices.get(k) is not None},
        "restrictions":restrictions,
        "powerMax":c.get("powerMax"),"current":c.get("current"),"standard":c.get("standard"),"status":c.get("status"),
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--pun",required=True); ap.add_argument("--out",default="data/reports/ges_nextcharge_uid_stratified_probe.json"); args=ap.parse_args()
    with gzip.open(args.pun,"rt",encoding="utf-8") as fh: pun=json.load(fh)
    targets,total_stations=select_targets(pun,3)

    opts=Options(); opts.page_load_strategy="none"
    for x in ("--headless=new","--no-sandbox","--disable-dev-shm-usage","--window-size=1440,1600","--lang=it-IT","--disable-geolocation"): opts.add_argument(x)
    driver=webdriver.Chrome(options=opts); driver.set_script_timeout(30)
    browser_errors=[]; results=[]; stopped=None
    exact_evse=set(); targeted_evse=set(); price_component_counts=Counter(); price_values=Counter(); status_pairs=Counter(); candidate_station_ids=set();
    try:
        driver.set_page_load_timeout(20)
        try: driver.get(MAP_URL)
        except TimeoutException: browser_errors.append("page_load_timeout")
        time.sleep(7)
        runtime=driver.execute_script("""const s=n=>{try{return typeof window[n]==='undefined'?null:window[n]}catch(e){return null}};return {osType:s('osType'),appVersion:s('appVersion')};""") or {}
        os_type=runtime.get("osType") or "desktop"; app_version=runtime.get("appVersion") or "6.1.4"
        for target in targets:
            targeted_evse.update(target["evseIds"])
            lat,lon=target["coordinates"]
            # ~250-350 m box, then only <=100m station candidates are detailed.
            grid=api(driver,"stationsGrid",{
                "lonSW":str(lon-0.0045),"lonNE":str(lon+0.0045),"latSW":str(lat-0.0032),"latNE":str(lat+0.0032),
                "favorites":"false","userCountry":"IT","owner":"ITGES","osType":str(os_type),"appVersion":str(app_version),"idGroupProvider":"",
            })
            row={"target":target,"gridOk":bool(isinstance(grid,dict) and grid.get("ok")),"candidates":[],"matchedEvseIds":[]}
            if captcha(grid): stopped="CAPTCHA_REQUIRED"; results.append(row); break
            data=((grid.get("json") or {}).get("data") or []) if isinstance(grid,dict) else []
            near=[]
            for g in data if isinstance(data,list) else []:
                try: gc=(float(g.get("latitude")),float(g.get("longitude")))
                except Exception: continue
                d=km((lat,lon),gc)*1000
                if d<=100: near.append((d,g))
            near.sort(key=lambda x:x[0])
            target_uid_set=set(target["uids"])
            for d,g in near[:5]:
                sid=g.get("idStation")
                if sid is None: continue
                candidate_station_ids.add(str(sid))
                detail=api(driver,"station",{"idStation":str(sid),"osType":str(os_type),"appVersion":str(app_version)})
                if captcha(detail): stopped="CAPTCHA_REQUIRED"; break
                connectors,stop_reason,page_failures=connector_pages(driver,sid,os_type,app_version)
                if stop_reason: stopped=stop_reason; break
                matched=[]
                for c in connectors:
                    uid=c.get("uidConnector") if isinstance(c,dict) else None
                    try: uid_int=int(uid)
                    except Exception: continue
                    if uid_int not in target_uid_set: continue
                    eid=UID_PREFIX+str(uid_int)
                    matched.append({"evseId":eid,"uidConnector":uid_int,"tariff":tariff_signature(c)})
                    exact_evse.add(eid)
                    sig=tariff_signature(c)
                    for k,v in sig["prices"].items():
                        price_component_counts[k]+=1
                        if isinstance(v,(int,float)): price_values[f"{k}:{float(v):.6f}"]+=1
                    # PUN status for that exact EVSE vs NextCharge connector status.
                    pun_status="UNKNOWN"
                    for e in pun.get("evses",[]):
                        if str(e.get("evseId") or "").upper()==eid:
                            pun_status=str(e.get("sourceStatus") or "UNKNOWN"); break
                    status_pairs[f"{pun_status}->{str(c.get('status') or 'unknown')}"]+=1
                row["candidates"].append({
                    "idStation":str(sid),"distanceM":round(d,1),
                    "provider":(((detail.get("json") or {}).get("data") or {}).get("provider") if isinstance(detail,dict) else None),
                    "connectorCount":len(connectors),"pageFailures":page_failures,
                    "matched":matched,
                })
                row["matchedEvseIds"].extend(x["evseId"] for x in matched)
                # Exact uid identity is decisive; no need to query other co-located candidates once all target EVSE found.
                if set(row["matchedEvseIds"])>=set(target["evseIds"]): break
            results.append(row)
            if stopped: break
    finally:
        driver.quit()

    exact_target_stations=sum(1 for r in results if r.get("matchedEvseIds"))
    complete_target_stations=sum(1 for r in results if set(r.get("matchedEvseIds",[]))>=set(r["target"]["evseIds"]))
    report={
        "generatedAt":now_iso(),
        "joinRule":"PUN evseId == 'ITGESE' + decimal NextCharge uidConnector",
        "security":{"accountCredentialsUsed":False,"sessionTokenSent":False,"captchaBypassed":False,"paymentWalletChargeEndpointsCalled":False},
        "diagnostics":{"browserErrors":browser_errors,"stoppedReason":stopped},
        "counts":{
            "punGesStationCountParseable":total_stations,
            "targetsSelected":len(targets),"targetsCompleted":len(results),
            "targetedEvse":len(targeted_evse),"exactUidMatchedEvse":len(exact_evse),
            "exactUidEvseCoverage":round(len(exact_evse)/len(targeted_evse),6) if targeted_evse else 0,
            "targetsWithAnyExactUidMatch":exact_target_stations,
            "targetsWithCompleteExactUidCoverage":complete_target_stations,
            "uniqueNextChargeStationsDetailed":len(candidate_station_ids),
            "tariffComponentsOnMatchedConnectors":dict(price_component_counts),
            "tariffValueDistribution":dict(price_values),
            "statusPairs":dict(status_pairs),
        },
        "anchors":[x[0] for x in ANCHORS],
        "results":results,
    }
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:180000])

if __name__=="__main__": main()
