#!/usr/bin/env python3
"""Classify 738 GFX no-price connectors against TotalEnergies own public API.

No payment or session calls, no generalized pricing; reuse existing CPO
read-only inventory, exact EVSE+connector identity only.
"""
from __future__ import annotations
import collections,csv,datetime as dt,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from integrate_total_nl_chargingservices import fetch_config,fetch_inventory,fixed_price
GAPS=ROOT/"reports/netherlands/dotnl-active-type2-ccs-unpriced-connectors-latest.csv"
OUT=ROOT/"reports/netherlands/nl-gfx-totalenergies-738-missing-direct-price-diagnostic-latest.json"
DETAIL=ROOT/"reports/netherlands/nl-gfx-totalenergies-738-missing-direct-price-diagnostic-latest.csv"

def main():
    with GAPS.open(newline="",encoding="utf8") as f:
        rows=[x for x in csv.DictReader(f) if x["partyId"]=="GFX" and x["gapType"]=="NO_TARIFF_IN_DOTNL"]
    assert len(rows)==738,len(rows)
    base,key,js=fetch_config()
    inventory=fetch_inventory(base,key)
    byid=collections.defaultdict(list)
    for loc in inventory:
        if (loc.get("address") or {}).get("country")!="NL" or loc.get("serviceOperatorId")!="TotalEnergies":
            continue
        for spot in loc.get("chargingSpots") or []:
            for evse in spot.get("evses") or []:
                for c in evse.get("connectors") or []:
                    products=evse.get("products") or []
                    pub=[]
                    for p in products:
                        px=fixed_price(p) if p.get("type")=="CHARGE" else None
                        pub.append({"type":str(p.get("type") or ""), "product":str(p.get("name") or ""),
                            "subEmspPresent":bool(p.get("subEmsp")),
                            "fixedGrossEurPerKwh":px})
                    byid[(str(evse.get("emi3") or ""),str(c.get("id") or ""))].append({
                       "operatorSourceLocationId":str(loc.get("id") or ""),
                       "sourceName":str(loc.get("name") or ""),
                       "products":pub})
    counts=collections.Counter();examples=collections.defaultdict(list);detail=[]
    for r in rows:
        k=(r["evseId"],r["connectorId"])
        refs=byid.get(k,[])
        if not refs:
            cls="not_in_operator_portal_by_exact_identity"
        elif len(refs)>1:
            cls="multiple_exact_operator_portal_records"
        else:
            products=refs[0]["products"]
            guest=[p for p in products if p["type"]=="CHARGE" and not p["subEmspPresent"] and "PAYG" in p["product"].upper()]
            if len(guest)==1 and guest[0]["fixedGrossEurPerKwh"] is not None:
                cls="exact_guest_fixed_tariff_exists_not_integrated"
            elif len(guest)==1:
                cls="exact_guest_dynamic_or_unparseable_tariff"
            elif guest:
                cls="multiple_guest_payg_products"
            elif products:
                cls="no_guest_payg_product_in_official_portal"
            else:
                cls="no_charge_product_in_official_portal"
        counts[cls]+=1
        data={"stationId":r["stationId"],"evseId":r["evseId"],"connectorId":r["connectorId"],
            "tccConnectorClass":r["tccConnectorClass"],"powerKw":r["powerKw"],
            "evseStatus":r["evseStatus"],"stationName":r["stationName"],
            "reason":cls,"officialPortalLocationId":refs[0]["operatorSourceLocationId"] if len(refs)==1 else "",
            "operatorProducts":json.dumps(refs[0]["products"],ensure_ascii=False,separators=(",",":")) if len(refs)==1 else ""}
        detail.append(data)
        if len(examples[cls])<6:examples[cls].append(data)
    assert sum(counts.values())==738
    with DETAIL.open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(detail[0]));w.writeheader();w.writerows(detail)
    rep={"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
       "nationalSource":"DOT-NL GFX missing, exact source snapshot 2026-10-11",
       "operator":"TotalEnergies","partyIdsFromBenelux":["NL*PCB","NL*TCB"],
       "source":"https://chargingservices.totalenergies.com/fr/find-a-charger?countryCode=NL",
       "officialPortalConnectorRecords":sum(len(v) for v in byid.values()),
       "exactMissingGfxConnectors":len(detail),"byCause":dict(counts),
       "examplesByCause":dict(examples),
       "noTariffPromoted":True,"noEmspPrices":True,
       "detailCsv":"reports/netherlands/nl-gfx-totalenergies-738-missing-direct-price-diagnostic-latest.csv",
       "guardrails":"No pricing inference from same operator, no CPO reference overwrite, no non-PAYG guest product substitution"}
    OUT.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"officialRecords":rep["officialPortalConnectorRecords"],"byCause":rep["byCause"]},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
