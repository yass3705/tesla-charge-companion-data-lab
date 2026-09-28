#!/usr/bin/env python3
import gzip,json,math,time,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from datetime import datetime,timezone

STATIC="https://adhoc-bff.ionity.cloud/api/v1/location/static"
DETAIL="https://adhoc-bff.ionity.cloud/api/v3/location/{}"
NATIONAL="https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
HEADERS={"User-Agent":"IONITY/2.428.0 (Android; TeslaChargeCompanion validation)","Accept":"application/json",
"x-adhoc-platform":"ANDROID_V2","x-adhoc-app-feature-version":"v2.428.0","x-adhoc-device-country":"CH","x-adhoc-device-language":"de"}
def get(url,attempts=4):
    last=None
    for i in range(attempts):
        try:
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=35) as r:return json.loads(r.read().decode())
        except Exception as e:
            last=e; time.sleep(.7*(2**i))
    raise RuntimeError(f"{url}: {last}")
def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x:yield from walk(v)
def national_ids():
    req=urllib.request.Request(NATIONAL,headers={"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
    if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
    d=json.loads(raw.decode())
    out=set()
    for o in walk(d):
        for k,v in o.items():
            if isinstance(v,str) and "evse" in k.lower() and v.startswith("CH*IOY*E"):out.add(v)
    return out
def hyd(s):
    d=get(DETAIL.format(s["uuid"]))
    if d.get("cpoIdentifier")!="IONITY_CPO" or str(d.get("country","")).upper()!="CH":return None
    cs=[]
    for c in d.get("connectors") or []:
        p=c.get("adhocPrice") or {}
        if str(p.get("name","")).upper()!="IONITY DIRECT":continue
        try:a=float(p.get("amount"))
        except:continue
        if not a>0:continue
        cs.append({"sourceEvseId":str(c.get("sourceEvseId") or ""),"connectorUuid":c.get("uuid"),
                   "type":c.get("type"),"maxPowerW":c.get("maxPower"),
                   "amount":a,"currency":str(p.get("currency") or "").upper(),"unit":p.get("unit"),
                   "product":p.get("name")})
    return {"uuid":d.get("uuid"),"name":d.get("name"),"address":d.get("address"),"city":d.get("city"),
            "latitude":d.get("latitude"),"longitude":d.get("longitude"),"connectors":cs}
nat=national_ids(); static=get(STATIC); raw=static.get("locations") or []
ops=[x for x in raw if x.get("cpoIdentifier")=="IONITY_CPO"]
cands=[x for x in ops if 45.7 <= float(x.get("latitude") or -99) <= 47.9 and 5.8 <= float(x.get("longitude") or -99) <= 10.7]
locs=[]
with ThreadPoolExecutor(max_workers=12) as pool:
    futs=[pool.submit(hyd,x) for x in cands]
    for f in as_completed(futs):
        x=f.result()
        if x:locs.append(x)
by={}
for loc in locs:
    for c in loc["connectors"]:
        eid=c["sourceEvseId"]
        if eid.startswith("CH*IOY*E"):
            by.setdefault(eid,[]).append({"locationUuid":loc["uuid"],"locationName":loc["name"],"city":loc["city"],**c})
matched=sorted(nat & set(by));missing=sorted(nat-set(by));extra=sorted(set(by)-nat)
ambiguous={k:v for k,v in by.items() if k in nat and len({(x["amount"],x["currency"],x["unit"]) for x in v})>1}
status="complete" if len(matched)==len(nat) and not ambiguous else "partial"
payload={"schemaVersion":1,"country":"CH","cpo":"IONITY","operatorId":"CH*IOY","generatedAt":datetime.now(timezone.utc).isoformat(),
"source":{"static":STATIC,"detailTemplate":DETAIL,"requiredCpoIdentifier":"IONITY_CPO","tariffProduct":"IONITY DIRECT"},
"counts":{"nationalEvseCount":len(nat),"ionityChLocationCount":len(locs),"matchedEvseCount":len(matched),"missingEvseCount":len(missing),"extraIonityEvseCount":len(extra),"ambiguousEvseCount":len(ambiguous)},
"policy":"Exact current national EVSE-ID match only. IONITY DIRECT adhocPrice only; no subscriber/roaming tariff and no extrapolation.",
"missingEvseIds":missing,"extraEvseIds":extra,"ambiguous":ambiguous,"evseTariffs":{k:by[k] for k in matched},"locations":locs}
Path("data/switzerland").mkdir(parents=True,exist_ok=True);Path("docs").mkdir(exist_ok=True)
Path("data/switzerland/ionity-official-direct-tariffs.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
final={"schemaVersion":1,"country":"CH","cpo":"IONITY","operatorId":"CH*IOY","status":status,"updatedAt":payload["generatedAt"],
"nationalEvseCount":len(nat),"pricedEvseCount":len(matched),"unresolvedEvseCount":len(missing),"ambiguousEvseCount":len(ambiguous),
"method":"Current Swiss national CH*IOY scope + IONITY public v3 location connector adhocPrice (IONITY DIRECT)",
"policy":payload["policy"],"productionSource":"data/switzerland/ionity-official-direct-tariffs.json"}
Path("docs/switzerland-ionity-finalization-2026-09-28.json").write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(final,ensure_ascii=False,indent=2))
