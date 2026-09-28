#!/usr/bin/env python3
import json, gzip, urllib.request
from pathlib import Path
from datetime import datetime, timezone

URL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
TARGET={
"CH*SOC*E5101*2A","CH*SOC*E5101*2B","CH*SOC*E5102*1A","CH*SOC*E5102*1B",
"CH*SOC*E5139*1A","CH*SOC*E5139*1B","CH*SOC*E5591*2A","CH*SOC*E5591*2B",
"CH*SOC*E5591*2C","CH*SOC*E5593*1A","CH*SOC*E5593*1B","CH*SOC*E5593*2A","CH*SOC*E5593*2B"
}
req=urllib.request.Request(URL,headers={"User-Agent":"TCC-V9-Switzerland/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=120) as r:
    raw=r.read()
    if raw[:2] == b"\\x1f\\x8b":
        raw=gzip.decompress(raw)
    data=json.loads(raw.decode("utf-8"))

rows=[]
def walk(x, ancestors):
    if isinstance(x, dict):
        anc=ancestors
        if any(k in x for k in ("OperatorID","OperatorName","EvseID","ChargingStationId")):
            anc=ancestors+[{k:x.get(k) for k in ("OperatorID","OperatorName","EvseID","ChargingStationId") if k in x}]
        eid=x.get("EvseID")
        if eid in TARGET:
            rows.append({"evseId":eid,"evse":x,"context":ancestors})
        for v in x.values(): walk(v,anc)
    elif isinstance(x,list):
        for v in x: walk(v,ancestors)
walk(data,[])
seen={r["evseId"] for r in rows}
out={
 "generatedAt":datetime.now(timezone.utc).isoformat(),
 "source":URL,
 "targetCount":len(TARGET),
 "foundCount":len(seen),
 "missing":sorted(TARGET-seen),
 "rows":rows
}
Path("docs/switzerland-soc-residual-national-context-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"targetCount":len(TARGET),"foundCount":len(seen),"missing":sorted(TARGET-seen),
 "summary":[{"evseId":r["evseId"],"address":r["evse"].get("Address"),"names":r["evse"].get("ChargingStationNames"),"facilities":r["evse"].get("ChargingFacilities"),"auth":r["evse"].get("AuthenticationModes"),"payment":r["evse"].get("PaymentOptions"),"accessibility":r["evse"].get("Accessibility")} for r in rows]},ensure_ascii=False,indent=2))

# trigger
