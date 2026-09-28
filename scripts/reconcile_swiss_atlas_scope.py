#!/usr/bin/env python3
import argparse,gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
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

ap=argparse.ArgumentParser()
ap.add_argument("--operator",required=True);ap.add_argument("--slug",required=True);ap.add_argument("--name",required=True)
args=ap.parse_args()
data_path=Path(f"data/switzerland/{args.slug}-direct-tariffs.json")
x=json.loads(data_path.read_text(encoding="utf-8"))
nat=getj(NATIONAL); national=set()
for d in walk(nat):
    for k,v in d.items():
        if isinstance(v,str) and "evse" in k.lower() and v.startswith(args.operator+"*E"): national.add(v)

atlas_all=set(); atlas_priced=set()
for s in x.get("stations",[]):
    atlas_all.update(s.get("evseIds") or [])
    for cp in s.get("chargePoints") or []:
        if cp.get("directTariffs"):
            atlas_priced.update((cp.get("chargePoint") or {}).get("evse_ids") or [])
matched=sorted(national & atlas_all); priced=sorted(national & atlas_priced)
missing_from_atlas=sorted(national-atlas_all); unpriced=sorted(national-atlas_priced)
status="complete" if national and not unpriced else "partial"
now=datetime.now(timezone.utc).isoformat()
doc={"schemaVersion":1,"country":"CH","cpo":args.name,"operatorId":args.operator,"status":status,"updatedAt":now,
 "nationalEvseCount":len(national),"atlasEvseCount":len(atlas_all),"matchedNationalEvseCount":len(matched),
 "pricedNationalEvseCount":len(priced),"missingFromAtlasCount":len(missing_from_atlas),"unpricedNationalEvseCount":len(unpriced),
 "missingFromAtlasEvseIds":missing_from_atlas,"unpricedNationalEvseIds":unpriced,
 "method":"Exact EVSE-ID reconciliation of Swiss national OICP scope against direct-only Chargeprice atlas output",
 "policy":"National EVSE scope is canonical. Atlas extras are ignored. No extrapolation.",
 "productionSource":str(data_path)}
Path("docs").mkdir(exist_ok=True)
Path(f"docs/switzerland-{args.slug}-scope-reconciliation-2026-09-28.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(doc,ensure_ascii=False,indent=2))
