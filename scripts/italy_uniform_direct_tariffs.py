#!/usr/bin/env python3
"""Build exact-party Italy direct-tariff candidates for CPOs with network-wide pricing.

No roaming price is promoted as CPO direct. Rules below are supported by current
first-party tariff surfaces checked on 2026-09-05. Unknown connector/power cases fail closed.
"""
from __future__ import annotations

import argparse, gzip, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RULES = {
    "ENX": {"operator":"Enel X Way Italia","source":"https://www.enel.it/it-it/mobilita-elettrica/tariffe-abbonamenti"},
    "ONS": {"operator":"On Charge","source":"https://onmobility.oncharge.it/ricarica"},
    "IPE": {"operator":"IPlanet","source":"https://iplanet.eu/tariffe/"},
    "FWY": {"operator":"FastWay","source":"https://www.fastway.energy/guida-alla-ricarica/"},
    "ENH": {"operator":"Enerhub","source":"https://enerhub.it/ricarica/"},
    "ENB": {"operator":"R-ev / Enerbroker","source":"https://www.r-ev.it/termini-di-utilizzo-abbonamenti/"},
}
CHECKED = "2026-09-05"


def now_iso(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def load(path):
    p=Path(path)
    if p.suffix==".gz":
        with gzip.open(p,"rt",encoding="utf-8") as f:return json.load(f)
    return json.loads(p.read_text(encoding="utf-8"))

def kind(e):
    types={str(c.get("powerType") or "").upper() for c in (e.get("connectors") or [])}
    if any(x.startswith("DC") for x in types): return "DC"
    if any(x.startswith("AC") for x in types): return "AC"
    return None

def flat(price, cls, **extra):
    x={"pricingType":"flat","currency":"EUR","unit":"kWh","energyEurPerKwh":price,"tariffClass":cls,"rankable":True}
    x.update(extra); return x

def tariff(e):
    p=e.get("partyId"); k=kind(e)
    try: power=float(e.get("maxPowerKw")) if e.get("maxPowerKw") is not None else None
    except Exception: power=None
    if p=="ENX":
        if k=="AC" and power is not None and power<=43:
            return {"pricingType":"time_band","currency":"EUR","unit":"kWh","tariffClass":"AC","rankable":True,"bands":[{"days":"all","from":"07:00","through":"20:59","energyEurPerKwh":0.67},{"days":"all","from":"21:00","through":"06:59","energyEurPerKwh":0.58}]}
        if k=="DC" and power is not None and power<100:
            return {"pricingType":"time_band","currency":"EUR","unit":"kWh","tariffClass":"DC","rankable":True,"bands":[{"days":"all","from":"07:00","through":"20:59","energyEurPerKwh":0.75},{"days":"all","from":"21:00","through":"06:59","energyEurPerKwh":0.64}]}
        if k=="DC" and power is not None and power>=100:
            return flat(0.86,"HPC",note="Post-2026-07-31 standard price; expired HPC promotional values are not used")
    elif p=="ONS":
        if k=="AC" and power is not None and power<=22.5:return flat(0.65,"AC_QUICK")
        if k=="DC" and power is not None and power<=50.5:return flat(0.85,"DC_FAST")
        if k=="DC" and power is not None and power<=350.5:return flat(0.95,"DC_ULTRAFAST")
    elif p=="IPE":
        if k=="AC" and power is not None and power<=22.5:return flat(0.60,"AC",paymentChannel="IPlanet_app")
        if k=="DC":return flat(0.74,"DC",paymentChannel="IPlanet_app",alternateDirectTariffs=[{"paymentChannel":"POS","energyEurPerKwh":0.79,"currency":"EUR","unit":"kWh"}])
    elif p=="FWY":
        if k=="AC":return flat(0.68,"AC_TYPE2")
        if k=="DC":return flat(0.88,"DC_CCS2")
    elif p=="ENH":
        if k=="AC" and power is not None and power<=22.5:return flat(0.60,"AC",paymentChannel="Enerapp",alternateDirectTariffs=[{"paymentChannel":"guest","energyEurPerKwh":0.65,"currency":"EUR","unit":"kWh"}])
        if k=="DC" and power is not None and power<=400.5:return flat(0.79,"DC",paymentChannel="Enerapp",alternateDirectTariffs=[{"paymentChannel":"guest","energyEurPerKwh":0.95,"currency":"EUR","unit":"kWh"}])
    elif p=="ENB":
        if k=="AC":return flat(0.65,"AC",paymentChannel="R-ev_wallet")
        if k=="DC" and power is not None and power<=150:return flat(0.85,"DC",paymentChannel="R-ev_wallet")
        if k=="DC" and power is not None and power>150:return flat(0.89,"HPC",paymentChannel="R-ev_wallet")
    return None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--output",required=True); ap.add_argument("--report",required=True); a=ap.parse_args()
    src=load(a.input); rows=[]; unresolved=[]; per={}
    for party,rule in RULES.items():
        evses=[e for e in src.get("evses",[]) if e.get("partyId")==party]; stations=set(); classes=Counter(); rank=0
        for e in evses:
            t=tariff(e); stations.add(e.get("stationId"))
            if t: rank+=1; classes[t["tariffClass"]]+=1
            else: classes["UNRESOLVED"]+=1; unresolved.append({"partyId":party,"evseId":e.get("evseId"),"maxPowerKw":e.get("maxPowerKw")})
            rows.append({"evseId":e.get("evseId"),"stationId":e.get("stationId"),"partyId":party,"operator":e.get("operator"),"maxPowerKw":e.get("maxPowerKw"),"connectors":e.get("connectors"),"operationalState":e.get("operationalState"),"sourceStatus":e.get("sourceStatus"),"directTariff":t,"rankableDirectTariff":bool(t),"source":rule["source"],"sourceCheckedAt":CHECKED})
        per[party]={"operator":rule["operator"],"evse":len(evses),"stations":len(stations),"rankableDirectEvse":rank,"classes":dict(classes)}
    payload={"schemaVersion":1,"dataset":"italy-v9-uniform-direct-tariffs-candidate","generatedAt":now_iso(),"country":"IT","policy":{"priority":"network_wide_predefined_direct_tariff","exactPartyIdScope":True,"failClosed":True,"atlanteExcluded":True},"rules":RULES,"counts":{"operators":len(RULES),"evse":len(rows),"stations":sum(v["stations"] for v in per.values()),"rankableDirectEvse":sum(v["rankableDirectEvse"] for v in per.values()),"unresolvedEvse":len(unresolved),"byOperator":per},"unresolved":unresolved,"evses":rows}
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(gzip.compress((json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n").encode(),compresslevel=9,mtime=0))
    report={k:v for k,v in payload.items() if k!="evses"}; rp=Path(a.report); rp.parent.mkdir(parents=True,exist_ok=True); rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    assert not unresolved, unresolved[:5]
    print(json.dumps(payload["counts"],ensure_ascii=False,indent=2))

if __name__=="__main__":main()
