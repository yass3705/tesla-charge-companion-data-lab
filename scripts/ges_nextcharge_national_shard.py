#!/usr/bin/env python3
"""Extract one deterministic shard of PUN GES EVSE tariffs from public NextCharge.

Identity is exact only: PUN evseId ITGESE<n> <-> NextCharge uidConnector <n>.
PUN is authoritative for GES membership, station coordinates and health. The
NextCharge public app supplies a consumer/eMSP tariff snapshot and auxiliary
connector status. No geo-only tariff attribution is permitted.
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

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options

MAP_URL="https://nextcharge.app/map?location=44.4949%2C11.3426&nextcharge=only&lang=it"
PREFIX="ITGESE"
RECOGNIZED_PRICE_KEYS={"energy","time","parking","session"}


def now_iso(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def fnum(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None

def coords(e):
    c=e.get("coordinates")
    if isinstance(c,list) and len(c)>=2:
        a,b=fnum(c[0]),fnum(c[1]); return (a,b) if a is not None and b is not None else None
    if isinstance(c,dict):
        a=fnum(c.get("lat") or c.get("latitude")); b=fnum(c.get("lon") or c.get("lng") or c.get("longitude")); return (a,b) if a is not None and b is not None else None
    return None

def parse_uid(eid):
    s=str(eid or "").upper()
    if not s.startswith(PREFIX): return None
    t=s[len(PREFIX):]; return int(t) if t.isdigit() else None

def pwr(e):
    for k in ("maxPowerKw","powerKw","maxPower","power"):
        x=fnum(e.get(k))
        if x is not None: return round(x,3)
    return None

def dist_m(a,b):
    lat1,lon1,lat2,lon2=map(math.radians,[a[0],a[1],b[0],b[1]])
    dlat,dlon=lat2-lat1,lon2-lon1
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(h)))
def captcha(x):
    try:return "CAPTCHA_REQUIRED" in json.dumps(x,ensure_ascii=False).upper()
    except Exception:return False

ASYNC_FETCH=r"""
const done=arguments[arguments.length-1], path=arguments[0], params=arguments[1];
const ctrl=new AbortController(), timer=setTimeout(()=>ctrl.abort(),20000);
fetch('/apps/map/apis/'+path,{method:'POST',credentials:'same-origin',signal:ctrl.signal,
 headers:{'client-type':'webapp','Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
 body:new URLSearchParams(params).toString()}).then(async r=>{clearTimeout(timer);const t=await r.text();let j=null;try{j=JSON.parse(t)}catch(e){};
 done({ok:r.ok,httpStatus:r.status,json:j,textPrefix:j?null:t.slice(0,300)});
}).catch(e=>{clearTimeout(timer);done({error:String(e&&e.name||e),message:String(e).slice(0,220)});});
"""

def api(driver,path,params): return driver.execute_async_script(ASYNC_FETCH,path,params)

def connector_pages(driver,sid,os_type,app_version):
    out=[]; seen=set(); failures=[]
    for page in range(4):
        x=api(driver,"stationConnectors",{"idStation":str(sid),"reservable":"0","limit":"100","offset":str(page*100),"osType":str(os_type),"appVersion":str(app_version)})
        if captcha(x): return out,"CAPTCHA_REQUIRED",failures
        if not isinstance(x,dict) or not x.get("ok"):
            failures.append({"page":page,"httpStatus":x.get("httpStatus") if isinstance(x,dict) else None,"error":x.get("error") if isinstance(x,dict) else "invalid"}); break
        data=((x.get("json") or {}).get("data") or [])
        if not isinstance(data,list): break
        added=0
        for c in data:
            uid=c.get("uidConnector") if isinstance(c,dict) else None
            key=str(uid) if uid is not None else json.dumps(c,sort_keys=True,default=str)[:220]
            if key not in seen: seen.add(key); out.append(c); added+=1
        if not bool((x.get("json") or {}).get("hasMore")) and len(data)<100: break
        if not data or not added: break
    return out,None,failures

def target_groups(pun):
    groups=defaultdict(list); by_id={}
    malformed=[]
    for e in pun.get("evses",[]):
        if str(e.get("partyId") or "").upper()!="GES": continue
        eid=str(e.get("evseId") or "").upper(); uid=parse_uid(eid); c=coords(e)
        if uid is None or not c:
            malformed.append(eid); continue
        by_id[eid]=e
        key=str(e.get("stationId") or "") or f"{c[0]:.6f},{c[1]:.6f}"
        groups[key].append(e)
    rows=[]
    for key,es in groups.items():
        c=coords(es[0]); rows.append({"stationKey":key,"coords":c,"evses":es})
    rows.sort(key=lambda r:(r["stationKey"],r["coords"][0],r["coords"][1]))
    return rows,by_id,malformed

def tariff_snapshot(c):
    tariff=(c.get("tariff") or {}) if isinstance(c,dict) else {}
    charge=(tariff.get("charge") or {}) if isinstance(tariff,dict) else {}
    prices=(charge.get("prices") or {}) if isinstance(charge,dict) else {}
    restrictions=(charge.get("restrictions") or {}) if isinstance(charge,dict) else {}
    prices={str(k):v for k,v in prices.items()} if isinstance(prices,dict) else {}
    unknown=sorted(set(prices)-RECOGNIZED_PRICE_KEYS)
    numeric_known=bool(prices) and not unknown and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(float(v)) for v in prices.values())
    return {
        "currency":tariff.get("currency"),"prices":prices,"restrictions":restrictions,
        "preAuth":tariff.get("preAuth"),
        "recognizedPriceKeysOnly":not unknown,"unknownPriceKeys":unknown,
        "numericRecognizedPrices":numeric_known,
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--pun",required=True); ap.add_argument("--shard",type=int,required=True); ap.add_argument("--shards",type=int,default=4); ap.add_argument("--out-dir",default="data/shards/ges_nextcharge"); args=ap.parse_args()
    assert 0<=args.shard<args.shards
    with gzip.open(args.pun,"rt",encoding="utf-8") as fh: pun=json.load(fh)
    groups,by_id,malformed=target_groups(pun)
    targets=[g for i,g in enumerate(groups) if i%args.shards==args.shard]

    opts=Options(); opts.page_load_strategy="none"
    for x in ("--headless=new","--no-sandbox","--disable-dev-shm-usage","--window-size=1440,1600","--lang=it-IT","--disable-geolocation"): opts.add_argument(x)
    driver=webdriver.Chrome(options=opts); driver.set_script_timeout(30)
    browser_errors=[]; stopped=None; connector_cache={}; entries=[]; failures=[]; grid_cache={}; station_ids_seen=set();
    request_counts=Counter(); matched_ids=set(); targeted_ids=set(); tariff_components=Counter(); connector_statuses=Counter()
    try:
        driver.set_page_load_timeout(20)
        try: driver.get(MAP_URL)
        except TimeoutException: browser_errors.append("page_load_timeout")
        time.sleep(7)
        runtime=driver.execute_script("""const s=n=>{try{return typeof window[n]==='undefined'?null:window[n]}catch(e){return null}};return {osType:s('osType'),appVersion:s('appVersion')};""") or {}
        os_type=runtime.get("osType") or "desktop"; app_version=runtime.get("appVersion") or "6.1.4"
        for idx,target in enumerate(targets,1):
            es=target["evses"]; target_ids={str(e.get("evseId") or "").upper() for e in es}; targeted_ids.update(target_ids); target_uids={parse_uid(x) for x in target_ids}
            lat,lon=target["coords"]; gkey=f"{lat:.6f},{lon:.6f}"
            if gkey not in grid_cache:
                grid=api(driver,"stationsGrid",{"lonSW":str(lon-0.0045),"lonNE":str(lon+0.0045),"latSW":str(lat-0.0032),"latNE":str(lat+0.0032),"favorites":"false","userCountry":"IT","owner":"ITGES","osType":str(os_type),"appVersion":str(app_version),"idGroupProvider":""})
                request_counts["stationsGrid"]+=1; grid_cache[gkey]=grid
            else:grid=grid_cache[gkey]
            if captcha(grid): stopped="CAPTCHA_REQUIRED"; break
            if not isinstance(grid,dict) or not grid.get("ok"):
                failures.append({"stationKey":target["stationKey"],"kind":"grid","httpStatus":grid.get("httpStatus") if isinstance(grid,dict) else None}); continue
            data=((grid.get("json") or {}).get("data") or [])
            near=[]
            for g in data if isinstance(data,list) else []:
                try:gc=(float(g.get("latitude")),float(g.get("longitude")))
                except Exception:continue
                d=dist_m((lat,lon),gc)
                if d<=150: near.append((d,g))
            near.sort(key=lambda x:x[0])
            local_found=set()
            for d,g in near[:12]:
                sid=g.get("idStation")
                if sid is None:continue
                sid=str(sid); station_ids_seen.add(sid)
                if sid not in connector_cache:
                    cs,stop,page_fail=connector_pages(driver,sid,os_type,app_version); request_counts["stationConnectorsStations"]+=1; connector_cache[sid]=(cs,stop,page_fail)
                cs,stop,page_fail=connector_cache[sid]
                if stop: stopped=stop; break
                if page_fail: failures.append({"stationKey":target["stationKey"],"kind":"connectors","idStation":sid,"pages":page_fail})
                for c in cs:
                    try:uid=int(c.get("uidConnector"))
                    except Exception:continue
                    if uid not in target_uids:continue
                    eid=PREFIX+str(uid); pe=by_id.get(eid)
                    if not pe:continue
                    snap=tariff_snapshot(c)
                    entry={
                        "evseId":eid,"uidConnector":uid,"punStationId":pe.get("stationId"),"coordinates":list(coords(pe) or ()),
                        "punSourceStatus":pe.get("sourceStatus"),"punOperationalState":pe.get("operationalState"),"punPowerKw":pwr(pe),
                        "nextChargeStationId":sid,"nextChargeDistanceFromPunM":round(d,2),"nextChargeConnectorStatus":c.get("status"),
                        "nextChargePowerMaxKw":c.get("powerMax"),"current":c.get("current"),"standard":c.get("standard"),
                        "tariffSnapshot":snap,
                        "commercialLayer":"emsp","emsp":"NextCharge","billedBy":"Go Electric Stations S.r.l.s.",
                        "identityRule":"ITGESE + uidConnector","exactIdentityMatch":True,
                    }
                    entries.append(entry); matched_ids.add(eid); local_found.add(eid); connector_statuses[str(c.get("status") or "unknown")]+=1
                    for k,v in snap.get("prices",{}).items():
                        if v is not None: tariff_components[str(k)]+=1
                if local_found>=target_ids:break
            if stopped:break
            if idx%50==0: print(f"shard {args.shard} progress {idx}/{len(targets)} exact={len(matched_ids)} grids={request_counts['stationsGrid']} connectorStations={request_counts['stationConnectorsStations']}")
    finally:
        driver.quit()

    # Do not resolve duplicates here; merge job checks exact tariff conflicts globally.
    payload={
        "generatedAt":now_iso(),"shard":args.shard,"shards":args.shards,
        "security":{"accountCredentialsUsed":False,"sessionTokenSent":False,"captchaBypassed":False,"paymentWalletChargeEndpointsCalled":False},
        "diagnostics":{"browserErrors":browser_errors,"stoppedReason":stopped},
        "counts":{"totalParseableGesStations":len(groups),"targetStations":len(targets),"targetEvse":len(targeted_ids),"exactMatchedEvse":len(matched_ids),"rawEntryRows":len(entries),"uniqueNextChargeStationsQueried":len(station_ids_seen),"failures":len(failures),"requestCounts":dict(request_counts),"tariffComponents":dict(tariff_components),"connectorStatuses":dict(connector_statuses),"malformedGesEvseIds":len(malformed)},
        "failures":failures[:1000],"entries":entries,
    }
    outdir=Path(args.out_dir); outdir.mkdir(parents=True,exist_ok=True); out=outdir/f"ges_nextcharge_shard_{args.shard}.json.gz"
    with gzip.open(out,"wt",encoding="utf-8") as fh: json.dump(payload,fh,ensure_ascii=False,separators=(",",":"))
    report=outdir/f"ges_nextcharge_shard_{args.shard}_report.json"; report.write_text(json.dumps({k:v for k,v in payload.items() if k not in ("entries","failures")}|{"failureSample":failures[:30]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload["counts"],ensure_ascii=False,indent=2)); print(json.dumps(payload["diagnostics"],ensure_ascii=False,indent=2))

if __name__=="__main__":main()
