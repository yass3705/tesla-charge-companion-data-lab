#!/usr/bin/env python3
from __future__ import annotations
import json,re,xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter,defaultdict

ROAD=Path("data/belgium/additional/road-2026-09-29.json")
INDIGO=Path("data/belgium/additional/indigo-2026-09-28.xml")
OUTD=Path("data/belgium/additional/canonical"); OUTD.mkdir(parents=True,exist_ok=True)
REPD=Path("reports/belgium"); REPD.mkdir(parents=True,exist_ok=True)

road=json.loads(ROAD.read_text())

def pick(d,*names):
    for n in names:
        if n in d and d[n] not in (None,"",[],{}): return d[n]
    return None

locations=[]
def walk(x):
    if isinstance(x,dict):
        low={str(k).lower():v for k,v in x.items()}
        evses=low.get("evses")
        if isinstance(evses,list) and any(k in low for k in ("coordinates","city","country","address")):
            locations.append(x)
        for v in x.values(): walk(v)
    elif isinstance(x,list):
        for v in x: walk(v)
walk(road)

road_rows=[]
operator_counts=Counter(); public_flags=Counter(); country_counts=Counter(); power_counts=Counter()
for loc in locations:
    low={str(k).lower():v for k,v in loc.items()}
    op=pick(low,"operator","cpo","network","party_id","partyid")
    if isinstance(op,dict): op=op.get("name") or op.get("id")
    op=str(op or "UNKNOWN")
    city=pick(low,"city")
    country=pick(low,"country","country_code")
    name=pick(low,"name")
    lid=pick(low,"id","location_id","locationid")
    access=pick(low,"access","access_type","parking_type","public")
    if isinstance(access,(str,bool,int,float)): public_flags[str(access)]+=1
    if country: country_counts[str(country)]+=1
    for ev in low.get("evses") or []:
        if not isinstance(ev,dict): continue
        eid=ev.get("evse_id") or ev.get("evseid") or ev.get("uid") or ev.get("id")
        conn=ev.get("connectors") or []
        maxw=[]
        for c in conn if isinstance(conn,list) else []:
            if not isinstance(c,dict): continue
            p=c.get("max_electric_power") or c.get("maxpowerw") or c.get("max_power") or c.get("power")
            if isinstance(p,(int,float)): maxw.append(p)
        if maxw: power_counts[str(max(maxw))]+=1
        road_rows.append({
          "source":"Road",
          "operator":op,"locationId":lid,"locationName":name,"city":city,"country":country,
          "access":access,"evseId":eid,"connectors":conn
        })
        operator_counts[op]+=1

(OUTD/"road-belgium-canonical-2026-09-29.json").write_text(json.dumps({
 "country":"BE","source":"Road","locationsDetected":len(locations),"evseRows":len(road_rows),"items":road_rows
},ensure_ascii=False,indent=2)+"\n")

# Indigo canonical
tree=ET.parse(INDIGO); root=tree.getroot()
def local(t): return t.split("}")[-1]
indigo_sites=[]
indigo_evses=0
for site in root.iter():
    if local(site.tag)!="energyInfrastructureSite": continue
    texts=defaultdict(list)
    for el in site.iter():
        if el.text and el.text.strip():
            texts[local(el.tag)].append(el.text.strip())
    ids=texts.get("externalIdentifier",[])
    rps=[]
    for rp in site.iter():
        if local(rp.tag)!="refillPoint": continue
        vals={}
        for el in rp.iter():
            if el.text and el.text.strip():
                vals.setdefault(local(el.tag),[]).append(el.text.strip())
        ext=(vals.get("externalIdentifier") or [None])[0]
        p=(vals.get("maxPowerAtSocket") or [None])[0]
        rps.append({"externalIdentifier":ext,"maxPowerAtSocket":p,"connectorType":(vals.get("connectorType") or [None])[0]})
    indigo_evses+=len(rps)
    indigo_sites.append({
      "source":"INDIGO",
      "name":(texts.get("name") or [None])[0],
      "city":(texts.get("city") or [None])[0],
      "postcode":(texts.get("postcode") or [None])[0],
      "countryCode":(texts.get("countryCode") or [None])[0],
      "operator":(texts.get("organisationName") or texts.get("operator") or [None])[0],
      "refillPoints":rps
    })
(OUTD/"indigo-belgium-canonical-2026-09-29.json").write_text(json.dumps({
 "country":"BE","source":"INDIGO","sites":len(indigo_sites),"evses":indigo_evses,"items":indigo_sites
},ensure_ascii=False,indent=2)+"\n")

report={
 "country":"BE","asOf":"2026-09-29","phase":"additional-inventory-integration",
 "road":{
   "locationsDetected":len(locations),"evseRows":len(road_rows),
   "operators":operator_counts.most_common(),
   "accessSignals":dict(public_flags),"countries":dict(country_counts)
 },
 "indigo":{"sites":len(indigo_sites),"evses":indigo_evses},
 "notes":[
   "Road and INDIGO are integrated as complementary inventory sources, not tariff sources.",
   "No pricing is inferred from operator names or power.",
   "Tariff resolution is performed separately per operator/source."
 ]
}
(REPD/"belgium-additional-inventory-integration-2026-09-29.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\\n")

manifest={
 "country":"BE","asOf":"2026-09-29","phase":"v9-source-consolidation",
 "inventorySources":[
   {"name":"Eco-Movement Belgium NAP","manifest":"data/belgium/nap-belgium-manifest.json","scope":"selected CPOs","locations":16873,"evses":70216},
   {"name":"Road","canonical":"data/belgium/additional/canonical/road-belgium-canonical-2026-09-29.json","locations":len(locations),"evses":len(road_rows)},
   {"name":"INDIGO","canonical":"data/belgium/additional/canonical/indigo-belgium-canonical-2026-09-29.json","sites":len(indigo_sites),"evses":indigo_evses}
 ],
 "tariffSources":[
   {"name":"Eco-Movement + exact official overlays","progress":"docs/belgium-cpo-progress-2026-09.json"},
   {"name":"Road public tariffs","overlay":"data/operator_direct/road_belgium_tariffs_2026-09-29.json","pricedEvses":7475,"sourceLimitedEvses":699},
   {"name":"INDIGO official Belgium tariff","overlay":"data/operator_direct/indigo_belgium_official_2026-09-29.json","pricedEvses":indigo_evses}
 ],
 "externalBlockedSources":[
   {"name":"EnergyVision","reason":"free API key required from myevplatform@energyvision.be"},
   {"name":"Monta","reason":"authenticated Public API application requires clientId/clientSecret"}
 ],
 "rules":[
   "Do not infer tariffs.",
   "Preserve source provenance.",
   "Deduplicate only on stable EVSE identifiers or explicit source identity evidence.",
   "Credential-gated sources remain blocked until legitimate credentials are supplied."
 ]
}
(REPD/"belgium-v9-source-manifest-2026-09-29.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\\n")
print(json.dumps(report,ensure_ascii=False,indent=2))
