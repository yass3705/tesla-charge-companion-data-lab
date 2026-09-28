#!/usr/bin/env python3
import json,urllib.request,urllib.parse,re
from pathlib import Path
from datetime import datetime,timezone

UA={"User-Agent":"Mozilla/5.0","Accept":"application/json"}
base="https://app.move.ch/api/v2/move/search"
queries=[
 {"latitude":"46.204391","longitude":"6.143158"},
 {"latitude":"46.204391","longitude":"6.143158","radius":"50"},
 {"latitude":"46.204391","longitude":"6.143158","distance":"50"},
 {"latitude":"46.204391","longitude":"6.143158","maxDistance":"50"},
 {"latitude":"46.204391","longitude":"6.143158","limit":"100"}
]
res=[]
for q in queries:
    url=base+"?"+urllib.parse.urlencode(q)
    req=urllib.request.Request(url,headers=UA)
    try:
        with urllib.request.urlopen(req,timeout=45) as r:
            raw=r.read(5000000)
            text=raw.decode("utf-8","replace")
            try: parsed=json.loads(text)
            except Exception: parsed=None
            summary={"type":type(parsed).__name__ if parsed is not None else None}
            if isinstance(parsed,list):
                summary["count"]=len(parsed); summary["sample"]=parsed[:3]
            elif isinstance(parsed,dict):
                summary["keys"]=list(parsed.keys())[:100]
                for k,v in parsed.items():
                    if isinstance(v,list):
                        summary.setdefault("listCounts",{})[k]=len(v)
                        if v and "sample" not in summary: summary["sample"]=v[:3]
            res.append({"url":url,"status":r.status,"contentType":r.headers.get("content-type"),"bytes":len(raw),"summary":summary,"bodyPreview":text[:3000]})
    except Exception as e:
        res.append({"url":url,"error":type(e).__name__+": "+str(e)})
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"endpoint":base,"tests":res}
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-move-public-api-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2)[:100000])
