#!/usr/bin/env python3
import json, urllib.parse, urllib.request, gzip, math
from pathlib import Path
from datetime import datetime, timezone

BLOCK=Path("docs/switzerland-ecarup-exhaustive-residual-blockers-2026-09-30.json")
OUT=Path("docs/switzerland-ecarup-deep-audit-60-2026-09-30.json")
BASE="https://ecarup.com/api/stations"
HDR={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}

def norm(s): return "".join(c for c in str(s or "").upper() if c.isalnum())
def dist(a,b):
    x=math.radians(b[1]-a[1])*math.cos(math.radians((a[0]+b[0])/2))
    y=math.radians(b[0]-a[0]); return 6371000*(x*x+y*y)**.5
def scoord(s):
    for a,b in (("Latitude","Longitude"),("latitude","longitude")):
        if isinstance(s.get(a),(int,float)) and isinstance(s.get(b),(int,float)):
            return [float(s[a]),float(s[b])]
def conns(s): return s.get("Connectors") or s.get("connectors") or []
def fetch(term,co):
    q=urllib.parse.urlencode({"searchTerm":term,"location":f"{co[0]},{co[1]}","includePartners":"true","onlyAvailable":"false","onlyRecentlyUsed":"false"})
    req=urllib.request.Request(BASE+"?"+q,headers=HDR)
    with urllib.request.urlopen(req,timeout=30) as r: return json.loads(r.read().decode())

src=json.loads(BLOCK.read_text())
rows=[]
for r in src["residuals"]:
    eid=r["evseId"]; name=r.get("stationName"); co=r.get("coordinate")
    item={"evseId":eid,"stationName":name,"coordinate":co,"queries":[],"exactHubjectHits":[],"nearStations":[]}
    if not co or abs(co[0])>90 or abs(co[1])>180:
        item["classification"]="invalid_coordinate"; rows.append(item); continue
    terms=[""]
    if name: terms.append(name)
    seen=set()
    for term in terms:
        try: arr=fetch(term,co)
        except Exception as e:
            item["queries"].append({"term":term,"error":str(e)[:200]}); continue
        item["queries"].append({"term":term,"resultCount":len(arr) if isinstance(arr,list) else None})
        if not isinstance(arr,list): continue
        for st in arr:
            sc=scoord(st)
            d=dist(co,sc) if sc else None
            for c in conns(st):
                hub=(c.get("Hubject") or {}).get("ID") if isinstance(c.get("Hubject"),dict) else None
                if norm(hub)==norm(eid):
                    item["exactHubjectHits"].append({"stationId":st.get("ID") or st.get("id"),"stationName":st.get("Name") or st.get("name"),"distanceMeters":round(d,2) if d is not None else None,"connector":c})
            if d is not None and d<=250:
                item["nearStations"].append({
                    "stationId":st.get("ID") or st.get("id"),"stationName":st.get("Name") or st.get("name"),
                    "distanceMeters":round(d,2),"connectorCount":len(conns(st)),
                    "connectors":[{
                        "Id":c.get("Id") or c.get("ID") or c.get("id"),
                        "Name":c.get("Name") or c.get("name"),
                        "Hubject":c.get("Hubject"),
                        "PlugType":c.get("PlugType"),
                        "MaxPower":c.get("MaxPower"),
                        "AccessType":c.get("AccessType"),
                        "Price":c.get("Price")
                    } for c in conns(st)]
                })
    # dedupe station snapshots
    uniq={}
    for st in item["nearStations"]:
        uniq[(st["stationId"],st["distanceMeters"])]=st
    item["nearStations"]=sorted(uniq.values(),key=lambda x:x["distanceMeters"])
    if item["exactHubjectHits"]: item["classification"]="exact_hubject_now_available"
    elif not item["nearStations"]: item["classification"]="no_current_public_station_within_250m"
    else:
        prices=set(); hubs=0
        for st in item["nearStations"]:
            for c in st["connectors"]:
                if c.get("Hubject") and (c["Hubject"] or {}).get("ID"): hubs+=1
                if isinstance(c.get("Price"),dict): prices.add(json.dumps(c["Price"],sort_keys=True))
        item["classification"]="nearby_public_candidates"
        item["nearbyDistinctExplicitPrices"]=len(prices)
        item["nearbyHubjectIdCount"]=hubs
    rows.append(item)

out={"schemaVersion":1,"country":"CH","operatorId":"CH*ECU","generatedAt":datetime.now(timezone.utc).isoformat(),"residualCount":len(rows),"classCounts":{},"rows":rows,"policy":"Read-only public API audit. No tariff promotion performed."}
for r in rows: out["classCounts"][r["classification"]]=out["classCounts"].get(r["classification"],0)+1
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"residualCount":len(rows),"classCounts":out["classCounts"],"exactHubject":[r["evseId"] for r in rows if r["classification"]=="exact_hubject_now_available"]},indent=2))
