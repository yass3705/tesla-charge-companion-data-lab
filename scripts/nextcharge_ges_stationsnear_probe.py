#!/usr/bin/env python3
import gzip, json, math, requests
from pathlib import Path

BASE="https://nextcharge.app.apis.goelectricstations.com/apis"
OUT=Path("data/reports/nextcharge_ges_stationsnear_probe.json")
PUN=Path("data/national/pun_italy_national.json.gz")

def post(path,data):
    try:
        r=requests.post(BASE+path,data=data,headers={"User-Agent":"NextCharge/6.2.02 Android","Content-Type":"application/x-www-form-urlencoded"},timeout=(8,20))
        row={"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
        try: row["json"]=r.json()
        except Exception: row["textPrefix"]=r.text[:1000]
        return row
    except Exception as e:
        return {"error":f"{type(e).__name__}: {e}"}

def load_pun():
    return json.loads(gzip.decompress(PUN.read_bytes()))

def dist_m(a,b,c,d):
    # local-enough haversine for deterministic candidate ranking
    R=6371000.0
    p1,p2=math.radians(a),math.radians(c)
    dp=math.radians(c-a); dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(min(1,math.sqrt(x)))

pun=load_pun()
ges=[e for e in pun.get("evses",[]) if isinstance(e,dict) and e.get("partyId")=="GES" and e.get("evseId") and isinstance(e.get("coordinates"),list) and len(e["coordinates"])>=2]
samples=[]
seen_station=set()
for e in ges:
    sid=e.get("stationId")
    if sid in seen_station: continue
    seen_station.add(sid)
    samples.append(e)
    if len(samples)>=6: break

rows=[]
for target in samples:
    evse=str(target["evseId"]); lat=float(target["coordinates"][0]); lon=float(target["coordinates"][1])
    base={"latitude":str(lat),"longitude":str(lon),"limit":"30","includeHighway":"1","includeNextcharge":"1","favorites":"0","osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":""}
    near=post("/stationsNear",base)
    row={"targetEvseId":evse,"targetPunStationId":target.get("stationId"),"targetCoordinates":[lat,lon],"response":near}
    obj=near.get("json") if isinstance(near,dict) else None
    data=obj.get("data") if isinstance(obj,dict) and obj.get("status")=="OK" else None
    stations=[]
    if isinstance(data,dict):
        for k in ("results","stations","data"):
            if isinstance(data.get(k),list):
                stations=data[k]; break
    elif isinstance(data,list):
        stations=data
    ranked=[]
    for st in stations:
        if not isinstance(st,dict): continue
        slat=st.get("latitude"); slon=st.get("longitude")
        try: distance=dist_m(lat,lon,float(slat),float(slon))
        except Exception: distance=None
        ranked.append((distance if distance is not None else 1e18,st))
    ranked.sort(key=lambda x:x[0])
    chains=[]
    for distance,st in ranked[:12]:
        sid=st.get("idStation") or st.get("stationId") or st.get("id")
        if sid is None: continue
        cf={"idStation":str(sid),"limit":"100","offset":"0","osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":""}
        cr=post("/stationConnectors",cf)
        chains.append({"distanceM":None if distance>=1e18 else round(distance,2),"idStation":sid,"stationSummary":st,"connectorsResponse":cr})
    row["connectorChains"]=chains
    rows.append(row)

report={"scope":"GES-targeted PUN coordinates -> NextCharge stationsNear -> stationConnectors","gesPunEvseCount":len(ges),"sampleTargetCount":len(samples),"results":rows}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2)[:180000])
