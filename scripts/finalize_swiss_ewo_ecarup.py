#!/usr/bin/env python3
import gzip,json,math,urllib.request
from pathlib import Path
from datetime import datetime,timezone
NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
ECAR=Path("data/switzerland/ecarup-public-stations.json")
OUT=Path("data/switzerland/ewo-ecarup-direct-tariffs.json")
FINAL=Path("docs/switzerland-ewo-finalization-2026-09-28.json")
OWNER="CH*EWO"; OPNAME="Elektrizitätswerk Obwalden"
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
nat=json.loads(raw.decode())
ec=json.loads(ECAR.read_text(encoding="utf-8"))
records={}
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str): owner=x["OperatorID"]
        eid=x.get("EvseID")
        if owner==OWNER and isinstance(eid,str):records[eid]=x
        for v in x.values():walk(v,owner)
    elif isinstance(x,list):
        for v in x:walk(v,owner)
walk(nat)
def xy(d):
    try:
        a,b=(d.get("GeoCoordinates") or {}).get("Google").replace(","," ").split()[:2];return float(a),float(b)
    except:return None
def hav(a,b,c,d):
    R=6371000;p1=math.radians(a);p2=math.radians(c);dp=math.radians(c-a);dl=math.radians(d-b)
    z=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(z))
stations=[s for s in ec.get("stations",[]) if ((s.get("ContactDetails") or {}).get("OperatorName") or "").strip()==OPNAME]
rows=[];unresolved=[]
for eid,d in sorted(records.items()):
    p=xy(d)
    cands=[]
    if p:
      for s in stations:
        try:dist=hav(p[0],p[1],float(s["Latitude"]),float(s["Longitude"]))
        except:continue
        if dist<=50:cands.append((dist,s))
    cands.sort(key=lambda x:x[0])
    if not cands:
        unresolved.append({"evseId":eid,"reason":"no_same_operator_station_within_50m","geo":d.get("GeoCoordinates"),"address":d.get("Address")});continue
    # One physical public eCarUp station is expected near the national record.
    bestd,best=cands[0]
    if len(cands)>1 and cands[1][0]-bestd<5 and bestd>5:
        unresolved.append({"evseId":eid,"reason":"ambiguous_same_operator_station","candidates":[{"id":s.get("ID"),"name":s.get("Name"),"distanceMeters":round(dd,1)} for dd,s in cands[:5]]});continue
    conns=[]
    for c in best.get("Connectors") or []:
        price=c.get("Price") or {}
        conns.append({"connectorId":c.get("Id"),"name":c.get("Name"),"accessType":c.get("AccessType"),"state":c.get("State"),
                      "maxPowerKw":(float(c["MaxPower"])/1000.0 if isinstance(c.get("MaxPower"),(int,float)) else None),
                      "hubjectId":(c.get("Hubject") or {}).get("ID"),
                      "energyPrice":price.get("EnergyPrice"),"parkingPrice":price.get("ParkingPrice"),
                      "penaltyGracePeriodMinutes":price.get("PenaltyGracePeriodMinutes"),"penaltyPricePerMinute":price.get("PenaltyPricePerMinute"),
                      "penaltyMaxFee":price.get("PenaltyMaxFee"),"currency":price.get("Currency")})
    public=[c for c in conns if c.get("accessType")==0]
    if not public or any(c.get("energyPrice") is None for c in public):
        unresolved.append({"evseId":eid,"reason":"public_connector_price_missing","station":best.get("Name"),"connectors":conns});continue
    rows.append({"evseId":eid,"chargingStationId":d.get("ChargingStationId"),"nationalAddress":d.get("Address"),"nationalFacilities":d.get("ChargingFacilities"),
                 "ecarupStationId":best.get("ID"),"ecarupStationName":best.get("Name"),"distanceMeters":round(bestd,1),
                 "publicConnectors":public,"restrictedConnectors":[c for c in conns if c.get("accessType")!=0]})
now=datetime.now(timezone.utc).isoformat()
status="complete" if records and len(rows)==len(records) and not unresolved else "partial"
policy="Exact same-operator eCarUp station within 50 m of each current CH*EWO national record. Public connectors are accessType=0; restricted/reserved connectors are retained separately and never treated as public. Explicit connector prices only, no extrapolation."
payload={"schemaVersion":1,"country":"CH","cpo":"Elektrizitätswerk Obwalden","operatorId":OWNER,"generatedAt":now,
         "sources":{"national":NATIONAL,"ecarup":"data/switzerland/ecarup-public-stations.json"},"counts":{"nationalEvseCount":len(records),"resolvedEvseCount":len(rows),"unresolvedEvseCount":len(unresolved)},
         "policy":policy,"evses":rows,"unresolved":unresolved}
final={"schemaVersion":1,"country":"CH","cpo":"Elektrizitätswerk Obwalden","operatorId":OWNER,"status":status,"updatedAt":now,
       "nationalEvseCount":len(records),"pricedEvseCount":len(rows),"unresolvedEvseCount":len(unresolved),
       "method":"Current Swiss national CH*EWO scope + eCarUp public same-operator station/connector pricing by exact geographic reconciliation",
       "policy":policy,"productionSource":str(OUT)}
OUT.parent.mkdir(parents=True,exist_ok=True);FINAL.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n");FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(final,ensure_ascii=False,indent=2));print(json.dumps(unresolved,ensure_ascii=False,indent=2))
