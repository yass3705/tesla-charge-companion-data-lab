#!/usr/bin/env python3
import gzip,json,math,time,urllib.request,urllib.parse
from pathlib import Path
NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
API="https://ecarup.com/api/stations"
UA={"User-Agent":"eCarUp/2.6.0 Android TCC-readonly","Accept":"application/json"}
req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))
records={}
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str): owner=x["OperatorID"]
        eid=x.get("EvseID")
        if owner=="CH*EPO" and isinstance(eid,str): records[eid]=x
        for v in x.values(): walk(v,owner)
    elif isinstance(x,list):
        for v in x: walk(v,owner)
walk(nat)
def xy(d):
    try:
        a,b=(d.get("GeoCoordinates") or {}).get("Google").replace(","," ").split()[:2]; return float(a),float(b)
    except:return None
def hav(a,b,c,d):
    R=6371000.;p1=math.radians(a);p2=math.radians(c);dp=math.radians(c-a);dl=math.radians(d-b)
    z=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(z))
cache={};rows=[];errors=[]
for n,(eid,d) in enumerate(sorted(records.items()),1):
    p=xy(d)
    if not p:
        rows.append({"evseId":eid,"error":"missing_geo","candidates":[]}); continue
    key=f"{p[0]:.6f},{p[1]:.6f}"
    if key not in cache:
        q=urllib.parse.urlencode({"location":key,"includePartners":"true","onlyAvailable":"false"})
        try:
            req=urllib.request.Request(API+"?"+q,headers=UA)
            with urllib.request.urlopen(req,timeout=35) as r: arr=json.loads(r.read().decode("utf-8"))
            cache[key]=arr if isinstance(arr,list) else []
        except Exception as e:
            cache[key]=[];errors.append({"location":key,"error":type(e).__name__+": "+str(e)})
        time.sleep(0.06)
    cands=[]
    for s in cache[key]:
        try:dist=hav(p[0],p[1],float(s["Latitude"]),float(s["Longitude"]))
        except:continue
        if dist<=100:
            pcs=[]
            for c in s.get("Connectors") or []:
                pr=c.get("Price") or {}
                pcs.append({"id":c.get("Id"),"accessType":c.get("AccessType"),"state":c.get("State"),"maxPowerW":c.get("MaxPower"),
                            "hubjectId":(c.get("Hubject") or {}).get("ID"),"energyPrice":pr.get("EnergyPrice"),
                            "parkingPrice":pr.get("ParkingPrice"),"currency":pr.get("Currency"),
                            "penaltyGracePeriodMinutes":pr.get("PenaltyGracePeriodMinutes"),
                            "penaltyPricePerMinute":pr.get("PenaltyPricePerMinute"),"penaltyMaxFee":pr.get("PenaltyMaxFee")})
            cands.append({"distanceMeters":round(dist,1),"stationId":s.get("ID"),"name":s.get("Name"),"address":s.get("Address"),
                          "operatorName":((s.get("ContactDetails") or {}).get("OperatorName") or "").strip(),"connectors":pcs})
    cands.sort(key=lambda z:z["distanceMeters"])
    rows.append({"evseId":eid,"chargingStationId":d.get("ChargingStationId"),"nationalAddress":d.get("Address"),
                 "geo":d.get("GeoCoordinates"),"facilities":d.get("ChargingFacilities"),"plugs":d.get("Plugs"),"candidates":cands})
out={"schemaVersion":1,"country":"CH","operatorId":"CH*EPO","nationalEvseCount":len(records),"uniqueQueryCount":len(cache),
     "errorCount":len(errors),"errors":errors,"rows":rows}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-epo-ecarup-targeted-audit-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"nationalEvseCount":len(records),"uniqueQueryCount":len(cache),"errorCount":len(errors),
 "withCandidateWithin100m":sum(1 for r in rows if r["candidates"]),
 "withPricedPublicCandidate":sum(1 for r in rows if any(c.get("accessType")==0 and c.get("energyPrice") is not None for s in r["candidates"] for c in s["connectors"]))},indent=2))
