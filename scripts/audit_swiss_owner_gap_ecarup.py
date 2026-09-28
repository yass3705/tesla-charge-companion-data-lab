#!/usr/bin/env python3
import gzip,json,math,time,urllib.request,urllib.parse
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
API="https://ecarup.com/api/stations"
TARGETS={"CH*PAR","CHEVP","CH*TAE","CH*ENMOBILECHARGE","CH*MOBIMOEMOBILITY","CH*BCK","CH*EVAEMOBILITAET","CH*PACEMOBILITY"}
UA={"User-Agent":"eCarUp/2.6.0 Android TCC-readonly","Accept":"application/json"}

req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode())

owned=defaultdict(dict)
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str): owner=x["OperatorID"]
        eid=x.get("EvseID")
        if owner in TARGETS and isinstance(eid,str): owned[owner][eid]=x
        for v in x.values(): walk(v,owner)
    elif isinstance(x,list):
        for v in x: walk(v,owner)
walk(nat)

def xy(d):
    try:
        s=(d.get("GeoCoordinates") or {}).get("Google") or ""
        a,b=s.replace(","," ").split()[:2]
        return float(a),float(b)
    except:return None

def hav(a,b,c,d):
    R=6371000;p1=math.radians(a);p2=math.radians(c);dp=math.radians(c-a);dl=math.radians(d-b)
    z=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(z))

def norm(s): return "".join(ch for ch in (s or "").upper() if ch.isalnum())

cache={}; out={"generatedAt":datetime.now(timezone.utc).isoformat(),"operators":{},"requestErrors":[]}
for op,records in owned.items():
    exact=[]; near=[]; no_candidates=0
    for eid,d in sorted(records.items()):
        p=xy(d)
        if not p: continue
        key=f"{p[0]:.6f},{p[1]:.6f}"
        if key not in cache:
            q=urllib.parse.urlencode({"location":key,"includePartners":"true","onlyAvailable":"false"})
            try:
                req=urllib.request.Request(API+"?"+q,headers=UA)
                with urllib.request.urlopen(req,timeout=35) as r: arr=json.loads(r.read().decode())
                cache[key]=arr if isinstance(arr,list) else []
            except Exception as e:
                cache[key]=[];out["requestErrors"].append({"location":key,"error":type(e).__name__+": "+str(e)})
            time.sleep(0.06)
        local=[]
        for s in cache[key]:
            try: dist=hav(p[0],p[1],float(s["Latitude"]),float(s["Longitude"]))
            except: continue
            if dist>50: continue
            conns=[]
            for c in s.get("Connectors") or []:
                rec={"id":c.get("Id"),"accessType":c.get("AccessType"),"state":c.get("State"),
                     "maxPowerW":c.get("MaxPower"),"hubjectId":(c.get("Hubject") or {}).get("ID"),"price":c.get("Price")}
                conns.append(rec)
                if norm(rec["hubjectId"])==norm(eid):
                    exact.append({"evseId":eid,"distanceMeters":round(dist,1),"stationId":s.get("ID"),"name":s.get("Name"),
                                  "operatorName":((s.get("ContactDetails") or {}).get("OperatorName") or "").strip(),"connector":rec})
            if dist<=15 and any(c.get("accessType")==0 and isinstance(c.get("price"),dict) for c in conns):
                local.append({"distanceMeters":round(dist,1),"stationId":s.get("ID"),"name":s.get("Name"),
                              "operatorName":((s.get("ContactDetails") or {}).get("OperatorName") or "").strip(),"connectors":conns})
        if len(local)==1: near.append({"evseId":eid,"candidate":local[0]})
        if not cache[key]: no_candidates+=1
    out["operators"][op]={"nationalEvseCount":len(records),"exactHubjectMatchCount":len(exact),
                          "uniquePricedCandidateWithin15mCount":len(near),"noCandidateLocationCount":no_candidates,
                          "exactHubjectMatches":exact,"nearCandidates":near[:100]}

Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-owner-gap-ecarup-audit-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{k:v for k,v in d.items() if k not in ("exactHubjectMatches","nearCandidates")} for op,d in out["operators"].items()},ensure_ascii=False,indent=2))
