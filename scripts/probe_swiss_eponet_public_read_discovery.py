#!/usr/bin/env python3
import json,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from datetime import datetime,timezone

URL="https://portal.eponet.ch/api/publicCharger.php"
REFERER="https://portal.eponet.ch/public-charge.php"
HEAD={
 "User-Agent":"Mozilla/5.0 TCC-V9-Switzerland/1.0",
 "Accept":"application/json,text/plain,*/*",
 "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
 "X-Requested-With":"XMLHttpRequest",
 "Referer":REFERER
}
known=[
 ("shortcut","243fdf344f5a44f4872998649ca89eb3"),
 ("evse_example","CH*EPO*E0001579"),
 ("evse_current1","CH*EPO*E0001697"),
 ("evse_current2","CH*EPO*E0001727"),
 ("full_charger","23-2116"),
 ("numeric_charger","2116")
]
request_names=[
 "getChargerDetails","getMapChargers","getPublicChargers","getPublicCharger",
 "getCharger","searchChargers","getChargers","getChargerByEvse","getChargerByEvseId"
]
rows=[]
for reqname in request_names:
 for label,value in known:
  for field in ("id","charger_id","evse_id","evseId","full_charger_id","search"):
   form={"request":reqname,field:value}
   data=urllib.parse.urlencode(form).encode()
   req=urllib.request.Request(URL,data=data,headers=HEAD,method="POST")
   try:
    with urllib.request.urlopen(req,timeout=20) as r:
     raw=r.read(750000); status=r.status; ct=r.headers.get("content-type")
   except urllib.error.HTTPError as e:
    raw=e.read(750000); status=e.code; ct=e.headers.get("content-type")
   txt=raw.decode("utf-8","replace")
   parsed=None
   try: parsed=json.loads(txt)
   except: pass
   summary={"request":reqname,"field":field,"label":label,"value":value,"status":status,"contentType":ct}
   if isinstance(parsed,dict):
    summary["keys"]=list(parsed.keys())
    summary["ack"]=parsed.get("ack")
    summary["msg"]=parsed.get("msg") or parsed.get("message") or parsed.get("error")
    d=parsed.get("data")
    summary["dataType"]="list" if isinstance(d,list) else type(d).__name__
    summary["dataCount"]=len(d) if isinstance(d,list) else (len(d) if isinstance(d,dict) else None)
    if isinstance(d,list) and d:
     x=d[0] if isinstance(d[0],dict) else {}
     summary["sample"]={k:x.get(k) for k in ("charger_id","full_charger_id","evse_id_str","shortcut_url","name","rate_id","profile_id","performance","city","latitude","longitude") if k in x}
   else:
    summary["bodyPreview"]=txt[:300]
   rows.append(summary)
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"endpoint":URL,"tests":rows}
Path("docs/switzerland-eponet-public-read-discovery-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
interesting=[x for x in rows if x.get("ack")==1 or x.get("dataCount") not in (None,0) or x.get("status") not in (200,)]
print(json.dumps({"testCount":len(rows),"interesting":interesting[:500]},ensure_ascii=False,indent=2)[:120000])
