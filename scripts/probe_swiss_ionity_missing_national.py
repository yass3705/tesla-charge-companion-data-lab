#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
TARGETS={"CH*IOY*E202471","CH*IOY*E202472","CH*IOY*E202473","CH*IOY*E202474","CH*IOY*E240101","CH*IOY*E240102","CH*IOY*E240171","CH*IOY*E240172","CH*IOY*E240173","CH*IOY*E240174","CH*IOY*E240175","CH*IOY*E240176","CH*IOY*E240177","CH*IOY*E240178","CH*IOY*E240179","CH*IOY*E240180"}
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
hits=[]
def walk(x,path=(),anc=()):
    if isinstance(x,dict):
        vals=set(v for v in x.values() if isinstance(v,str))
        found=TARGETS & vals
        if found:
            hits.append({"path":list(path),"found":sorted(found),"object":x,"ancestors":[a for a in anc[-3:]]})
        for k,v in x.items():
            walk(v,path+(str(k),),anc+(x,))
    elif isinstance(x,list):
        for i,v in enumerate(x):
            walk(v,path+(str(i),),anc)
walk(j)
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-ionity-national-missing-context-2026-09-28.json").write_text(json.dumps({"targets":sorted(TARGETS),"hits":hits},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"targetCount":len(TARGETS),"hitCount":len(hits),"hits":[{"found":h["found"],"path":h["path"],"object":h["object"]} for h in hits]},ensure_ascii=False,indent=2)[:120000])
