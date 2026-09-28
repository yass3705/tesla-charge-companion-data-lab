#!/usr/bin/env python3
import json
from pathlib import Path

targets={
"CH*360":set(["CH*360*E91620","CH*360*E91621","CH*360*E91622","CH*360*E212018","CH*360*E60316","CH*360*E130912","CH*360*E130913","CH*360*E171920","CH*360*E171921","CH*360*E325109","CH*360*E325110"]),
"CH*EWZ":set(["CH*EWZ*E1777"]),
"CH*ELC":set(["CH*ELC*E4T8H","CH*ELC*E56XR","CH*ELC*E5HLN","CH*ELC*ED4V5","CH*ELC*EEKN7","CH*ELC*EEQB9"]),
}
files={
"CH*360":["data/switzerland/energie360-direct-tariffs.json","docs/switzerland-current-scope-reconciliation-2026-09-27.json"],
"CH*EWZ":["data/switzerland/ewz-direct-tariffs.json","data/switzerland/ewz-direct-tariffs-second-pass.json","docs/switzerland-current-scope-reconciliation-2026-09-27.json"],
"CH*ELC":["data/switzerland/electra-direct-tariffs.json","data/switzerland/electra-direct-tariffs-second-pass.json"],
}
out={}
for op,ids in targets.items():
 out[op]={}
 for fp in files[op]:
  p=Path(fp)
  if not p.exists() or p.stat().st_size==0:
   out[op][fp]={"status":"missing_or_empty"}; continue
  try: obj=json.loads(p.read_text())
  except Exception as e:
   out[op][fp]={"status":"invalid","error":str(e)}; continue
  hits=[]
  def walk(x,path="$"):
   if isinstance(x,dict):
    txt_ids=[]
    for k in ("evseId","EvseID"):
     if isinstance(x.get(k),str): txt_ids.append(x[k])
    for k in ("evseIds","evse_ids"):
     if isinstance(x.get(k),list): txt_ids += [z for z in x[k] if isinstance(z,str)]
    if any(z in ids for z in txt_ids):
     slim={k:v for k,v in x.items() if k not in ("nationalRecord","atlasRecords","portalAttempts")}
     hits.append({"path":path,"ids":[z for z in txt_ids if z in ids],"node":slim})
    for k,v in x.items():
     if isinstance(v,(dict,list)): walk(v,path+"."+str(k))
   elif isinstance(x,list):
    for i,v in enumerate(x):
     if isinstance(v,(dict,list)): walk(v,path+f"[{i}]")
  walk(obj)
  out[op][fp]={"status":"ok","hits":hits[:100]}
Path("docs/switzerland-v9-residual-source-audit-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({op:{fp:{"status":x["status"],"hitCount":len(x.get("hits",[]))} for fp,x in fs.items()} for op,fs in out.items()},indent=2))
