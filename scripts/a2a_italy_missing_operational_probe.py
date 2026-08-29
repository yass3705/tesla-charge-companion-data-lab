#!/usr/bin/env python3
"""Probe A2A-map aliases near operational PUN A2M EVSE lacking a direct tariff.

Research only. Geography is used only to select a small alias candidate set; a
recovery is reported only when an EVSE identifier from the detailed A2A record
matches the authoritative PUN EVSE exactly or by unique plug suffix. Nothing is
published or made rankable here.
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
from selenium.webdriver.chrome.options import Options

BASE_PAGE = "https://e-movinghub.a2a.it/acEicp/publicMapCMS.action"
MAP_ENDPOINT = "jsonGetMapDashboard"
DETAIL_ENDPOINT = "jsonGetCuFromAlias"
MAX_NEIGHBOR_M = 250.0


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fnum(v):
    try:
        x=float(str(v).replace(",","."))
        return x if math.isfinite(x) else None
    except Exception:
        return None


def coords(item):
    lat=fnum(item.get("lat")); lon=fnum(item.get("long"))
    return [lat,lon] if lat is not None and lon is not None else None


def haversine_m(a,b):
    if not a or not b: return None
    lat1,lon1,lat2,lon2=map(math.radians,[a[0],a[1],b[0],b[1]])
    dlat=lat2-lat1; dlon=lon2-lon1
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(h)))


def suffix(evse_id):
    p=str(evse_id or "").split("*",2)
    return p[2] if len(p)==3 else None


def browser_post(driver, endpoint, payload, timeout=60):
    script="""
      const endpoint=arguments[0],payload=arguments[1],done=arguments[2];
      fetch(endpoint,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json;charset=utf-8'},body:JSON.stringify(payload)})
        .then(async r=>{const t=await r.text();let d=null;try{d=JSON.parse(t)}catch(_){};done({ok:r.ok,status:r.status,data:d,error:d===null?t.slice(0,300):null});})
        .catch(e=>done({ok:false,status:null,data:null,error:String(e)}));
    """
    driver.set_script_timeout(timeout)
    return driver.execute_async_script(script,endpoint,payload)


def detail_evse_ids(detail):
    provider=detail.get("assetProvider") if isinstance(detail.get("assetProvider"),dict) else {}
    pid=str(provider.get("providerId") or "").strip().upper()
    out=[]
    for evse in detail.get("evseData") or []:
        if not isinstance(evse,dict): continue
        for plug in evse.get("plugs") or []:
            if not isinstance(plug,dict): continue
            plug_id=str(plug.get("plugId") or plug.get("id") or "").strip()
            if plug_id:
                out.append({
                    "providerId":pid,
                    "plugId":plug_id,
                    "constructedEvseId":f"IT*{pid}*{plug_id}" if pid else None,
                    "priceList":plug.get("priceList"),
                    "penaltyList":plug.get("penaltyList"),
                    "status":plug.get("status"),
                    "maxPower":plug.get("maxPower"),
                })
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pun",required=True)
    ap.add_argument("--a2a",required=True)
    ap.add_argument("--out",default="data/reports/a2a_italy_missing_operational_probe.json")
    args=ap.parse_args()

    with gzip.open(args.pun,"rt",encoding="utf-8") as f: pun=json.load(f)
    with gzip.open(args.a2a,"rt",encoding="utf-8") as f: a2a=json.load(f)
    covered={str(e.get("evseId")) for e in a2a.get("evses",[]) if e.get("rankableDirectTariff") is True}
    missing=[e for e in pun.get("evses",[]) if str(e.get("partyId") or "").upper()=="A2M" and e.get("operationalState")=="operational" and str(e.get("evseId")) not in covered]

    opts=Options()
    for x in ("--headless=new","--no-sandbox","--disable-dev-shm-usage","--window-size=1440,1600","--lang=it-IT"):
        opts.add_argument(x)
    driver=webdriver.Chrome(options=opts)
    try:
        driver.get(BASE_PAGE); time.sleep(5)
        mr=browser_post(driver,MAP_ENDPOINT,{"userNation":"IT"})
        if not isinstance(mr,dict) or not mr.get("ok") or not isinstance(mr.get("data"),list):
            raise RuntimeError(f"map failed {mr}")
        map_items=[x for x in mr["data"] if isinstance(x,dict) and str(x.get("alias") or "").strip() and coords(x)]

        neighbor_aliases={}
        alias_reasons=defaultdict(list)
        for pe in missing:
            pc=pe.get("coordinates")
            near=[]
            for mi in map_items:
                d=haversine_m(pc,coords(mi))
                if d is not None and d<=MAX_NEIGHBOR_M:
                    alias=str(mi.get("alias")).strip()
                    near.append((round(d,2),alias))
                    neighbor_aliases[alias]=mi
                    alias_reasons[alias].append(pe.get("evseId"))
            pe["probeNeighborAliases"]=[{"alias":a,"distanceM":d} for d,a in sorted(near)[:20]]

        details={}
        failures=[]
        for i,alias in enumerate(sorted(neighbor_aliases),1):
            r=browser_post(driver,DETAIL_ENDPOINT,{"aliasCu":alias})
            if isinstance(r,dict) and r.get("ok") and isinstance(r.get("data"),dict):
                details[alias]=r["data"]
            else:
                failures.append({"alias":alias,"status":r.get("status") if isinstance(r,dict) else None,"error":r.get("error") if isinstance(r,dict) else "unexpected"})
            if i%50==0 or i==len(neighbor_aliases):
                print(f"detail {i}/{len(neighbor_aliases)} ok={len(details)} failed={len(failures)}")
    finally:
        driver.quit()

    exact=[]; suffix_unique=[]; unresolved=[]
    all_detail_rows=[]
    for alias,d in details.items():
        mi=neighbor_aliases[alias]
        for row in detail_evse_ids(d):
            all_detail_rows.append({"alias":alias,"mapExternal":(mi.get("assetProvider") or {}).get("external") if isinstance(mi.get("assetProvider"),dict) else None,"mapOperator":(mi.get("assetProvider") or {}).get("operatore") if isinstance(mi.get("assetProvider"),dict) else None,**row})

    for pe in missing:
        target=str(pe.get("evseId")); target_suffix=suffix(target)
        neighbor_set={x["alias"] for x in pe.get("probeNeighborAliases",[])}
        rows=[r for r in all_detail_rows if r["alias"] in neighbor_set]
        ex=[r for r in rows if r.get("constructedEvseId")==target]
        sx=[r for r in rows if suffix(r.get("constructedEvseId"))==target_suffix]
        base={"punEvseId":target,"stationId":pe.get("stationId"),"status":pe.get("sourceStatus"),"powerKw":pe.get("maxPowerKw"),"coordinates":pe.get("coordinates"),"neighborAliases":pe.get("probeNeighborAliases",[])}
        if ex:
            exact.append({**base,"matches":ex})
        elif len(sx)==1:
            suffix_unique.append({**base,"matches":sx})
        else:
            unresolved.append({**base,"suffixMatches":sx[:20]})

    report={
        "generatedAt":now_iso(),
        "policy":"geography selects aliases only; recovery requires exact detailed EVSE ID or a unique detailed plug suffix",
        "counts":{
            "operationalPunA2mMissingBeforeProbe":len(missing),
            "mapRecordsWithAliasAndCoordinates":len(map_items),
            "neighborAliasesQueried":len(neighbor_aliases),
            "successfulDetails":len(details),
            "failedDetails":len(failures),
            "exactDetailedEvseRecoveries":len(exact),
            "uniqueSuffixDetailedRecoveries":len(suffix_unique),
            "unresolved":len(unresolved),
        },
        "mapProviderCounts":dict(Counter(str((x.get("assetProvider") or {}).get("providerId") if isinstance(x.get("assetProvider"),dict) else "") for x in neighbor_aliases.values())),
        "exactRecoveries":exact,
        "uniqueSuffixRecoveries":suffix_unique,
        "unresolved":unresolved,
        "failures":failures,
    }
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["counts"],ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
