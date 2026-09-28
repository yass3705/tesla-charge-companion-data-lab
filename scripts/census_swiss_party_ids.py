#!/usr/bin/env python3
import gzip,json,urllib.request,re
from collections import defaultdict,Counter
from pathlib import Path
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
j=json.loads(raw.decode())
by=defaultdict(list)
def walk(x,owner=None):
 if isinstance(x,dict):
  if isinstance(x.get("OperatorID"),str) and x["OperatorID"].strip():owner=x["OperatorID"].strip()
  eid=x.get("EvseID")
  if owner and isinstance(eid,str):by[owner].append(eid)
  for v in x.values():walk(v,owner)
 elif isinstance(x,list):
  for v in x:walk(v,owner)
walk(j)
def party(eid):
 s=eid.strip()
 # canonical eMI3-like: country*party*E...
 m=re.match(r'^([A-Z]{2}\*[A-Z0-9]{3})\*E',s,re.I)
 if m:return m.group(1).upper()
 # compact eMI3-like: country + party + E...
 m=re.match(r'^([A-Z]{2})([A-Z0-9]{3})E',s,re.I)
 if m:return (m.group(1)+'*'+m.group(2)).upper()
 # some providers use longer literal IDs; don't invent party id.
 return None
out=[]
allp=Counter();unparsed=0
for owner,ids in sorted(by.items(),key=lambda kv:(-len(set(kv[1])),kv[0])):
 c=Counter(party(x) or "__UNPARSED__" for x in set(ids));allp.update(c);unparsed+=c["__UNPARSED__"]
 out.append({"feedOperatorId":owner,"evseCount":len(set(ids)),"partyIdBreakdown":dict(c),"sampleEvseIds":sorted(set(ids))[:20]})
doc={"source":URL,"feedOperatorCount":len(out),"parsedPartyIdCount":len([k for k in allp if k!="__UNPARSED__"]),
     "unparsedEvseCount":unparsed,"partyTotals":dict(allp),"feedOperators":out}
Path("docs/switzerland-partyid-census-2026-09-28.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"feedOperatorCount":doc["feedOperatorCount"],"parsedPartyIdCount":doc["parsedPartyIdCount"],"unparsedEvseCount":unparsed,
                  "partyTotals":dict(allp),"feedOperators":out},ensure_ascii=False,indent=2))
