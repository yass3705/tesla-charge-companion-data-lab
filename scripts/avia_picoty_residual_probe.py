#!/usr/bin/env python3
import json, os, subprocess, time
from pathlib import Path
from urllib.parse import urlencode

API=os.environ.get("AVIA_API_BASE","https://pdefweushaapiam01.azure-api.net").rstrip("/")
TENANT="9439c762-3ce1-45fc-a9ea-a92ed5e06489"
KEY=os.environ.get("AVIA_APIM_SUBSCRIPTION_KEY","").strip()
INDEX=Path("data/national/avia_volt_picoty_station_index.json")
EXACT=Path("data/operator_direct/avia_picoty_deftpower_exact_france.json")
OUT=Path("data/reports/avia_picoty_residual_probe.json")

def norm(v): return "".join(ch for ch in str(v or "").upper() if ch.isalnum())
def req(path,q=None):
    url=API+path
    if q: url+="?"+urlencode(q)
    cmd=["curl","-sS","--fail-with-body","--max-time","35",
         "-H","accept: application/json","-H","x-app-platform: ios",
         "-H","x-app-version: 2.3.0","-H","user-agent: RechargeEtVous/4614 CFNetwork",
         "-H",f"ocp-apim-subscription-key: {KEY}",url]
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout)[:400])
    return json.loads(p.stdout)
def coords(raw):
    s=str(raw or "").strip().strip("[]")
    a=[x.strip() for x in s.split(",")]
    return float(a[1]),float(a[0])

def main():
    idx=json.loads(INDEX.read_text())
    exact=json.loads(EXACT.read_text())
    matched={x.get("stationId") for x in exact.get("connectors",[])}
    stations=[x for x in idx.get("stations",[]) if x.get("stationId") not in matched]
    report={"schemaVersion":1,"tenant":TENANT,"residualCount":len(stations),"stations":[]}
    for st in stations:
        lat,lon=coords(st.get("coordinatesRaw"))
        expected={norm(x) for x in st.get("pdcIds",[])}
        candidates={}
        attempts=[]
        for delta in (0.035,0.10,0.25):
          for status in ("AVAILABLE","UNKNOWN","OUT_OF_ORDER"):
            q={
              "latLongBottomLeft":f"{lat-delta:.6f},{lon-delta:.6f}",
              "latLongTopRight":f"{lat+delta:.6f},{lon+delta:.6f}",
              "evseTypes":"AC,DC,HPC",
              "connectorTypes":"TYPE2,CCS",
              "includeCpos":"FRPY2",
              "locationStatus":status,
            }
            try:
              data=req(f"/app-backend/v1/tenants/{TENANT}/map-locations",q)
              locs=data.get("locations") or []
              attempts.append({"delta":delta,"status":status,"locations":len(locs)})
              for loc in locs:
                lid=loc.get("id")
                if not lid or lid in candidates: continue
                try:
                  d=req(f"/app-backend/v1/tenants/{TENANT}/locations/{lid}")
                  evses=d.get("evses") or []
                  ids=[e.get("evseId") for e in evses if e.get("evseId")]
                  nids={norm(x) for x in ids}
                  candidates[lid]={
                    "locationUuid":lid,"locationName":d.get("locationName"),
                    "address":d.get("address"),"postalCode":d.get("postalCode"),"city":d.get("city"),
                    "coordinates":d.get("coordinates"),"evseIds":ids,
                    "exactEvseMatches":sorted(expected & nids),
                    "partyId":loc.get("partyId"),
                  }
                except Exception as e:
                  candidates[lid]={"locationUuid":lid,"detailError":str(e)}
            except Exception as e:
              attempts.append({"delta":delta,"status":status,"error":str(e)})
            time.sleep(0.08)
        report["stations"].append({
          "stationId":st.get("stationId"),"stationName":st.get("stationName"),
          "address":st.get("address"),"coordinatesRaw":st.get("coordinatesRaw"),
          "expectedEvseIds":st.get("pdcIds") or [],"attempts":attempts,
          "candidates":list(candidates.values())
        })
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"residualCount":len(stations),"candidateCounts":[[x["stationId"],len(x["candidates"])] for x in report["stations"]]},ensure_ascii=False))
if __name__=="__main__": main()
