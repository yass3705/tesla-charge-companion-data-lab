#!/usr/bin/env python3
import json,gzip,urllib.request,math,re
from pathlib import Path
from datetime import datetime,timezone
NAT="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
EC=Path("data/switzerland/ecarup-public-stations.json")
EXACT=Path("data/switzerland/ecarup-owner-direct-tariffs.json")
OUT=Path("data/switzerland/ecarup-owner-coordinate-safe-overlay.json")
DOC=Path("docs/switzerland-ecarup-owner-coordinate-safe-overlay-2026-09-28.json")
req=urllib.request.Request(NAT,headers={"User-Agent":"TCC-V9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if len(raw)>=2 and raw[0]==31 and raw[1]==139: raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8")); ec=json.loads(EC.read_text(encoding="utf-8"))
already=set()
if EXACT.exists():
 try:
  x=json.loads(EXACT.read_text(encoding="utf-8"))
  already={r.get("evseId") for r in x.get("evses",[]) if r.get("evseId")}
 except: pass
records={}
def walk(x,owner=None):
 if isinstance(x,dict):
  if isinstance(x.get("OperatorID"),str): owner=x["OperatorID"]
  eid=x.get("EvseID")
  if owner=="CH*ECU" and isinstance(eid,str): records[eid]=x
  for v in x.values(): walk(v,owner)
 elif isinstance(x,list):
  for v in x: walk(v,owner)
walk(nat)
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
stations=[]
for s in ec.get("stations",[]):
 lat=s.get("Latitude");lon=s.get("Longitude")
 if isinstance(lat,(int,float)) and isinstance(lon,(int,float)): stations.append((lat,lon,s))
# coarse bins
bins={}
for lat,lon,s in stations:
 bins.setdefault((round(lat,3),round(lon,3)),[]).append((lat,lon,s))
def price_tuple(c):
 p=c.get("Price") or {}
 if not p: return None
 return (p.get("EnergyPrice"),p.get("ParkingPrice"),p.get("PenaltyGracePeriodMinutes"),p.get("PenaltyPricePerMinute"),p.get("PenaltyMaxFee"),str(p.get("Currency") or "").upper())
resolved=[]; ambiguous=[]; no_candidate=[]
for eid,rec in records.items():
 if eid in already: continue
 co=coord(rec)
 if not co: no_candidate.append({"evseId":eid,"reason":"no_coordinate"}); continue
 lat,lon=co;cand=[]
 for di in (-1,0,1):
  for dj in (-1,0,1):
   key=(round(lat,3)+di*.001,round(lon,3)+dj*.001)
   for slat,slon,s in bins.get(key,[]):
    d=dist(co,(slat,slon))
    if d<=3.0:cand.append((d,s))
 if not cand: no_candidate.append({"evseId":eid,"reason":"no_station_within_3m"});continue
 exactish=[x for x in cand if x[0]<=0.75]
 eval_cand=exactish if exactish else cand
 tuples=set(); pub_connectors=[]
 for d,s in eval_cand:
  for c in s.get("Connectors") or []:
   if c.get("AccessType")==0:
    pt=price_tuple(c)
    if pt is not None: tuples.add(pt);pub_connectors.append({"distanceMeters":round(d,2),"stationId":s.get("ID"),"stationName":s.get("Name"),"connectorId":c.get("ID"),"hubjectId":c.get("HubjectID"),"price":c.get("Price")})
 if len(tuples)==1 and pub_connectors:
  resolved.append({"evseId":eid,"nationalCoordinate":{"lat":lat,"lon":lon},"evidence":"all priced public eCarUp connectors in the accepted coordinate candidate set share one identical price tuple (prefer <=0.75m exact-coordinate tolerance; otherwise full <=3m set)","connectors":pub_connectors,"priceTuple":list(next(iter(tuples)))})
 else: ambiguous.append({"evseId":eid,"candidateStationCount":len(cand),"distinctPublicPriceTupleCount":len(tuples),"reason":"multiple_or_missing_public_price_tuples"})
now=datetime.now(timezone.utc).isoformat()
out={"schemaVersion":1,"country":"CH","operatorId":"CH*ECU","generatedAt":now,"nationalEvseCount":len(records),"alreadyExactPricedCount":len(already),"safeCoordinateOverlayCount":len(resolved),"ambiguousCount":len(ambiguous),"noCandidateCount":len(no_candidate),"policy":"Only unresolved current CH*ECU EVSEs. Prefer exact-coordinate tolerance <=0.75m when present; otherwise use the full <=3m candidate set. Accept only when every priced public connector in the accepted set has one identical complete price tuple. No nearest-neighbour selection and no cross-location extrapolation.","evses":resolved,"ambiguous":ambiguous,"noCandidate":no_candidate}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
DOC.write_text(json.dumps({k:v for k,v in out.items() if k not in ("evses","ambiguous","noCandidate")},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k not in ("evses","ambiguous","noCandidate")},indent=2))
