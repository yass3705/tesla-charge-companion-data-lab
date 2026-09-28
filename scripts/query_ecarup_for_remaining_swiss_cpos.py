#!/usr/bin/env python3
import gzip,json,math,time,urllib.request,urllib.parse
from pathlib import Path
from collections import defaultdict
NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
API="https://ecarup.com/api/stations"
TARGETS={"CH*SOC","CH*MMN","CH*SCH","CH*AVI"}
UA={"User-Agent":"eCarUp/2.6.0 Android TCC-readonly","Accept":"application/json"}
req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
nat=json.loads(raw.decode())
owned=defaultdict(dict)
def walk(x,owner=None):
 if isinstance(x,dict):
  if isinstance(x.get("OperatorID"),str):owner=x["OperatorID"]
  eid=x.get("EvseID")
  if owner in TARGETS and isinstance(eid,str):owned[owner][eid]=x
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
cache={};results={};errors=[]
for op,records in owned.items():
 rows=[]
 for eid,d in sorted(records.items()):
  p=xy(d)
  if not p:
   rows.append({"evseId":eid,"error":"missing_geo"});continue
  key=f"{p[0]:.6f},{p[1]:.6f}"
  if key not in cache:
   q=urllib.parse.urlencode({"location":key,"includePartners":"true","onlyAvailable":"false"})
   try:
    req=urllib.request.Request(API+"?"+q,headers=UA)
    with urllib.request.urlopen(req,timeout=35) as r: arr=json.loads(r.read().decode())
    cache[key]=arr if isinstance(arr,list) else []
   except Exception as e:
    cache[key]=[];errors.append({"location":key,"error":type(e).__name__+": "+str(e)})
   time.sleep(0.08)
  cands=[]
  for s in cache[key]:
   try:dist=hav(p[0],p[1],float(s["Latitude"]),float(s["Longitude"]))
   except:continue
   if dist<=1000:
    cands.append({"distanceMeters":round(dist,1),"stationId":s.get("ID"),"name":s.get("Name"),"address":s.get("Address"),
      "operatorName":((s.get("ContactDetails") or {}).get("OperatorName") or "").strip(),
      "lat":s.get("Latitude"),"lon":s.get("Longitude"),
      "connectors":[{"id":c.get("Id"),"name":c.get("Name"),"accessType":c.get("AccessType"),"state":c.get("State"),
        "maxPowerW":c.get("MaxPower"),"hubjectId":(c.get("Hubject") or {}).get("ID"),"price":c.get("Price")} for c in s.get("Connectors") or []]})
  cands.sort(key=lambda x:x["distanceMeters"])
  rows.append({"evseId":eid,"chargingStationId":d.get("ChargingStationId"),"address":d.get("Address"),"geo":d.get("GeoCoordinates"),
               "facilities":d.get("ChargingFacilities"),"plugs":d.get("Plugs"),"candidates":cands[:20]})
 results[op]=rows
out={"requestCount":len(cache),"errorCount":len(errors),"errors":errors,"operators":results}
Path("docs/switzerland-ecarup-remaining-targeted-queries-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{"count":len(rows),"noCandidates":sum(1 for r in rows if not r.get("candidates")),
 "samples":[{"evseId":r["evseId"],"candidates":[{"distance":c["distanceMeters"],"name":c["name"],"operator":c["operatorName"]} for c in r.get("candidates",[])[:5]]} for r in rows]} for op,rows in results.items()},ensure_ascii=False,indent=2)[:180000])
