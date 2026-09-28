#!/usr/bin/env python3
import json,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone

BASE="https://app.move.ch"
UA={"User-Agent":"Mozilla/5.0","Accept":"application/json,text/plain,*/*"}
connector="66472"
station="10762"
location="2278"
paths=[
 "/swagger/v1/swagger.json","/swagger/index.html","/swagger.json","/openapi.json","/api/swagger/v1/swagger.json",
 f"/api/v2/move/connector/{connector}",f"/api/v2/move/connectors/{connector}",
 f"/api/v2/move/chargingstationconnector/{connector}",f"/api/v2/move/charging-station-connector/{connector}",
 f"/api/v2/move/station/{station}",f"/api/v2/move/stations/{station}",
 f"/api/v2/move/location/{location}",f"/api/v2/move/locations/{location}",
 f"/api/v2/move/tariff/{connector}",f"/api/v2/move/tariffs/{connector}",
 f"/api/v2/move/price/{connector}",f"/api/v2/move/prices/{connector}",
 f"/api/v2/move/price?chargingStationConnectorId={connector}",
 f"/api/v2/move/tariff?chargingStationConnectorId={connector}",
 f"/api/v2/move/chargingStationConnector?chargingStationConnectorId={connector}",
]
res=[]
for path in paths:
  url=BASE+path
  req=urllib.request.Request(url,headers=UA)
  try:
    with urllib.request.urlopen(req,timeout=25) as r:
      raw=r.read(300000)
      res.append({"path":path,"status":r.status,"contentType":r.headers.get("content-type"),"body":raw.decode("utf-8","replace")[:120000]})
  except urllib.error.HTTPError as e:
    raw=e.read(50000)
    res.append({"path":path,"status":e.code,"contentType":e.headers.get("content-type"),"body":raw.decode("utf-8","replace")[:20000]})
  except Exception as e:
    res.append({"path":path,"error":type(e).__name__+": "+str(e)})
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"base":BASE,"testConnectorId":connector,"testStationId":station,"testLocationId":location,"results":res}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-move-api-route-discovery-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps([{"path":x["path"],"status":x.get("status"),"contentType":x.get("contentType"),"bodyPreview":x.get("body","")[:600]} for x in res],ensure_ascii=False,indent=2))
