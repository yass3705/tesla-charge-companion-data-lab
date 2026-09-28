#!/usr/bin/env python3
import gzip,json,urllib.request
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone
URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
req=urllib.request.Request(URL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))
cnt=Counter()
owners=Counter()
def walk(x,owner=None):
    if isinstance(x,dict):
        if isinstance(x.get("OperatorID"),str): owner=x.get("OperatorID")
        eid=x.get("EvseID")
        if isinstance(eid,str) and "*E" in eid:
            pref=eid.split("*E",1)[0]
            cnt[pref]+=1
            if owner: owners[(pref,owner)]+=1
        for v in x.values(): walk(v,owner)
    elif isinstance(x,list):
        for v in x: walk(v,owner)
walk(j)
rows=[{"operatorId":k,"evseCount":v,"ownerContexts":[{"operatorId":o,"count":n} for (p,o),n in owners.items() if p==k]} for k,v in cnt.most_common()]
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"source":URL,"operatorCount":len(rows),"evseCount":sum(cnt.values()),"operators":rows}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-national-cpo-counts-current-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
