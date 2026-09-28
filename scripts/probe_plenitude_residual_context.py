#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
TARGETS={
"CH*PLN*EH000767*1","CH*PLN*EH000767*2","CH*PLN*EH000767*3",
"CH*PLN*EH000771*1","CH*PLN*EH000771*2","CH*PLN*EH000771*3",
"CH*PLN*EH000776*1","CH*PLN*EH000776*2","CH*PLN*EH000776*3"}
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode())
hits={}
def walk(x,anc=()):
 if isinstance(x,dict):
  eid=x.get("EvseID")
  if eid in TARGETS:hits[eid]={"record":x,"ancestors":[a for a in anc[-4:] if isinstance(a,dict)]}
  for v in x.values():walk(v,anc+(x,))
 elif isinstance(x,list):
  for v in x:walk(v,anc)
walk(j)
Path("docs/switzerland-plenitude-residual-national-context-2026-09-28.json").write_text(json.dumps(hits,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(hits,ensure_ascii=False,indent=2)[:150000])
