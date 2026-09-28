#!/usr/bin/env python3
import gzip,json,math,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
OFF_PATH=Path("data/switzerland/ionity-official-direct-tariffs.json")
OUT=Path("data/switzerland/ionity-official-national-direct-tariffs.json")
FINAL=Path("docs/switzerland-ionity-national-finalization-2026-09-28.json")
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}

def getj(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
    if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))

def walk(o):
    if isinstance(o,dict):
        yield o
        for v in o.values(): yield from walk(v)
    elif isinstance(o,list):
        for v in o: yield from walk(v)

def coords(d):
    g=(d.get("GeoCoordinates") or {}).get("Google")
    if isinstance(g,str):
        try:
            a,b=g.replace(","," ").split()[:2]
            return float(a),float(b)
        except: pass
    return None

def hav(a,b,c,d):
    R=6371000.0
    p1,p2=math.radians(a),math.radians(c)
    dp=math.radians(c-a);dl=math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(x))

nat=getj(NATIONAL)
official=json.loads(OFF_PATH.read_text(encoding="utf-8"))
locs=official.get("locations",[])
evses={}
for d in walk(nat):
    eid=d.get("EvseID") if isinstance(d,dict) else None
    if isinstance(eid,str) and eid.startswith("CH*IOY*E"):
        evses[eid]=d

rows=[]; unresolved=[]
for eid,d in sorted(evses.items()):
    xy=coords(d)
    powers=[]
    for f in d.get("ChargingFacilities") or []:
        try:powers.append(float(f.get("power")))
        except: pass
    p=max(powers) if powers else None
    if not xy:
        unresolved.append({"evseId":eid,"reason":"missing_national_coordinates","powerKw":p});continue
    ranked=[]
    for loc in locs:
        try:dist=hav(xy[0],xy[1],float(loc["latitude"]),float(loc["longitude"]))
        except:continue
        ranked.append((dist,loc))
    ranked.sort(key=lambda x:x[0])
    if not ranked or ranked[0][0]>2000:
        unresolved.append({"evseId":eid,"reason":"no_official_location_within_2km","coordinate":xy,"nearestMeters":round(ranked[0][0],1) if ranked else None});continue
    dist,loc=ranked[0]
    # Require strong spatial uniqueness unless the best location is essentially exact.
    second=ranked[1][0] if len(ranked)>1 else 1e12
    if dist>50 and second-dist<250:
        unresolved.append({"evseId":eid,"reason":"ambiguous_official_location","coordinate":xy,"bestMeters":round(dist,1),"secondMeters":round(second,1)});continue
    conns=[c for c in loc.get("connectors",[]) if c.get("amount") is not None and c.get("currency")=="CHF" and str(c.get("unit","")).lower()=="kwh"]
    if not conns:
        unresolved.append({"evseId":eid,"reason":"official_location_has_no_direct_price","officialLocation":loc.get("name")});continue
    # At mixed-price sites, exact/max-power is the discriminator used by the official connector feed.
    prices=set()
    selected=[]
    if p is not None:
        exact=[c for c in conns if c.get("maxPowerW") is not None and abs(float(c["maxPowerW"])/1000.0-p)<=1.0]
        if exact: selected=exact
    if not selected:
        unique_amounts={float(c["amount"]) for c in conns}
        if len(unique_amounts)==1:selected=conns
    for c in selected:prices.add((float(c["amount"]),c.get("currency"),c.get("unit")))
    if len(prices)!=1:
        unresolved.append({"evseId":eid,"reason":"ambiguous_connector_price","officialLocation":loc.get("name"),"powerKw":p,
                           "available":[{"maxPowerKw":(float(c["maxPowerW"])/1000.0 if c.get("maxPowerW") is not None else None),"amount":c.get("amount")} for c in conns]});continue
    amount,curr,unit=next(iter(prices))
    rows.append({"evseId":eid,"chargingStationId":d.get("ChargingStationId"),"latitude":xy[0],"longitude":xy[1],
                 "maxPowerKw":p,"officialLocationUuid":loc.get("uuid"),"officialLocationName":loc.get("name"),
                 "distanceMeters":round(dist,1),"pricePerKwh":amount,"currency":curr,"product":"IONITY DIRECT",
                 "source":"IONITY public v3 connector adhocPrice"})

now=datetime.now(timezone.utc).isoformat()
status="complete" if evses and len(rows)==len(evses) and not unresolved else "partial"
payload={"schemaVersion":1,"country":"CH","cpo":"IONITY","operatorId":"CH*IOY","generatedAt":now,
 "sources":{"national":NATIONAL,"officialLocations":"data/switzerland/ionity-official-direct-tariffs.json"},
 "counts":{"nationalEvseCount":len(evses),"pricedEvseCount":len(rows),"unresolvedEvseCount":len(unresolved)},
 "policy":"Exact current national EVSE coordinates matched to official IONITY Swiss locations; at mixed-price sites, national EVSE power must match official connector power. IONITY DIRECT only; no roaming/subscriber tariff and no cross-station extrapolation.",
 "evses":rows,"unresolved":unresolved}
final={"schemaVersion":1,"country":"CH","cpo":"IONITY","operatorId":"CH*IOY","status":status,"updatedAt":now,
 "nationalEvseCount":len(evses),"pricedEvseCount":len(rows),"unresolvedEvseCount":len(unresolved),
 "method":"Current Swiss national CH*IOY coordinates/power + official IONITY v3 location connector adhocPrice",
 "policy":payload["policy"],"productionSource":str(OUT)}
OUT.parent.mkdir(parents=True,exist_ok=True);FINAL.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2));print(json.dumps({"unresolved":unresolved[:100]},ensure_ascii=False,indent=2))
