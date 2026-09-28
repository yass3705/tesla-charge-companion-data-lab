#!/usr/bin/env python3
import json,gzip,urllib.request,math,re
from pathlib import Path
from datetime import datetime,timezone

NAT="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
GO=Path("data/gofast/ev_charger_stations.json")
OUT=Path("data/switzerland/gofast-official-direct-tariffs.json")
DOC=Path("docs/switzerland-gofast-national-reconciliation-2026-09-28.json")

req=urllib.request.Request(NAT,headers={"User-Agent":"TCC-V9-Switzerland/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=120) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))
go=json.loads(GO.read_text(encoding="utf-8"))

def coord(rec):
 g=(rec.get("GeoCoordinates") or {}).get("Google")
 if isinstance(g,str):
  try:
   a,b=g.replace(","," ").split()[:2]; return float(a),float(b)
  except: return None
 return None
def dist(a,b):
 lat1,lon1=a;lat2,lon2=b
 x=math.radians(lon2-lon1)*math.cos(math.radians((lat1+lat2)/2));y=math.radians(lat2-lat1)
 return 6371000*math.sqrt(x*x+y*y)
def names(rec):
 n=rec.get("ChargingStationNames")
 if isinstance(n,list): return " ".join(str(x.get("value") or "") for x in n if isinstance(x,dict))
 if isinstance(n,dict): return str(n.get("value") or "")
 return str(n or "")
def parse_price(s):
 if not isinstance(s,str): return None
 m=re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*CHF\s*/\s*kWh",s,re.I)
 return float(m.group(1).replace(",",".")) if m else None
def parse_block(s):
 if not isinstance(s,str): return {}
 pm=re.search(r"CHF\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*Min",s,re.I)
 am=re.search(r"(?:ab|après|after)\s*(\d+)\.?(?:\s*Minute|\s*min)",s,re.I)
 out={}
 if pm: out["blockingFeeChfPerMinute"]=float(pm.group(1).replace(",","."))
 if am: out["blockingFeeAfterMinutes"]=int(am.group(1))
 return out

# Current national owner scope grouped by station id.
stations={}
def walk(x,owner=None):
 if isinstance(x,dict):
  if isinstance(x.get("OperatorID"),str): owner=x["OperatorID"]
  eid=x.get("EvseID")
  if owner=="CH*GFT" and isinstance(eid,str):
   sid=x.get("ChargingStationId") or eid
   st=stations.setdefault(sid,{"stationId":sid,"evses":[],"coord":coord(x),"name":names(x),"address":x.get("Address")})
   st["evses"].append(eid)
   if not st["coord"]: st["coord"]=coord(x)
  for v in x.values(): walk(v,owner)
 elif isinstance(x,list):
  for v in x: walk(v,owner)
walk(nat)

official=[]
for s in go:
 loc=s.get("location") or {}
 try: co=(float(loc.get("lat")),float(loc.get("lng")))
 except: continue
 price=parse_price(s.get("pricing_de") or s.get("pricing_fr") or s.get("pricing_it") or s.get("pricing_en"))
 if price is None: continue
 official.append({"id":s.get("id"),"title":s.get("title_de") or s.get("title_fr") or s.get("title_it") or s.get("title_en"),"coord":co,"pricePerKwh":price,"details":s.get("pricing_detail_de") or s.get("pricing_detail_fr") or s.get("pricing_detail_it") or s.get("pricing_detail_en")})

resolved=[];unresolved=[];used=set()
for sid,st in stations.items():
 if not st["coord"]:
  unresolved.append({"stationId":sid,"evseIds":st["evses"],"reason":"no_national_coordinate"});continue
 ranked=sorted((dist(st["coord"],o["coord"]),o) for o in official)
 if not ranked:
  unresolved.append({"stationId":sid,"evseIds":st["evses"],"reason":"no_official_station"});continue
 d,o=ranked[0]
 d2=ranked[1][0] if len(ranked)>1 else 999999
 # Fail closed: accept a unique physical match within 100 m only when the next official candidate is at least 100 m farther away.
 # This tolerates map/geocoder offsets without allowing ambiguous nearby GOFAST sites.
 if d<=100 and d2-d>=100:
  used.add(o["id"])
  extra=parse_block(o["details"])
  for eid in st["evses"]:
   resolved.append({"evseId":eid,"chargingStationId":sid,"officialStationId":o["id"],"officialStationName":o["title"],"distanceMeters":round(d,2),"currency":"CHF","pricePerKwh":o["pricePerKwh"],**extra,"source":"GOFAST official public web-app station feed"})
 else:
  unresolved.append({"stationId":sid,"evseIds":st["evses"],"nearestDistanceMeters":round(d,2),"secondDistanceMeters":round(d2,2),"nationalName":st.get("name"),"nationalAddress":st.get("address"),"nearestOfficial":o["title"],"reason":"no_unique_safe_official_match"})

out={"schemaVersion":1,"country":"CH","cpo":"GOFAST","operatorId":"CH*GFT","generatedAt":datetime.now(timezone.utc).isoformat(),"nationalStationCount":len(stations),"nationalEvseCount":sum(len(s["evses"]) for s in stations.values()),"pricedEvseCount":len(resolved),"unresolvedEvseCount":sum(len(x["evseIds"]) for x in unresolved),"matchedOfficialStationCount":len(used),"policy":"Exact current CH*GFT owner scope. Match to official GOFAST station feed only when nearest official station is <=100m and at least 100m better than next candidate. Station-specific official price only; no cross-station extrapolation.","evses":resolved,"unresolved":unresolved}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
DOC.write_text(json.dumps({k:v for k,v in out.items() if k not in ("evses","unresolved")}|{"unresolvedStations":unresolved},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k not in ("evses","unresolved")},indent=2))

# trigger
