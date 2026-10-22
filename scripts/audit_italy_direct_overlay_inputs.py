#!/usr/bin/env python3
"""Inventory Italy direct-CPO overlay candidates without inventing EVSE matches or tariffs."""
import gzip, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
INPUTS=[
"data/national/allego_direct_stations_italy_20260925.json.gz",
"data/national/atlante_direct_stations_italy_latest.json.gz",
"data/national/ewiva_pos_direct_italy_candidate.json.gz",
"data/national/freetox_direct_stations_italy.json.gz",
"data/national/ionity_direct_stations_italy.json.gz",
"data/national/neogy_alperia_italy_v9_candidate.json.gz",
"data/national/repower_italy_v9_candidate.json.gz",
]
def summary(path):
    raw=path.read_bytes()
    data=json.loads(gzip.decompress(raw) if path.suffix==".gz" else raw)
    return {"source":str(path.relative_to(ROOT)),"bytes":len(raw),"topLevelType":type(data).__name__,
      "topLevelKeys":sorted(data.keys())[:30] if isinstance(data,dict) else [],
      "listLength":len(data) if isinstance(data,list) else None,
      "requiresSchemaSpecificEvseMatching":True,"publishedOfferCount":None}
def main():
    records=[summary(ROOT/x) for x in INPUTS]
    result={"country":"IT","mode":"read-only-overlay-inventory","sources":records,
       "matchingPolicy":"Exact EVSE ID and connector power; no station-only inferred tariff",
       "unmatchedPolicy":"No CPO direct price available; preserve station and EVSE",
       "coverageCertified":False,"readyForProductionSwitch":False}
    out=ROOT/"reports/migration/italy-direct-overlay-inputs.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
