#!/usr/bin/env python3
import json,re,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path

BASE="https://prod-driver-api.freshmile.com/charge/api/v2"
UA="Tesla-Charge-Companion-Homecourt-Freshmile/1.0"
OUT=Path("reports/france/homecourt_freshmile_exact_tariffs.json")
TARGETS=[
  {"legacyStationId":"_SkQzDtCh9kIqIcaqIsA2dQoeqh9uxYRPqMC_FM","name":"Gare Homécourt","addressNeedle":"avenue de la république","ref":"NFZ3TXLMC0"},
  {"legacyStationId":"wpf9KQt0D5l-E5CKBmfwFUvLTAW2ysjM3DMf7V8","name":"Parking college Amilcar","addressNeedle":"esplanade samuel paty","ref":"IB0HMQS0YP"},
  {"legacyStationId":"P30tN3hWm94cZ-gfY6cyL-afzjptQL4WP8_MHpC","name":"Parking Mairie Homécourt","addressNeedle":"georges clémenceau","ref":"Z4Q5I7BYZR"}
]
NUM=r"([0-9]+(?:[.,][0-9]+)?)"

def req(ref):
    url=BASE+"/locations?"+urllib.parse.urlencode({"filter[ref]":ref})
    r=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/plain,*/*"})
    with urllib.request.urlopen(r,timeout=30) as resp:
        return url,resp.status,json.loads(resp.read().decode("utf-8"))

def locs(payload):
    if isinstance(payload,dict) and isinstance(payload.get("data"),list): return payload["data"]
    if isinstance(payload,list): return payload
    return []

def norm(s):
    return re.sub(r"\s+"," ",str(s or "").lower().replace("\u00a0"," ")).strip()

def parse_desc(desc):
    t=" ".join(str(desc or "").replace("\r","\n").split())
    out={"rawDescription":desc}
    for pat in [
      rf"(?:€|EUR)?\s*{NUM}\s*(?:€|EUR)?\s*(?:/|per)\s*(?:started\s*)?kwh",
      rf"{NUM}\s*(?:€|EUR)\s*(?:/|per)\s*(?:started\s*)?kwh"
    ]:
      m=re.search(pat,t,re.I)
      if m:
        out["energyEurPerKwh"]=float(m.group(1).replace(",","."))
        break
    for pat in [
      rf"(?:€|EUR)?\s*{NUM}\s*(?:€|EUR)?\s*(?:/|per)\s*(?:started\s*)?(?:min|minute)",
      rf"{NUM}\s*(?:€|EUR)\s*(?:/|per)\s*(?:started\s*)?(?:min|minute)"
    ]:
      m=re.search(pat,t,re.I)
      if m:
        out["timeEurPerMinute"]=float(m.group(1).replace(",","."))
        break
    return out

rows=[]
for target in TARGETS:
    url,status,payload=req(target["ref"])
    candidates=locs(payload)
    exact=[x for x in candidates if str(x.get("ref") or "").upper()==target["ref"]]
    if len(exact)!=1:
        rows.append({**target,"status":"fail_closed","reason":f"expected one exact location, got {len(exact)}","url":url})
        continue
    loc=exact[0]
    address=norm(loc.get("address"))
    name=norm(loc.get("name"))
    if target["addressNeedle"] not in address and target["addressNeedle"] not in name:
        rows.append({**target,"status":"fail_closed","reason":"exact ref returned but address/name identity check failed","resolvedName":loc.get("name"),"resolvedAddress":loc.get("address"),"url":url})
        continue
    tariffs=[]
    evses=[]
    for evse in loc.get("evses") or []:
        eout={"id":evse.get("id"),"customRef":evse.get("custom_ref"),"status":evse.get("status"),"tariffs":[]}
        seen=set()
        for conn in evse.get("connectors") or []:
            tariff=conn.get("tariff") if isinstance(conn,dict) else None
            if not isinstance(tariff,dict): continue
            tid=str(tariff.get("id") or tariff.get("custom_ref") or tariff.get("description") or "")
            if tid in seen: continue
            seen.add(tid)
            parsed=parse_desc(tariff.get("description"))
            tout={
              "tariffId":tariff.get("id"),
              "tariffRef":tariff.get("custom_ref") or tariff.get("origin_ref"),
              "name":tariff.get("name"),
              "currency":tariff.get("currency"),
              "isFree":bool(tariff.get("is_free")),
              "description":tariff.get("description"),
              "parsed":parsed,
              "connectorPowerKw":conn.get("power"),
              "connectorStandard":conn.get("standard")
            }
            eout["tariffs"].append(tout); tariffs.append(tout)
        evses.append(eout)
    energy=sorted({t["parsed"].get("energyEurPerKwh") for t in tariffs if t["currency"]=="EUR" and t["parsed"].get("energyEurPerKwh") is not None and not t["isFree"]})
    validated=(len(energy)==1)
    rows.append({
      **target,"status":"validated_exact" if validated else "fail_closed",
      "url":url,"resolvedName":loc.get("name"),"resolvedAddress":loc.get("address"),
      "locationId":loc.get("id"),"energyPricesEurPerKwh":energy,"evses":evses,
      "reason":None if validated else "no unique exact EUR/kWh tariff across exact-location EVSEs"
    })

payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"source":"Freshmile public driver API exact ref","rows":rows}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False,indent=2))
if any(x["status"]!="validated_exact" for x in rows): raise SystemExit(2)
