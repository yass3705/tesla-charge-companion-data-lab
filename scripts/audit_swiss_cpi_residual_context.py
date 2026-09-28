#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
IDS={"CHCPIE6951745*1","CHCPIE6951745*2","CHCPIE6951765*1","CHCPIE6951765*2","CHCPIE6951795*1","CHCPIE6951795*2"}
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
req=urllib.request.Request(URL,headers={"User-Agent":"TCC/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
x=json.loads(raw.decode())
hits=[]
def walk(o,anc=()):
 if isinstance(o,dict):
  if o.get("EvseID") in IDS:hits.append({"evseId":o.get("EvseID"),"record":o,"ancestors":list(anc[-2:])})
  for v in o.values():walk(v,anc+(o,))
 elif isinstance(o,list):
  for v in o:walk(v,anc)
walk(x)
Path("docs/switzerland-cpi-residual-national-context-2026-09-28.json").write_text(json.dumps({"hits":hits},ensure_ascii=False,indent=2)+"\n")
print(json.dumps([{"evseId":h["evseId"],"record":h["record"]} for h in hits],ensure_ascii=False,indent=2))
