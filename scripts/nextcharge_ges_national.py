#!/usr/bin/env python3
from __future__ import annotations
import gzip, json, math, re, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

BASE="https://nextcharge.app.apis.goelectricstations.com/apis"
PUN=Path("data/national/pun_italy_national.json.gz")
OUT=Path("data/reports/nextcharge_ges_national_report.json")
DATA=Path("data/national/nextcharge_ges_national.json.gz")
UA="NextCharge/6.2.02 Android"
MAX_DISTANCE_M=100.0
WORKERS=12

def post(path,data,attempts=3):
    last=None
    for i in range(attempts):
        try:
            r=requests.post(BASE+path,data=data,headers={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"},timeout=(8,25))
            row={"httpStatus":r.status_code}
            try: row["json"]=r.json()
            except Exception: row["textPrefix"]=r.text[:500]
            if r.status_code in (429,500,502,503,504):
                last=row; time.sleep(0.5*(2**i)); continue
            return row
        except Exception as e:
            last={"error":f"{type(e).__name__}: {e}"}
            time.sleep(0.5*(2**i))
    return last or {"error":"unknown"}

def hav(a,b,c,d):
    R=6371000.0
    p1,p2=math.radians(a),math.radians(c)
    dp=math.radians(c-a); dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(min(1.0,math.sqrt(x)))

def numeric_suffix(evse):
    s=str(evse)
    m=re.search(r'(\d+)$',s)
    return int(m.group(1)) if m else None

def norm_ref(v):
    return re.sub(r'[^A-Z0-9]','',str(v or '').upper())

def list_data(resp):
    o=resp.get("json") if isinstance(resp,dict) else None
    if not isinstance(o,dict) or o.get("status")!="OK": return []
    d=o.get("data")
    if isinstance(d,list): return d
    if isinstance(d,dict):
        for k in ("results","stations","data","connectors"):
            if isinstance(d.get(k),list): return d[k]
    return []

def tariff_row(c):
    t=c.get("tariff") if isinstance(c.get("tariff"),dict) else {}
    ch=t.get("charge") if isinstance(t.get("charge"),dict) else {}
    prices=ch.get("prices") if isinstance(ch.get("prices"),dict) else {}
    restrictions=ch.get("restrictions") if isinstance(ch.get("restrictions"),dict) else {}
    return {
      "currency":t.get("currency"),
      "energy":prices.get("energy"),
      "parking":prices.get("parking"),
      "time":prices.get("time"),
      "session":prices.get("session"),
      "paymentRequired":ch.get("paymentRequired"),
      "preAuth":ch.get("preAuth"),
      "restrictions":restrictions,
    }

pun=json.loads(gzip.decompress(PUN.read_bytes()))
ges=[e for e in pun.get("evses",[]) if isinstance(e,dict) and e.get("partyId")=="GES" and e.get("evseId") and isinstance(e.get("coordinates"),list) and len(e["coordinates"])>=2]
by_station=defaultdict(list)
for e in ges:
    by_station[str(e.get("stationId") or e.get("evseId"))].append(e)
stations=list(by_station.items())

def process(item):
    sid,evses=item
    lat=float(evses[0]["coordinates"][0]); lon=float(evses[0]["coordinates"][1])
    near_form={"latitude":str(lat),"longitude":str(lon),"limit":"20","includeHighway":"1","includeNextcharge":"1","favorites":"0","osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":""}
    near=post("/stationsNear",near_form)
    candidates=[]
    for st in list_data(near):
        if not isinstance(st,dict): continue
        try: d=hav(lat,lon,float(st.get("latitude")),float(st.get("longitude")))
        except Exception: continue
        if d<=MAX_DISTANCE_M:
            candidates.append((d,st))
    candidates.sort(key=lambda x:x[0])
    grid=None
    grid_candidates=[]
    # Second pass from the exact APK-observed stationsGrid form. This is only
    # discovery: acceptance still requires an exact connector identifier match.
    if not candidates:
        grid_form={
          "lonSW":str(lon-GRID_HALFSPAN_DEG),"latSW":str(lat-GRID_HALFSPAN_DEG),
          "lonNE":str(lon+GRID_HALFSPAN_DEG),"latNE":str(lat+GRID_HALFSPAN_DEG),
          "statusStation":"","UID":"","includeNextcharge":"1","includeHighway":"1",
          "favorites":"0","filterStations":"",
          "osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":"",
        }
        grid=post("/stationsGrid",grid_form)
        for st in list_data(grid):
            if not isinstance(st,dict): continue
            try: d=hav(lat,lon,float(st.get("latitude")),float(st.get("longitude")))
            except Exception: d=None
            grid_candidates.append((d if d is not None else 1e18,st))
        grid_candidates.sort(key=lambda x:x[0])
        # Keep a bounded candidate set; exact uid/ref equality below is mandatory.
        candidates=grid_candidates[:50]
    target_by_num={numeric_suffix(e["evseId"]):e for e in evses if numeric_suffix(e["evseId"]) is not None}
    target_refs={norm_ref(e["evseId"]):e for e in evses}
    matches={}
    station_calls=[]
    for d,st in candidates:
        nsid=st.get("idStation") or st.get("stationId") or st.get("id")
        if nsid is None: continue
        cf={"idStation":str(nsid),"limit":"100","offset":"0","osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":""}
        cresp=post("/stationConnectors",cf)
        conns=list_data(cresp)
        station_calls.append({"idStation":nsid,"distanceM":round(d,2),"provider":st.get("provider"),"connectorCount":len(conns),"status":(cresp.get("json") or {}).get("status") if isinstance(cresp,dict) and isinstance(cresp.get("json"),dict) else None})
        for c in conns:
            if not isinstance(c,dict): continue
            uid=c.get("uidConnector")
            ev=None; method=None
            try:
                n=int(uid)
                if n in target_by_num:
                    ev=target_by_num[n]; method="exact_numeric_suffix_uidConnector"
            except Exception: pass
            if ev is None:
                pr=norm_ref(c.get("physicalReference"))
                # only exact normalized EVSE ID/ref; no fuzzy matching
                if pr in target_refs:
                    ev=target_refs[pr]; method="exact_normalized_physicalReference"
            if ev is not None:
                eid=str(ev["evseId"])
                row={"evseId":eid,"punStationId":sid,"coordinates":[lat,lon],"nextchargeStationId":nsid,"distanceM":round(d,2),"provider":st.get("provider"),"uidConnector":uid,"physicalReference":c.get("physicalReference"),"powerMax":c.get("powerMax"),"current":c.get("current"),"standard":c.get("standard"),"status":c.get("status"),"tariff":tariff_row(c),"matchMethod":method}
                # If duplicated, keep closest deterministic candidate.
                if eid not in matches or row["distanceM"]<matches[eid]["distanceM"]:
                    matches[eid]=row
    return {"punStationId":sid,"punEvseCount":len(evses),"nearStatus":(near.get("json") or {}).get("status") if isinstance(near,dict) and isinstance(near.get("json"),dict) else None,"gridStatus":((grid or {}).get("json") or {}).get("status") if isinstance(grid,dict) and isinstance(grid.get("json"),dict) else None,"gridCandidateCount":len(grid_candidates),"candidateStationCount":len(candidates),"stationCalls":station_calls,"matches":list(matches.values())}

results=[]
with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    futs={pool.submit(process,x):x[0] for x in stations}
    for i,f in enumerate(as_completed(futs),1):
        try: results.append(f.result())
        except Exception as e: results.append({"punStationId":futs[f],"error":f"{type(e).__name__}: {e}","matches":[]})
        if i%50==0 or i==len(futs): print(f"GES national progress {i}/{len(futs)}",flush=True)

matches=[]
for r in results: matches.extend(r.get("matches") or [])
matched_ids={m["evseId"] for m in matches}
rankable=[]
matched_no_rank=[]
for m in matches:
    t=m["tariff"]
    cur=t.get("currency")
    energy=t.get("energy")
    payment=t.get("paymentRequired")
    # paymentRequired false + empty prices is deterministically free on current NextCharge surface.
    if cur=="EUR" and isinstance(energy,(int,float)):
        rankable.append(m)
    elif cur=="EUR" and payment is False and all(t.get(k) in (None,0) for k in ("energy","parking","time","session")):
        x=dict(m); x["interpretedEnergyEurPerKwh"]=0.0; x["rankableReason"]="paymentRequired_false_empty_prices"
        rankable.append(x)
    else:
        matched_no_rank.append(m)

rank_ids={m["evseId"] for m in rankable}
tariff_counts=Counter()
for m in rankable:
    t=m["tariff"]
    key=(t.get("currency"), t.get("energy",m.get("interpretedEnergyEurPerKwh")), t.get("parking"), t.get("time"), t.get("session"), t.get("paymentRequired"))
    tariff_counts[str(key)]+=1
provider_counts=Counter(str(m.get("provider")) for m in matches)
method_counts=Counter(str(m.get("matchMethod")) for m in matches)

payload={"schemaVersion":1,"source":"NextCharge 6.2.02 public stationsNear/stationConnectors","partyId":"GES","punEvseCount":len(ges),"punStationCount":len(stations),"matchedEvseCount":len(matched_ids),"rankableEvseCount":len(rank_ids),"failClosedEvseCount":len(ges)-len(rank_ids),"matches":sorted(rankable,key=lambda x:x["evseId"])}
report={"scope":"GES national deterministic NextCharge reconciliation","punEvseCount":len(ges),"punStationCount":len(stations),"matchedEvseCount":len(matched_ids),"rankableEvseCount":len(rank_ids),"coveragePct":round(100*len(rank_ids)/len(ges),2) if ges else 0,"failClosedEvseCount":len(ges)-len(rank_ids),"matchedButNotRankableCount":len(matched_no_rank),"matchMethodCounts":dict(method_counts),"providerCounts":dict(provider_counts),"tariffTupleCounts":dict(tariff_counts),"stationOutcomeCounts":dict(Counter("error" if r.get("error") else ("matched" if r.get("matches") else "no_match") for r in results)),"maxDistanceM":MAX_DISTANCE_M,"gridHalfspanDeg":GRID_HALFSPAN_DEG,"gridStatusCounts":dict(Counter(str(r.get("gridStatus")) for r in results if r.get("gridStatus") is not None)),"gridCandidateStationTotal":sum(int(r.get("gridCandidateCount") or 0) for r in results),"security":{"credentialsUsed":False,"paymentAttempted":False,"chargingStarted":False},"stationDiagnostics":results}

OUT.parent.mkdir(parents=True,exist_ok=True); DATA.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
DATA.write_bytes(gzip.compress((json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n").encode(),compresslevel=9,mtime=0))
print(json.dumps({k:v for k,v in report.items() if k!="stationDiagnostics"},ensure_ascii=False,indent=2))
