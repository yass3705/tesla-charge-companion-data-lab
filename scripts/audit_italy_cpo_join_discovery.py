#!/usr/bin/env python3
"""Read-only diagnostic: inspect Italian CPO source identity and tariff field availability.

No tariff value is assumed to be a direct CPO price based on field names alone.
"""
import gzip, json, pathlib, collections, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = [
 "data/national/allego_direct_stations_italy_20260925.json.gz",
 "data/national/atlante_direct_stations_italy_latest.json.gz",
 "data/national/ewiva_pos_direct_italy_candidate.json.gz",
 "data/national/freetox_direct_stations_italy.json.gz",
 "data/national/ionity_direct_stations_italy.json.gz",
 "data/national/neogy_alperia_italy_v9_candidate.json.gz",
 "data/national/repower_italy_v9_candidate.json.gz",
]
ID_KEYS = {"evseid", "evse_id", "evseuid", "evse_uid", "uid"}
POWER_KEYS = {"powerkw", "maxpowerkw", "max_power_kw", "power", "max_electric_power"}
TARIFF_KEYS = {"tariff", "tariffs", "price", "pricing", "offers", "priceperkwh", "eurperkwh"}
LIMIT=1500000

def inspect(path):
    raw=path.read_bytes()
    payload=json.loads(gzip.decompress(raw) if path.suffix==".gz" else raw)
    seen=collections.Counter(); counts=collections.Counter(); examples=[]; identity_shapes=collections.defaultdict(collections.Counter); identity_examples={}; geo_fields=collections.Counter(); address_fields=collections.Counter(); geo_examples={}
    stack=[payload]
    while stack and counts["nodes"]<LIMIT:
        value=stack.pop()
        counts["nodes"]+=1
        if isinstance(value,dict):
            keys={str(k).lower() for k in value}
            for typ, fields in (("identity",ID_KEYS),("power",POWER_KEYS),("tariff_like",TARIFF_KEYS)):
                if keys & fields: counts[typ+"_objects"]+=1
            for k,v in value.items():
                kl=str(k).lower()
                if kl in ID_KEYS and isinstance(v,(str,int)) and len(examples)<5: examples.append(str(v)[:80])
                if kl in ("sourceevseid", "physicalreference", "uuid"):
                    identity_shapes[kl][type(v).__name__]+=1
                    if kl not in identity_examples:
                        identity_examples[kl]=repr(v)[:180]
                if kl in ("latitude","longitude","lat","lon","lng","coordinates","location","geometry","geo","position","gps"):
                    geo_fields[kl]+=1
                    if kl not in geo_examples: geo_examples[kl]=repr(v)[:220]
                if kl in ("address","street","streetname","city","postalcode","postcode","zip","formattedaddress","locality"):
                    address_fields[kl]+=1
                seen[kl]+=1
                if isinstance(v,(dict,list)):stack.append(v)
        elif isinstance(value,list):
            stack.extend(x for x in value if isinstance(x,(dict,list)))
    return {"bytes":len(raw),"topLevelType":type(payload).__name__,
      "nodesInspected":counts["nodes"],"truncated":bool(stack),
      "identityBearingObjects":counts["identity_objects"],"powerBearingObjects":counts["power_objects"],
      "tariffLikeObjects":counts["tariff_like_objects"],"sampleIdentityValues":examples,
      "presentIdentityFields":sorted(k for k in seen if k in ID_KEYS),
      "presentPowerFields":sorted(k for k in seen if k in POWER_KEYS),
      "presentTariffFields":sorted(k for k in seen if k in TARIFF_KEYS),
      "identityValueShapes":{k:dict(v) for k,v in identity_shapes.items()},
      "identityValueExamples":identity_examples,
      "geoFields":dict(geo_fields),"addressFields":dict(address_fields),
      "geoExamples":geo_examples}

def main():
    records=[]
    for name in SOURCES:
        path=ROOT/name
        if not path.is_file():records.append({"path":name,"exists":False});continue
        try: records.append({"path":name,"exists":True,**inspect(path)})
        except Exception as e:records.append({"path":name,"exists":True,"inspectionError":str(e)[:250]})
    report={"schemaVersion":1,"country":"IT","generatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "classification":"schema-discovery-not-tariff-join",
      "sources":records,"readyForProductionSwitch":False,
      "nextGates":["identify official CPO direct tariff versus roaming by source evidence",
                   "match station and EVSE identifiers exactly; unresolved mappings stay unpriced",
                   "validate connector Type2/CCS power and pricing conditions against runtime"]}
    path=ROOT/"reports/migration/italy-cpo-join-discovery.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
