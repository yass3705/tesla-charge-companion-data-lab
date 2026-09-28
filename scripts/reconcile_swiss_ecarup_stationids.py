#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from collections import defaultdict
NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
ECAR=Path("data/switzerland/ecarup-public-stations.json")
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
nat=json.loads(raw.decode())
ec=json.loads(ECAR.read_text(encoding="utf-8"))
records={}
def walk(x,owner=None):
 if isinstance(x,dict):
  if isinstance(x.get("OperatorID"),str):owner=x["OperatorID"]
  eid=x.get("EvseID")
  if owner=="CH*ECU" and isinstance(eid,str): records[eid]=x
  for v in x.values():walk(v,owner)
 elif isinstance(x,list):
  for v in x:walk(v,owner)
walk(nat)
by_station={str(s.get("ID")):s for s in ec.get("stations",[]) if s.get("ID")}
direct=[];missing=[]
for eid,d in records.items():
 sid=str(d.get("ChargingStationId") or "")
 if sid in by_station:
  s=by_station[sid]
  direct.append({"evseId":eid,"chargingStationId":sid,"stationId":s.get("ID"),"stationName":s.get("Name"),"address":s.get("Address"),"connectors":s.get("Connectors")})
 else: missing.append({"evseId":eid,"chargingStationId":sid,"address":d.get("Address"),"geo":d.get("GeoCoordinates")})
out={"nationalEvseCount":len(records),"ecarupCollectedStationCount":len(by_station),"chargingStationIdExactMatchCount":len(direct),
     "missingExactStationIdCount":len(missing),"coveragePct":round(100*len(direct)/len(records),3) if records else 0,
     "matches":direct,"missingSample":missing[:100]}
Path("docs/switzerland-ecarup-national-stationid-reconciliation-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k not in ("matches","missingSample")},indent=2))
