#!/usr/bin/env python3
import json,re,urllib.request
from pathlib import Path
from datetime import datetime,timezone

URLS=["https://www.move.ch/karte/main.js","https://www.move.ch/karte/main-genf.js"]
UA={"User-Agent":"Mozilla/5.0"}
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"files":[]}
for url in URLS:
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=40) as r:
        txt=r.read(500000).decode("utf-8","replace")
    hits=[]
    for m in re.finditer(r'app\.move\.ch|api/v\d+|ajax|ChargingStationConnectorId|tariff|price',txt,re.I):
        a=max(0,m.start()-900); b=min(len(txt),m.end()+1800)
        ctx=txt[a:b]
        if ctx not in hits:hits.append(ctx)
    out["files"].append({"url":url,"bytes":len(txt),"contexts":hits[:80]})
Path("docs/switzerland-move-map-source-context-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2)[:120000])
