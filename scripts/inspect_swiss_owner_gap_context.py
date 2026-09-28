#!/usr/bin/env python3
import gzip,json,urllib.request
from collections import defaultdict,Counter
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
TARGETS={"CH*PAR","CH*REP","CH*911","CH*505","CHEVP","CH*TAE","CH*ENMOBILECHARGE","CH*MOBIMOEMOBILITY","CH*BCK","CH*EVAEMOBILITAET","CH*PACEMOBILITY"}
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
by=defaultdict(list)
def compact(d):
    keep={}
    for k,v in d.items():
        lk=k.lower()
        if k in {"EvseID","ChargingStationId","OperatorID","Accessibility","HotlinePhoneNumber","IsOpen24Hours","MaxCapacity"} or any(t in lk for t in ("name","address","geo","authentication","payment","power","facility","plug","charging")):
            if isinstance(v,(str,int,float,bool,type(None))):keep[k]=v
            elif isinstance(v,list) and len(v)<=20:keep[k]=v
            elif isinstance(v,dict) and len(v)<=30:keep[k]=v
    return keep
def walk(x,owner=None,anc=()):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip():owner=x["OperatorID"].strip()
        eid=x.get("EvseID")
        if owner in TARGETS and isinstance(eid,str):
            ctx={"evse":compact(x)}
            for a in reversed(anc[-4:]):
                c=compact(a)
                if c:
                    ctx.setdefault("ancestors",[]).append(c)
            by[owner].append(ctx)
        for v in x.values():walk(v,owner,anc+(x,))
    elif isinstance(x,list):
        for v in x:walk(v,owner,anc)
walk(j)
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"source":URL,"operators":{}}
for op in sorted(TARGETS):
    rows=by.get(op,[])
    names=[];auth=[];samples=[]
    for r in rows:
        for obj in [r.get("evse",{})]+r.get("ancestors",[]):
            for k,v in obj.items():
                lk=k.lower()
                if "name" in lk and isinstance(v,str) and v.strip():names.append(v.strip())
                if "authentication" in lk:
                    auth.append(json.dumps(v,sort_keys=True,ensure_ascii=False))
        if len(samples)<8:samples.append(r)
    out["operators"][op]={"evseCount":len(rows),"topNames":Counter(names).most_common(20),"authenticationValues":Counter(auth).most_common(20),"samples":samples}
Path("docs/switzerland-owner-gap-national-context-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({op:{"evseCount":v["evseCount"],"topNames":v["topNames"],"auth":v["authenticationValues"]} for op,v in out["operators"].items()},ensure_ascii=False,indent=2))
