#!/usr/bin/env python3
import gzip,json,collections,datetime
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def read(p):
 with gzip.open(root/p,"rt",encoding="utf-8") as f:return json.load(f)
static=read("data/national/france-irve-static-v9/all.json.gz")
dynamic=read("data/national/france-irve-dynamic-status-v9.json.gz")
pdc=set();stations={};marked=collections.defaultdict(list)
for row in static:
 ids={str(x) for cfg in row[8] for x in cfg[6]}
 pdc|=ids;stations[str(row[0])]=ids
for item in dynamic["records"]:marked[str(item["id_station_itinerance"])].append(item)
marked_ids={r["id_pdc_itinerance"] for r in dynamic["records"]}
stats={
 "dynamicGeneratedAt":dynamic.get("generatedAt"),
 "sourceRows":dynamic.get("sourceRows"),
 "matchedPdc":dynamic.get("matchedPdc"),
 "dynamicStateCounts":dynamic.get("states"),
 "explicitlyUnavailable":dynamic.get("displayExcludedPdc"),
 "staticPdc":len(pdc),
 "staticStations":len(stations),
 "negativeIdsNotPresentInStatic":len(marked_ids-pdc),
 "withoutDynamicState":len(pdc)-int(dynamic.get("matchedPdc") or 0),
 "definitelyAllKnownUnavailableStations":sum(bool(ids) and all(x in marked_ids for x in ids) for ids in stations.values()),
 "stationsWithAnyPdcNotMarkedUnavailable":sum(any(x not in marked_ids for x in ids) for ids in stations.values()),
 "stationsWithAnyPdcIndividuallyVerifiedEnService":None,
 "note":"Negative-only snapshot intentionally omits en_service IDs. Absence from negative records cannot prove en_service (may be absent from feed)."
}
print("IRVE_DYNAMIC_PROBE="+json.dumps(stats,ensure_ascii=False,separators=(',',':')))
