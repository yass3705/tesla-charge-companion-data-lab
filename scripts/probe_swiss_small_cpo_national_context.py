#!/usr/bin/env python3
import gzip,json,math,urllib.request
from pathlib import Path
from collections import defaultdict
NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
TARGETS={"CH*EWO","CH*EBS","CH*AIL","CH*HER","CH*DIE","CH*MMN","CH*EVT"}
req=urllib.request.Request(NATIONAL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
nat=json.loads(raw.decode("utf-8"))
def walk(o,path=(),anc=()):
    if isinstance(o,dict):
        yield path,o,anc
        for k,v in o.items(): yield from walk(v,path+(str(k),),anc+(o,))
    elif isinstance(o,list):
        for i,v in enumerate(o): yield from walk(v,path+(str(i),),anc)
rows=[]
for path,d,anc in walk(nat):
    eid=d.get("EvseID") if isinstance(d,dict) else None
    if not isinstance(eid,str) or "*E" not in eid: continue
    op=eid.split("*E",1)[0]
    if op not in TARGETS: continue
    station=d.get("ChargingStationId")
    ctx=[]
    for x in anc[-5:]+(d,):
        if isinstance(x,dict):
            slim={}
            for k,v in x.items():
                lk=k.lower()
                if isinstance(v,(str,int,float,bool)) and any(t in lk for t in ("station","address","city","postal","street","latitude","longitude","geo","name","operator","evseid")):
                    slim[k]=v
            if slim: ctx.append(slim)
    rows.append({"operatorId":op,"evseId":eid,"chargingStationId":station,"evse":d,"context":ctx})
out={"operators":{}}
for op in sorted(TARGETS):
    out["operators"][op]=[r for r in rows if r["operatorId"]==op]
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-small-cpo-national-context-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{"evses":len(v),"stationIds":len(set(r.get("chargingStationId") for r in v)),"sample":v[:2]} for op,v in out["operators"].items()},ensure_ascii=False,indent=2)[:150000])
