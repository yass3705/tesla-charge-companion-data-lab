#!/usr/bin/env python3
import json,math
from pathlib import Path
OFF=Path("data/switzerland/ionity-official-direct-tariffs.json")
ATLAS=Path("data/switzerland/ioy-direct-tariffs-second-pass.json")
OUT=Path("docs/switzerland-ionity-coordinate-reconciliation-2026-09-28.json")
def hav(a,b,c,d):
    R=6371000
    p1,p2=math.radians(a),math.radians(c)
    dp=math.radians(c-a);dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(x))
o=json.loads(OFF.read_text(encoding="utf-8")); a=json.loads(ATLAS.read_text(encoding="utf-8"))
offs=o.get("locations",[]); ats=a.get("stations",[])
rows=[]; used=set()
for st in ats:
    lat=st.get("latitude");lon=st.get("longitude")
    candidates=[]
    for loc in offs:
        try:d=hav(float(lat),float(lon),float(loc["latitude"]),float(loc["longitude"]))
        except:continue
        candidates.append((d,loc))
    candidates.sort(key=lambda z:z[0])
    best=candidates[0] if candidates else None
    second=candidates[1][0] if len(candidates)>1 else None
    match=None
    if best and best[0] <= 1500 and (second is None or best[0]+250 < second):
        match=best[1];used.add(match["uuid"])
    prices=sorted(set((c.get("amount"),c.get("currency"),c.get("unit")) for c in (match or {}).get("connectors",[]) if c.get("amount") is not None))
    rows.append({"atlasStationId":st.get("stationId"),"atlasName":st.get("name"),"evseIds":st.get("evseIds") or [],
                 "atlasLat":lat,"atlasLon":lon,"officialUuid":match.get("uuid") if match else None,
                 "officialName":match.get("name") if match else None,"distanceMeters":round(best[0],1) if best else None,
                 "officialDirectPrices":[{"amount":x[0],"currency":x[1],"unit":x[2]} for x in prices],
                 "ambiguous":bool(match and len(prices)!=1)})
unmatched=[{"uuid":x.get("uuid"),"name":x.get("name"),"lat":x.get("latitude"),"lon":x.get("longitude"),
            "prices":sorted(set((c.get("amount"),c.get("currency"),c.get("unit")) for c in x.get("connectors",[]) if c.get("amount") is not None))}
           for x in offs if x.get("uuid") not in used]
out={"atlasStationCount":len(ats),"officialLocationCount":len(offs),
     "matchedAtlasStations":sum(1 for x in rows if x["officialUuid"]),
     "matchedEvseCount":sum(len(x["evseIds"]) for x in rows if x["officialUuid"] and not x["ambiguous"]),
     "unmatchedOfficialLocations":unmatched,"rows":rows}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k!="rows"},ensure_ascii=False,indent=2))
print(json.dumps(rows,ensure_ascii=False,indent=2))
