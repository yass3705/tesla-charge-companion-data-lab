#!/usr/bin/env python3
import json,time,urllib.request,urllib.parse
from pathlib import Path
from collections import Counter,defaultdict
BASE="https://ecarup.com/api/stations"
UA={"User-Agent":"eCarUp/2.6.0 Android TCC-readonly","Accept":"application/json"}
# Dense grid over Switzerland; endpoint is proximity based. Overlap is intentional, dedupe by station ID.
lats=[45.85+i*0.22 for i in range(10)]
lons=[5.95+i*0.32 for i in range(15)]
stations={}
errors=[]
request_count=0
for lat in lats:
  for lon in lons:
    q=urllib.parse.urlencode({"location":f"{lat:.5f},{lon:.5f}","includePartners":"true","onlyAvailable":"false"})
    url=BASE+"?"+q
    request_count+=1
    try:
      req=urllib.request.Request(url,headers=UA)
      with urllib.request.urlopen(req,timeout=35) as r:
        rows=json.loads(r.read().decode("utf-8"))
      if not isinstance(rows,list): rows=[]
      for s in rows:
        sid=s.get("ID")
        slat=s.get("Latitude"); slon=s.get("Longitude")
        if not sid: continue
        # Keep Swiss bounding box + small border tolerance only.
        if isinstance(slat,(int,float)) and isinstance(slon,(int,float)) and 45.7<=slat<=48.1 and 5.7<=slon<=10.8:
          stations[sid]=s
    except Exception as e:
      errors.append({"url":url,"error":type(e).__name__+": "+str(e)})
    time.sleep(0.08)

ops=Counter()
opstations=defaultdict(list)
for sid,s in stations.items():
  op=((s.get("ContactDetails") or {}).get("OperatorName") or "").strip()
  ops[op]+=1
  opstations[op].append(sid)

summary=[{"operatorName":k,"stationCount":v} for k,v in ops.most_common()]
out={
 "schemaVersion":1,"country":"CH","source":"eCarUp public Android-app API",
 "endpoint":BASE,"queryFormat":"location=lat,lng&includePartners=true&onlyAvailable=false",
 "requestCount":request_count,"errorCount":len(errors),"stationCount":len(stations),
 "operatorCount":len(ops),"operatorSummary":summary,"errors":errors,
 "stations":list(stations.values())
}
Path("data/switzerland").mkdir(parents=True,exist_ok=True)
Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/ecarup-public-stations.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
Path("docs/switzerland-ecarup-public-coverage-2026-09-28.json").write_text(json.dumps({k:v for k,v in out.items() if k!="stations"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"requests":request_count,"errors":len(errors),"stations":len(stations),"operators":len(ops),"topOperators":summary[:40]},ensure_ascii=False,indent=2))
