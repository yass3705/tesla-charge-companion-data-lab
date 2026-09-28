#!/usr/bin/env python3
import gzip,json,re,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
OFFICIAL="https://eniplenitude.com/mobilita-elettrica/tariffe-ricarica-auto-elettrica"
SRC=Path("data/switzerland/pln-direct-tariffs.json")
OUT=Path("data/switzerland/plenitude-official-direct-tariffs.json")
FINAL=Path("docs/switzerland-plenitude-finalization-2026-09-28.json")
UA={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}

def getj(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
    if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))

nat=getj(NATIONAL)
atlas=json.loads(SRC.read_text(encoding="utf-8"))

# Build exact current national CH*PLN scope.
national_ids=set()
records={}
def walk(o):
    if isinstance(o,dict):
        # Direct EVSE IDs on the current object are typically the narrowest useful national record.
        direct=[]
        for k,v in o.items():
            if isinstance(v,str) and v.startswith("CH*PLN*E"):
                direct.append(v)
        for eid in direct:
            national_ids.add(eid)
            records.setdefault(eid,[]).append(o)
        for v in o.values(): walk(v)
    elif isinstance(o,list):
        for v in o: walk(v)
walk(nat)

# Exact power/type mapping already observed by Chargeprice for currently indexed stations.
mapped={}
for st in atlas.get("stations",[]):
    for cp in st.get("chargePoints",[]):
        c=cp.get("chargePoint") or {}
        for eid in c.get("evse_ids") or []:
            if eid.startswith("CH*PLN*E"):
                mapped[eid]={
                    "powerKw":c.get("power"),
                    "energyType":(c.get("energy_type") or "").lower() or None,
                    "plug":c.get("plug"),
                    "stationName":st.get("name"),
                    "address":st.get("address"),
                    "classificationSource":"Chargeprice station metadata"
                }

def flatten(x):
    vals=[]
    if isinstance(x,dict):
        for k,v in x.items():
            vals.append((str(k),v))
            vals.extend(flatten(v))
    elif isinstance(x,list):
        for v in x: vals.extend(flatten(v))
    return vals

def infer_from_national(eid):
    objs=records.get(eid,[])
    powers=[]; texts=[]
    for o in objs:
        for k,v in flatten(o):
            lk=k.lower()
            if isinstance(v,(int,float)) and not isinstance(v,bool) and any(t in lk for t in ("power","kw","capacity")):
                n=float(v)
                if n>1000 and n<1000000: n=n/1000.0
                if 1 <= n <= 1000: powers.append(n)
            if isinstance(v,str):
                texts.append(v.lower())
    p=max(powers) if powers else None
    blob=" ".join(texts)
    et=None; plug=None
    if any(x in blob for x in ("chademo","combo 2","combo2","ccs")):
        et="dc"; plug="ccs/chademo"
    elif "type 2" in blob or "type2" in blob:
        et="ac"; plug="type2"
    return {"powerKw":p,"energyType":et,"plug":plug,"classificationSource":"Swiss national OICP metadata"}

def tariff(meta):
    et=meta.get("energyType"); p=meta.get("powerKw")
    if et=="ac":
        return {"pricePerKwh":0.50,"category":"Quick","currency":"CHF"}
    if et=="dc" and isinstance(p,(int,float)):
        if p < 75:
            return {"pricePerKwh":0.65,"category":"Fast","currency":"CHF"}
        if p > 75:
            return {"pricePerKwh":0.70,"category":"Fast+/Ultra Fast","currency":"CHF"}
        return None
    return None

rows=[]; unresolved=[]
for eid in sorted(national_ids):
    meta=mapped.get(eid) or infer_from_national(eid)
    t=tariff(meta)
    if t is None:
        unresolved.append({"evseId":eid,"metadata":meta,"reason":"power_or_energy_type_not_unambiguously_classified"})
        continue
    rows.append({"evseId":eid,**meta,**t,
                 "idleFeePolicy":"Official Plenitude page states 60 min post-charge grace; extra-stay fee applies afterward and is converted to local currency where non-EUR. Exact CHF idle fee intentionally not guessed.",
                 "source":OFFICIAL})

now=datetime.now(timezone.utc).isoformat()
status="complete" if national_ids and len(rows)==len(national_ids) else "partial"
payload={
 "schemaVersion":1,"country":"CH","cpo":"Plenitude On The Road","operatorId":"CH*PLN",
 "generatedAt":now,
 "sources":{"national":NATIONAL,"officialTariff":OFFICIAL,"stationMetadata":str(SRC)},
 "tariffRules":{"Quick_AC_up_to_22kW":{"CHF_per_kWh":0.50},"Fast_DC_below_75kW":{"CHF_per_kWh":0.65},"FastPlus_UltraFast_DC_above_75kW":{"CHF_per_kWh":0.70},
                 "boundary75kW":"fail_closed_due_official_wording_overlap"},
 "counts":{"nationalEvseCount":len(national_ids),"pricedEvseCount":len(rows),"unresolvedEvseCount":len(unresolved),"atlasMetadataEvseCount":len(set(mapped)&national_ids)},
 "policy":"Apply only current official Switzerland Plenitude On The Road energy tariffs by connector category. No roaming tariff, no station extrapolation, no guessed idle-fee conversion.",
 "evses":rows,"unresolved":unresolved
}
final={"schemaVersion":1,"country":"CH","cpo":"Plenitude On The Road","operatorId":"CH*PLN","status":status,"updatedAt":now,**payload["counts"],
       "method":"Current national CH*PLN scope + official Plenitude Switzerland Pay Per Use tariff tiers, with exact connector power/type classification",
       "policy":payload["policy"],"productionSource":str(OUT)}
OUT.parent.mkdir(parents=True,exist_ok=True);FINAL.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
if unresolved:
    print(json.dumps({"unresolvedSample":unresolved[:30]},ensure_ascii=False,indent=2))
