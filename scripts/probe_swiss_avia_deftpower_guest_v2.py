#!/usr/bin/env python3
import json,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from datetime import datetime,timezone

HOST="https://pdefweushaapiam01.azure-api.net"
TENANT="fdcb995a-8234-42ed-826f-3f2c7499d7f8"
LAT,LON=46.818,8.2275
paths=[
 "/cpos",
 f"/cpos?tenantId={TENANT}",
 "/map-locations",
 f"/map-locations?tenantId={TENANT}",
 f"/map-locations?tenantId={TENANT}&latitude={LAT}&longitude={LON}",
 f"/map-locations?tenantId={TENANT}&latitude={LAT}&longitude={LON}&radius=500",
 "/nearby-locations",
 f"/nearby-locations?tenantId={TENANT}",
 f"/nearby-locations?tenantId={TENANT}&latitude={LAT}&longitude={LON}",
 f"/nearby-locations?tenantId={TENANT}&latitude={LAT}&longitude={LON}&radius=500",
]
headersets=[
 {"User-Agent":"AVIA-VOLT-Suisse/2.3.0","Accept":"application/json"},
 {"User-Agent":"AVIA-VOLT-Suisse/2.3.0","Accept":"application/json","tenantId":TENANT},
 {"User-Agent":"AVIA-VOLT-Suisse/2.3.0","Accept":"application/json","TenantId":TENANT},
 {"User-Agent":"AVIA-VOLT-Suisse/2.3.0","Accept":"application/json","X-Tenant-Id":TENANT},
 {"User-Agent":"AVIA-VOLT-Suisse/2.3.0","Accept":"application/json","tenant-id":TENANT},
]
results=[]
for path in paths:
  for i,h in enumerate(headersets):
    req=urllib.request.Request(HOST+path,headers=h,method="GET")
    try:
      with urllib.request.urlopen(req,timeout=35) as r:
        raw=r.read(2500000)
        results.append({"path":path,"headerVariant":i,"status":r.status,"contentType":r.headers.get("content-type"),"bytes":len(raw),"body":raw.decode("utf-8","replace")[:2000000]})
    except urllib.error.HTTPError as e:
      raw=e.read(500000)
      results.append({"path":path,"headerVariant":i,"status":e.code,"contentType":e.headers.get("content-type"),"bytes":len(raw),"body":raw.decode("utf-8","replace")[:500000]})
    except Exception as e:
      results.append({"path":path,"headerVariant":i,"error":type(e).__name__+": "+str(e)})
    if results[-1].get("status") in (200,201,204): break
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"host":HOST,"tenantId":TENANT,"results":results}
Path("docs/switzerland-avia-deftpower-guest-probe-v2-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps([{k:v for k,v in r.items() if k!="body"}|{"bodyPreview":r.get("body","")[:1200]} for r in results if r.get("status") != 404],ensure_ascii=False,indent=2)[:120000])
