#!/usr/bin/env python3
import json, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from datetime import datetime,timezone

URL="https://portal.eponet.ch/api/publicCharger.php"
QR="243fdf344f5a44f4872998649ca89eb3"
data=urllib.parse.urlencode({"request":"getChargerDetails","id":QR}).encode()
req=urllib.request.Request(URL,data=data,headers={
 "User-Agent":"Mozilla/5.0 TCC-V9-Switzerland/1.0",
 "Accept":"application/json,text/plain,*/*",
 "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
 "Referer":"https://portal.eponet.ch/public-charge.php?id="+QR,
 "X-Requested-With":"XMLHttpRequest"
},method="POST")
try:
 with urllib.request.urlopen(req,timeout=30) as r:
  raw=r.read(2000000)
  status=r.status
  ctype=r.headers.get("content-type")
except urllib.error.HTTPError as e:
 raw=e.read(2000000); status=e.code; ctype=e.headers.get("content-type")
text=raw.decode("utf-8","replace")
parsed=None
try: parsed=json.loads(text)
except: pass

def sanitize(obj):
 if isinstance(obj,dict):
  # retain only read-only station/pricing context, drop payment/session/account/security fields
  deny=("token","secret","password","payment","stripe","datatrans","session","cookie","auth","email","phone","account_balance","client")
  out={}
  for k,v in obj.items():
   lk=k.lower()
   if any(d in lk for d in deny): continue
   out[k]=sanitize(v)
  return out
 if isinstance(obj,list): return [sanitize(v) for v in obj]
 return obj

safe=sanitize(parsed) if parsed is not None else {"bodyPreview":text[:10000]}
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"endpoint":URL,"request":{"request":"getChargerDetails","id":QR},"status":status,"contentType":ctype,"response":safe}
Path("docs/switzerland-eponet-public-charge-example-response-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2)[:120000])
