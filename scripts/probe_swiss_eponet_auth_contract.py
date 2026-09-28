#!/usr/bin/env python3
import json,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from datetime import datetime,timezone
BASE="https://api.eponet.io"
tests=[
 ("GET","portal/user/signin",None),
 ("POST","portal/user/signin",{}),
 ("POST","portal/user/signin",{"email":"","password":""}),
 ("GET","portal/user/register",None),
 ("POST","portal/user/register",{}),
 ("GET","ocpp/chargers/getmapchargers/",None),
 ("POST","ocpp/chargers/getmapchargers/",{}),
]
rows=[]
for method,path,payload in tests:
 data=None
 headers={"User-Agent":"Eponet/1.4.7 Android TCC-research","Accept":"application/json"}
 if payload is not None:
  data=json.dumps(payload).encode(); headers["Content-Type"]="application/json"
 req=urllib.request.Request(BASE+"/"+path,data=data,headers=headers,method=method)
 try:
  with urllib.request.urlopen(req,timeout=25) as r: raw=r.read(100000); status=r.status; h=dict(r.headers)
 except urllib.error.HTTPError as e: raw=e.read(100000); status=e.code; h=dict(e.headers)
 txt=raw.decode("utf-8","replace")
 # don't persist any response headers or credential-like values
 parsed=None
 try: parsed=json.loads(txt)
 except: pass
 safe=parsed if isinstance(parsed,(dict,list)) else txt[:2000]
 rows.append({"method":method,"path":path,"payloadKeys":list(payload.keys()) if isinstance(payload,dict) else None,"status":status,"contentType":h.get("Content-Type") or h.get("content-type"),"response":safe})
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"tests":rows}
Path("docs/switzerland-eponet-auth-contract-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
