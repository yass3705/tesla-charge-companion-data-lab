#!/usr/bin/env python3
import json,urllib.request,urllib.error,urllib.parse
from pathlib import Path
BASES=["https://ecarup.com/api/","https://staging.ecarup.com/api/"]
paths=[
"stations",
"stations?location=46.8182%2C8.2275&includePartners=true&onlyAvailable=false",
"stations?location=47.3769%2C8.5417&includePartners=true&onlyAvailable=false",
"stations?searchTerm=IWB&location=47.3769%2C8.5417&includePartners=true&onlyAvailable=false&onlyRecentlyUsed=false",
"stations/search?qr=CH%2AEBS%2AE123%2A0001",
"stations/search?qr=CH%2AEWO%2AE123%2A0001",
"stations/search","stations/favorite","chargings","v2/chargings"
]
UA={"User-Agent":"eCarUp/2.6.0 Android TCC-research","Accept":"application/json"}
out=[]
for base in BASES:
  for path in paths:
    for method in ("GET","OPTIONS"):
      url=urllib.parse.urljoin(base,path)
      req=urllib.request.Request(url,headers=UA,method=method)
      try:
        with urllib.request.urlopen(req,timeout=30) as r:
          body=r.read(12000).decode("utf-8","replace")
          out.append({"url":url,"method":method,"status":r.status,"finalUrl":r.geturl(),"headers":dict(r.headers),"body":body})
      except urllib.error.HTTPError as e:
        body=e.read(12000).decode("utf-8","replace")
        out.append({"url":url,"method":method,"status":e.code,"headers":dict(e.headers),"body":body})
      except Exception as e:
        out.append({"url":url,"method":method,"error":type(e).__name__+": "+str(e)})
Path("docs").mkdir(exist_ok=True)
Path("docs/switzerland-ecarup-api-probe-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
