#!/usr/bin/env python3
"""Non-published EnergyVision ad-hoc simple-kWh tariff proof candidates.

A station rate is NOT promoted to PDC unless individually certified. Monetary
examples are independent arithmetic only, not billable V9 prices.
"""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import gzip
import json
from pathlib import Path

ACTIVE = {"available", "charging"}

def amount(value):
    try:
        d = Decimal(str(value))
        return d if d.is_finite() and d >= 0 else None
    except (TypeError, ValueError, InvalidOperation):
        return None

def simple_rate(rate):
    if rate.get("ratePolicy") != "adHoc" or rate.get("currency") != "EUR":
        return None
    prices = rate.get("priceComponents") or []
    if len(prices) != 1:
        return None
    comp = prices[0]
    if comp.get("priceType") != "pricePerKWh" or str(comp.get("taxIncluded")).lower() != "true":
        return None
    if amount(comp.get("taxRateSource")) != Decimal("21"):
        return None
    if any(
        any(k in item.get("path","") for k in
            ("timeBasedApplicability", "overallPeriod", "energyBasedApplicability"))
        for item in comp.get("rawApplicabilityLeaves") or []
    ):
        return None
    return amount(comp.get("amountSource"))

def candidates(stage):
    if stage.get("provider") != "EnergyVision" or stage.get("country") != "BE" or stage.get("v9PublicationReady") is not False:
        raise ValueError("Only unpublished EnergyVision staging supported")
    sha = stage.get("sourceStatic",{}).get("sha256")
    if not isinstance(sha,str) or len(sha) != 64:
        raise ValueError("Missing source provenance")
    statuses = {}
    for p in stage["dynamic"]["refillPointStatuses"]:
        statuses.setdefault(p["sourceReferenceId"], []).append(p.get("status"))
    rows, ids, counts = [], set(), Counter()
    for site in stage["static"]["sites"]:
        for station in site["stations"]:
            rates = station["stationRatesUnassignedToEvse"]
            if len(rates) != 1:
                continue
            rate = rates[0]
            euro = simple_rate(rate)
            if euro is None:
                continue
            points = station["refillPoints"]
            if not points or any(len(x.get("connectors") or []) != 1 for x in points):
                continue
            kinds = {(p["connectors"][0].get("sourceConnectorType"),p["connectors"][0].get("sourcePowerW")) for p in points}
            if len(kinds) != 1:
                continue
            counts["homogeneousStations"] += 1
            for p in points:
                pid=p["sourceRefillPointId"]
                eid=p["connectors"][0].get("sourceExternalIdentifier")
                if not eid or not pid or eid in ids:
                    raise ValueError("Missing or duplicate EVSE")
                ids.add(eid)
                statuses_here = statuses.get(pid,[])
                state=str(statuses_here[0] or "unknown").lower() if len(statuses_here)==1 else "unknown"
                counts["candidateSourcePDC"] += 1
                counts["state_"+state] += 1
                if state in ACTIVE:
                    counts["activeSourcePDC"] += 1
                rows.append({
                    "sourceSiteId":site["sourceSiteId"], "sourceStationId":station["sourceStationId"],
                    "sourcePointId":pid, "externalEvseId":eid,
                    "sourceRateId":rate.get("sourceRateId"),
                    "connectorType":p["connectors"][0]["sourceConnectorType"],
                    "powerW":p["connectors"][0].get("sourcePowerW"),
                    "status":state, "sourceLastUpdated":rate.get("sourceLastUpdated"),
                    "eurPerKwhTTC":str(euro),
                    "independent20KwhEnergyOnlyExampleEur":str((euro*20).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)),
                    "sourceStationRateScopeVerifiedForPDC":False,
                    "siteSpecificPublicAccessVerified":False,
                    "v9Priceable":False,
                })
    return {
        "schemaVersion":1,"provider":"EnergyVision","country":"BE",
        "sourceSha256":sha,"collectedAt":stage.get("collectedAt"),
        "mode":"audit_only_no_price_promotion",
        "counts":dict(counts),"exampleEnergyKwh":20,
        "v9PricedPDC":0,"v9PublicationReady":False,"pdcCandidates":rows,
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",required=True)
    parser.add_argument("--output",default="artifacts/energyvision-kwh-proof-candidates.json.gz")
    parser.add_argument("--report",default="reports/belgium/energyvision-kwh-proof-audit.json")
    args=parser.parse_args()
    with gzip.open(args.stage,"rt",encoding="utf-8") as f:
        data=json.load(f)
    result=candidates(data)
    if not result["counts"].get("homogeneousStations") or result["v9PricedPDC"] or result["v9PublicationReady"]:
        raise ValueError("Invalid pricing evidence or unapproved promotion")
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(output,"wt",encoding="utf-8",compresslevel=9) as f:
        json.dump(result,f,ensure_ascii=False,separators=(",",":"))
    report={k:v for k,v in result.items() if k != "pdcCandidates"}
    report["pricesByRate"]=dict(Counter(r["eurPerKwhTTC"] for r in result["pdcCandidates"]))
    report["sourceDatesByMonth"]=dict(Counter(str(r["sourceLastUpdated"])[:7] for r in result["pdcCandidates"]))
    path=Path(args.report)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,sort_keys=True))

if __name__ == "__main__":
    main()
