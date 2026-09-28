#!/usr/bin/env python3
import json,urllib.request,urllib.parse,urllib.error,ssl
from pathlib import Path
from datetime import datetime,timezone

TENANT="fdcb995a-8234-42ed-826f-3f2c7499d7f8"
HOSTS=[
 "https://pdefweushaapiam01.azure-api.net",
 "https://pdefweushaapiam01.azure-api.net/",
 "https://pdefweucusapias01web.azurewebsites.net",
]
lat,lon=46.818,8.2275
paths=[
 "/",
 f"/tenants/{TENANT}/cpos",
 f"/v1/tenants/{TENANT}/cpos",
 f"/tenants/{TENANT}/map-locations?latitude={lat}&longitude={lon}&radius=1000",
 f"/v1/tenants/{TENANT}/map-locations?latitude={lat}&longitude={lon}&radius=1000",
 f"/tenants/{TENANT}/nearby-locations?latitude={lat}&longitude={lon}&radius=1000",
 f"/v1/tenants/{TENANT}/nearby-locations?latitude={lat}&longitude={lon}&radius=1000",
 f"/map-locations-as-guest?tenantId={TENANT}&latitude={lat}&longitude={lon}&radius=1000",
 f"/nearby-locations-as-guest?tenantId={TENANT}&latitude={lat}&longitude={lon}&radius=1000",
 f"/get-map-locations-as-guest?tenantId={TENANT}&latitude={lat}&longitude={lon}&radius=1000",
 f"/get-nearby-locations-as-guest?tenantId={TENANT}&latitude={lat}&longitude={lon}&radius=1000",
 f"/get-cpos-as-guest?tenantId={TENANT}",
]
header_sets=[
 {"User-Agent":"AVIA-VOLT-Suisse/2.3.0","Accept":"application/json"},
 {"User-Agent":"AVIA-VOLT-Suisse/2.3.0","Accept":"application/json","tenantId":TENANT},
 {"User-Agent":"AVIA-VOLT-Suisse/2.3.0","Accept":"application/json","TenantId":TENANT},
 {"User-Agent":"AVIA-VOLT-Suisse/2.3.0","Accept":"application/json","X-Tenant-Id":TENANT},
]
results=[]
seen=set()
for host in HOSTS:
  host=host.rstrip("/")
  for path in paths:
    url=host+path
    for hi,headers in enumerate(header_sets):
      key=(url,hi)
      if key in seen: continue
      seen.add(key)
      req=urllib.request.Request(url,headers=headers,method="GET")
      try:
        with urllib.request.urlopen(req,timeout=25,context=ssl.create_default_context()) as r:
          raw=r.read(1500000)
          txt=raw.decode("utf-8","replace")
          results.append({"url":url,"headerVariant":hi,"status":r.status,"contentType":r.headers.get("content-type"),"bytes":len(raw),"body":txt[:500000]})
      except urllib.error.HTTPError as e:
        raw=e.read(300000); txt=raw.decode("utf-8","replace")
        results.append({"url":url,"headerVariant":hi,"status":e.code,"contentType":e.headers.get("content-type"),"bytes":len(raw),"body":txt[:300000]})
      except Exception as e:
        results.append({"url":url,"headerVariant":hi,"error":type(e).__name__+": "+str(e)})
      # Stop testing header variants after a meaningful non-auth success or useful route signal.
      last=results[-1]
      if last.get("status") in (200,201,204): break

interesting=[r for r in results if r.get("status") not in (404,None) or "azure-api.net" in r.get("url","") and r.get("error")]
out={
 "generatedAt":datetime.now(timezone.utc).isoformat(),
 "apk":{"package":"ch.avia.volt","version":"2.3.0","tenantId":TENANT,"features":["GUEST_APP_ACCESS","PRICE_SIMULATION"],"environment":"prd"},
 "results":results,
 "interesting":interesting,
}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-avia-deftpower-guest-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps([{k:v for k,v in r.items() if k!="body"}|{"bodyPreview":r.get("body","")[:700]} for r in interesting],ensure_ascii=False,indent=2)[:120000])
