#!/usr/bin/env python3
import gzip,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone

NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
SOURCE="https://saascharge.com/wp-content/uploads/2025/10/Gireve_Price_list_10092025.pdf"
OUT=Path("data/switzerland/saascharge-official-direct-tariffs.json")
FINAL=Path("docs/switzerland-saascharge-finalization-2026-09-28.json")

req=urllib.request.Request(NATIONAL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
if raw[:2]==b"\x1f\x8b": raw=gzip.decompress(raw)
j=json.loads(raw.decode("utf-8"))

rows=[]
def walk(x,anc=()):
    if isinstance(x,dict):
        ev=None
        for k,v in x.items():
            if isinstance(v,str) and "evse" in k.lower() and v.startswith("CH*SCH*E"):
                ev=v
        if ev:
            rows.append((ev,x,anc))
        for v in x.values(): walk(v,anc+(x,))
    elif isinstance(x,list):
        for v in x: walk(v,anc)
walk(j)

def flatten_num(obj):
    vals=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            lk=str(k).lower()
            if isinstance(v,(int,float)) and not isinstance(v,bool) and any(t in lk for t in ("power","kw","capacity")):
                n=float(v)
                if n>1000 and n<1000000:n=n/1000
                if 0<n<=1000: vals.append(n)
            vals+=flatten_num(v)
    elif isinstance(obj,list):
        for v in obj: vals+=flatten_num(v)
    return vals

def flatten_text(obj):
    out=[]
    if isinstance(obj,dict):
        for v in obj.values():
            if isinstance(v,str): out.append(v.lower())
            else: out+=flatten_text(v)
    elif isinstance(obj,list):
        for v in obj: out+=flatten_text(v)
    return out

priced=[]; unresolved=[]
for ev,obj,anc in sorted(rows,key=lambda x:x[0]):
    powers=flatten_num(obj)
    power=max(powers) if powers else None
    text=" ".join(flatten_text(obj))
    et=None
    if "dc" in text or "ccs" in text or "chademo" in text: et="dc"
    if ("ac_3_phase" in text or "type 2" in text or "type2" in text) and et is None: et="ac"
    price=None; minute=None; category=None
    if et=="ac" and power is not None and 0 < power <= 22:
        price=0.50; minute=0.05; category="AC_CH_Max_AC"
    elif et=="dc" and power is not None and 23 <= power <= 49:
        price=0.70; minute=0.0; category="DC_CH_Max_DC"
    if price is None:
        unresolved.append({"evseId":ev,"powerKw":power,"energyType":et,"reason":"outside_or_unclassified_official_saascharge_ch_tariff_band"})
    else:
        priced.append({"evseId":ev,"powerKw":power,"energyType":et,"pricePerKwh":price,"pricePerMinute":minute,"currency":"CHF","tariffCategory":category,"source":SOURCE})

now=datetime.now(timezone.utc).isoformat()
payload={"schemaVersion":1,"country":"CH","cpo":"Saascharge","operatorId":"CH*SCH","generatedAt":now,
"source":SOURCE,
"officialSwissTariffRules":{"AC_CH_Max_AC":{"powerKw":"0-22","pricePerKwh":0.50,"pricePerMinute":0.05,"currency":"CHF"},"DC_CH_Max_DC":{"powerKw":"23-49","pricePerKwh":0.70,"pricePerMinute":0.0,"currency":"CHF"}},
"counts":{"nationalEvseCount":len(rows),"pricedEvseCount":len(priced),"unresolvedEvseCount":len(unresolved)},
"policy":"Apply only published Saascharge Switzerland Gireve price bands when the current national EVSE power/type fits exactly. No extrapolation outside published bands.",
"evses":priced,"unresolved":unresolved}
OUT.parent.mkdir(parents=True,exist_ok=True); FINAL.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
final={"schemaVersion":1,"country":"CH","cpo":"Saascharge","operatorId":"CH*SCH","status":"complete" if rows and not unresolved else "partial",
"updatedAt":now,**payload["counts"],"method":"Current national CH*SCH scope + Saascharge published Switzerland Gireve tariff bands by exact EVSE power/type",
"policy":payload["policy"],"productionSource":str(OUT)}
FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
if unresolved: print(json.dumps({"unresolvedSample":unresolved[:50]},ensure_ascii=False,indent=2))
