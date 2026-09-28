#!/usr/bin/env python3
import json
from pathlib import Path
src=json.loads(Path("data/switzerland/ecarup-public-stations.json").read_text(encoding="utf-8"))
names={"Elektrizitätswerk Obwalden","ebs Energie AG","Aziende Industriali di Lugano (AIL) SA"}
out={}
for name in names:
 rows=[]
 for s in src.get("stations",[]):
  if ((s.get("ContactDetails") or {}).get("OperatorName") or "").strip()==name:
   rows.append({"id":s.get("ID"),"name":s.get("Name"),"address":s.get("Address"),"lat":s.get("Latitude"),"lon":s.get("Longitude"),
                "connectors":[{"id":c.get("Id"),"name":c.get("Name"),"maxPowerW":c.get("MaxPower"),"accessType":c.get("AccessType"),
                               "state":c.get("State"),"hubject":(c.get("Hubject") or {}).get("ID"),"price":c.get("Price")} for c in s.get("Connectors") or []]})
 out[name]=rows
Path("docs/switzerland-ecarup-target-operator-stations-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:{"count":len(v),"stations":v} for k,v in out.items()},ensure_ascii=False,indent=2)[:180000])
