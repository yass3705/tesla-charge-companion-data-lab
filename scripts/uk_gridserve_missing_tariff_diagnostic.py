#!/usr/bin/env python3
import gzip, json, collections, os

LOCS="data/national/uk_gridserve_pcpr_locations.json.gz"
TARS="data/national/uk_gridserve_pcpr_tariffs.json.gz"
OUT="reports/uk/gridserve-missing-tariff-diagnostic-latest.json"

locdoc=json.load(gzip.open(LOCS,"rt",encoding="utf-8"))
tardoc=json.load(gzip.open(TARS,"rt",encoding="utf-8"))
locations=locdoc["locations"]
tariffs=tardoc["tariffs"]
known={str(t.get("id")):t for t in tariffs if isinstance(t,dict) and t.get("id") is not None}
missing_ids={"A0-GBP","GS1","GS3","GS9"}

diag={mid:{
    "connectors":0,"evses":set(),"locations":set(),"standards":collections.Counter(),
    "powerTypes":collections.Counter(),"powersW":collections.Counter(),"statuses":collections.Counter(),
    "samples":[]
} for mid in missing_ids}

all_refs=collections.Counter()
for loc in locations:
    lname=loc.get("name"); lid=loc.get("id"); city=loc.get("city"); address=loc.get("address")
    for evse in loc.get("evses") or []:
        uid=evse.get("uid"); status=evse.get("status")
        for conn in evse.get("connectors") or []:
            tids=conn.get("tariff_ids") or []
            if not isinstance(tids,list): tids=[tids]
            tids=[str(x) for x in tids if x is not None]
            for tid in tids: all_refs[tid]+=1
            for tid in tids:
                if tid not in missing_ids: continue
                d=diag[tid]
                d["connectors"]+=1; d["evses"].add(uid); d["locations"].add(lid)
                d["standards"][str(conn.get("standard"))]+=1
                d["powerTypes"][str(conn.get("power_type"))]+=1
                d["powersW"][str(conn.get("max_electric_power"))]+=1
                d["statuses"][str(status)]+=1
                if len(d["samples"])<25:
                    d["samples"].append({
                        "locationId":lid,"locationName":lname,"city":city,"address":address,
                        "evseUid":uid,"evseStatus":status,"connectorId":conn.get("id"),
                        "standard":conn.get("standard"),"powerType":conn.get("power_type"),
                        "maxElectricPower":conn.get("max_electric_power"),"tariffIds":tids,
                        "termsAndConditions":conn.get("terms_and_conditions")
                    })

def conv(d):
    return {
        "connectors":d["connectors"],"evses":len(d["evses"]),"locations":len(d["locations"]),
        "standards":dict(d["standards"]),"powerTypes":dict(d["powerTypes"]),
        "powersW":dict(d["powersW"]),"statuses":dict(d["statuses"]),"samples":d["samples"]
    }

out={
    "provider":"GRIDSERVE","missingTariffIds":sorted(missing_ids),
    "knownTariffIds":sorted(known.keys()),
    "referenceCountsAll":dict(all_refs),
    "missingDetails":{k:conv(v) for k,v in sorted(diag.items())}
}
os.makedirs(os.path.dirname(OUT),exist_ok=True)
with open(OUT,"w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=2); f.write("\n")
print(json.dumps({
    k:{"connectors":v["connectors"],"evses":len(v["evses"]),"locations":len(v["locations"]),
       "powersW":dict(v["powersW"]),"standards":dict(v["standards"])}
    for k,v in sorted(diag.items())
},indent=2))
