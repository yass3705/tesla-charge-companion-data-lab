#!/usr/bin/env python3
import json, math, time, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime, timezone

OWNER = Path("data/switzerland/ecarup-owner-direct-tariffs.json")
COORD = Path("data/switzerland/ecarup-owner-coordinate-safe-overlay.json")
OVERLAY = Path("data/switzerland/ecarup-residual-name-search-overlay-2026-09-29.json")
REPORT = Path("docs/switzerland-ecarup-residual-name-search-batch-2026-09-29.json")
BASE = "https://ecarup.com/api/stations"
HEADERS = {"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
BATCH = 50

def norm(s):
    return "".join(c for c in str(s or "").upper() if c.isalnum())

def get_coord(rec):
    if not isinstance(rec, dict):
        return None
    g = (rec.get("GeoCoordinates") or {}).get("Google")
    if isinstance(g, str):
        try:
            a,b = g.replace(","," ").split()[:2]
            return float(a), float(b)
        except Exception:
            pass
    for a,b in (("Latitude","Longitude"),("latitude","longitude")):
        if isinstance(rec.get(a),(int,float)) and isinstance(rec.get(b),(int,float)):
            return float(rec[a]), float(rec[b])
    return None

def distance_m(a,b):
    lat1,lon1=a; lat2,lon2=b
    x=math.radians(lon2-lon1)*math.cos(math.radians((lat1+lat2)/2))
    y=math.radians(lat2-lat1)
    return 6371000*math.sqrt(x*x+y*y)

def candidate_names(rec):
    vals=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if isinstance(v,str) and ("name" in k.lower() or k.lower() in ("title","label")):
                    s=v.strip()
                    if 2 <= len(s) <= 140:
                        vals.append(s)
                walk(v)
        elif isinstance(x,list):
            for v in x:
                walk(v)
    walk(rec)
    out=[]; seen=set()
    for s in vals:
        n=norm(s)
        if n and n not in seen and not n.startswith("ECARUP"):
            seen.add(n); out.append(s)
    return out[:8]

def fetch_search(term, co):
    q = urllib.parse.urlencode({
        "searchTerm": term,
        "location": f"{co[0]},{co[1]}",
        "includePartners": "true",
        "onlyAvailable": "false",
        "onlyRecentlyUsed": "false"
    })
    req=urllib.request.Request(BASE+"?"+q, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def station_name(s):
    return s.get("Name") or s.get("name") or ""

def station_coord(s):
    for a,b in (("Latitude","Longitude"),("latitude","longitude")):
        if isinstance(s.get(a),(int,float)) and isinstance(s.get(b),(int,float)):
            return float(s[a]), float(s[b])
    return None

def connectors(s):
    return s.get("Connectors") or s.get("connectors") or []

def connector_price(c):
    return c.get("Price") or c.get("price")

def connector_access(c):
    return c.get("AccessType", c.get("accessType"))

owner=json.loads(OWNER.read_text(encoding="utf-8"))
coord=json.loads(COORD.read_text(encoding="utf-8")) if COORD.exists() else {}
overlay=json.loads(OVERLAY.read_text(encoding="utf-8")) if OVERLAY.exists() else {
    "schemaVersion":1,"country":"CH","operatorId":"CH*ECU","rows":[]
}

done={r.get("evseId") for r in owner.get("evses",[]) if r.get("evseId")}
done |= {r.get("evseId") for r in coord.get("evses",[]) if r.get("evseId")}
done |= {r.get("evseId") for r in overlay.get("rows",[]) if r.get("evseId")}

remaining=[r for r in owner.get("unresolved",[]) if r.get("evseId") and r.get("evseId") not in done]
promoted=[]; tested=[]; errors=[]

for row in remaining[:BATCH]:
    eid=row["evseId"]
    rec=row.get("nationalRecord") or {}
    co=get_coord(rec)
    names=candidate_names(rec)
    accepted=None
    if co and names:
        for term in names:
            try:
                arr=fetch_search(term, co)
            except Exception as e:
                errors.append({"evseId":eid,"term":term,"error":str(e)[:200]})
                continue
            if not isinstance(arr,list):
                continue
            matches=[]
            for st in arr:
                sc=station_coord(st)
                if not sc or distance_m(co,sc) > 3.0:
                    continue
                if norm(station_name(st)) != norm(term):
                    continue
                matches.append(st)
            if len(matches) != 1:
                continue
            st=matches[0]
            priced=[]
            for c in connectors(st):
                p=connector_price(c)
                if connector_access(c) in (0,None) and isinstance(p,dict):
                    priced.append(c)
            if len(priced) != 1:
                continue
            c=priced[0]
            accepted={
                "evseId":eid,
                "stationName":station_name(st),
                "stationId":st.get("ID") or st.get("id"),
                "match":"exact_name_and_coordinate_single_connector",
                "distanceMeters":round(distance_m(co,station_coord(st)),2),
                "price":connector_price(c),
                "connector":{
                    "Id":c.get("Id") or c.get("ID") or c.get("id"),
                    "Name":c.get("Name") or c.get("name"),
                    "MaxPower":c.get("MaxPower") or c.get("maxPower")
                }
            }
            break
    if accepted:
        promoted.append(accepted)
        overlay.setdefault("rows",[]).append(accepted)
        result="promoted"
    else:
        result="no_safe_exact_match"
    tested.append({"evseId":eid,"result":result,"namesTried":names})
    time.sleep(0.15)

now=datetime.now(timezone.utc).isoformat()
overlay["generatedAt"]=now
overlay["method"]="Exact eCarUp public API searchTerm + national coordinate; accept only unique exact-name/coordinate station and deterministic single public connector/price"
overlay["policy"]="No nearest-neighbour tariff inheritance; no cross-station extrapolation."
OVERLAY.write_text(json.dumps(overlay,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

report={
    "schemaVersion":1,
    "country":"CH",
    "operatorId":"CH*ECU",
    "generatedAt":now,
    "remainingBeforeBatch":len(remaining),
    "batchSize":BATCH,
    "testedCount":len(tested),
    "promotedCount":len(promoted),
    "remainingAfterBatch":len(remaining)-len(promoted),
    "promoted":promoted,
    "tested":tested,
    "errors":errors,
    "policy":"Fail closed: exact normalized name + <=3m coordinate + one explicit public connector price only."
}
REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k not in ("tested","errors")},ensure_ascii=False,indent=2))
