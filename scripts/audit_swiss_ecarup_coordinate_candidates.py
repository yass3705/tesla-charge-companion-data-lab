#!/usr/bin/env python3
import gzip,json,math,urllib.request
from pathlib import Path
from collections import defaultdict,Counter
NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
TARGETS={"CH*EWO","CH*EBS","CH*AIL","CH*HER","CH*DIE","CH*EPO","CH*EVT"}
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
req=urllib.request.Request(NATIONAL,headers=UA)
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))
ec=json.loads(Path("data/switzerland/ecarup-public-stations.json").read_text(encoding="utf-8"))
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
    g=(d.get("GeoCoordinates") or {}).get("Google")
    try:
        a,b=str(g).replace(","," ").split()[:2];return float(a),float(b)
    except:return None
def hav(a,b,c,d):
    R=6371000;p1=math.radians(a);p2=math.radians(c);dp=math.radians(c-a);dl=math.radians(d-b)
    z=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(z))
stations=ec.get("stations",[])
res={}
for op,records in owned.items():
    rows=[];opnames=Counter()
    for eid,d in records.items():
        p=xy(d); candidates=[]
        if p:
            for s in stations:
                try:dist=hav(p[0],p[1],float(s["Latitude"]),float(s["Longitude"]))
                except:continue
                if dist<=300:
                    on=((s.get("ContactDetails") or {}).get("OperatorName") or "").strip()
                    candidates.append({"distanceMeters":round(dist,1),"stationId":s.get("ID"),"name":s.get("Name"),"address":s.get("Address"),
                                       "operatorName":on,"connectorCount":len(s.get("Connectors") or []),
                                       "connectors":[{"id":c.get("Id"),"maxPowerW":c.get("MaxPower"),"price":c.get("Price"),"hubjectId":(c.get("Hubject") or {}).get("ID")} for c in s.get("Connectors") or []]})
                    opnames[on]+=1
        candidates.sort(key=lambda x:x["distanceMeters"])
        rows.append({"evseId":eid,"nationalAddress":d.get("Address"),"geo":d.get("GeoCoordinates"),"facilities":d.get("ChargingFacilities"),"candidates":candidates[:12]})
    res[op]={"nationalEvseCount":len(records),"candidateOperatorNames":opnames.most_common(30),"rows":rows}
out={"operators":res}
Path("docs/switzerland-ecarup-coordinate-candidate-audit-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{"nationalEvseCount":d["nationalEvseCount"],"candidateOperatorNames":d["candidateOperatorNames"],
                            "noCandidateCount":sum(1 for r in d["rows"] if not r["candidates"]),
                            "nearestSamples":[{"evseId":r["evseId"],"nearest":r["candidates"][:3]} for r in d["rows"][:8]]} for op,d in res.items()},ensure_ascii=False,indent=2)[:180000])
