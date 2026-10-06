#!/usr/bin/env python3
"""Build V9 exact-station direct offers from an official IZIVIA FAST capture."""
import argparse
import gzip
import html
import json
import re
from collections import defaultdict
from pathlib import Path

EXPECTED_TARIFF = (
    "-- De 9h à 11h et de 15h00 à 17h00 : 0,30€/kWh; "
    "-- En dehors de ces horaires : 0,35€/kWh. "
    "-- Surcoût de 0,30€/min après 1h de charge, quelque soit l’horaire. "
    "Toutes minutes et kWh entamées sont dues. "
    "-L’horaire de branchement définit la tarification pour toute la session."
)


def clean(text):
    return " ".join(html.unescape(re.sub(r"<br\s*/?>", " ", text or "", flags=re.I)).split())


def rules():
    windows = [
        ("00:00", "09:00", 0.35),
        ("09:00", "11:00", 0.30),
        ("11:00", "15:00", 0.35),
        ("15:00", "17:00", 0.30),
        ("17:00", "24:00", 0.35),
    ]
    return [{"scope": "timeWindow", "start": start, "end": end, "billing": "kwh",
             "currency": "EUR", "pricePerKwh": price, "energyRounding": "started_kwh",
             "connectedTimeFreeMinutes": 60, "connectedTimePerMinuteAfterFreeEur": 0.30}
            for start, end, price in windows]


def connector_config(stat):
    standard = (stat.get("standard") or "").lower()
    power = float(stat.get("maxPowerInW") or 0) / 1000
    count = int(stat.get("totalConnectorCount") or 0)
    if count < 1 or power <= 0:
        return None
    if standard in ("t2", "type2", "type_2") and power <= 43:
        return ("AC", power)
    if standard in ("combo_t2", "ccs", "chademo") and power >= 50:
        return ("DC", power)
    return None


def build(capture):
    summary = capture["summary"]
    if summary.get("network") != "IZIVIA FAST" or summary.get("source") != "https://fronts-map.izivia.com/api/":
        raise ValueError("Wrong capture source or network")
    stations = capture["stations"]
    if len(stations) != summary["inventoryStations"] or len(stations) < 600:
        raise ValueError("Incomplete national station capture")
    station_ids = [row["stationId"] for row in stations]
    if len(set(station_ids)) != len(station_ids):
        raise ValueError("Duplicate national station ID")
    groups = defaultdict(set)
    excluded = []
    for row in stations:
        sid = row["stationId"]
        if not re.fullmatch(r"FRIZFPFAST\d+", sid) or row.get("status") != "direct_price_published":
            excluded.append({"stationId": sid, "reason": row.get("status", "invalid_station_id")})
            continue
        text = row.get("directRawPricing") or []
        if len(text) != 1 or clean(text[0]) != clean(EXPECTED_TARIFF):
            excluded.append({"stationId": sid, "reason": "unrecognized_direct_tariff"})
            continue
        detail = row.get("mapDetail") or {}
        if detail.get("legacyId") != row.get("legacyId") or detail.get("id") != row.get("mapId"):
            excluded.append({"stationId": sid, "reason": "map_identity_mismatch"})
            continue
        found = False
        for stat in detail.get("chargingConnectorsStats") or []:
            config = connector_config(stat)
            if config is None:
                continue
            groups[config].add(sid)
            found = True
        if not found:
            excluded.append({"stationId": sid, "reason": "no_supported_connector"})
    date = str(summary["capturedAt"])[:10]
    offers = []
    for (kind, power), ids in sorted(groups.items()):
        offers.append({
            "id": f"izivia-fast-official-{date}-{kind.lower()}-{str(power).replace('.', '_')}",
            "provider": f"IZIVIA FAST direct · relevé {date[8:10]}/{date[5:7]}/{date[:4]}",
            "operatorAliases": ["IZIVIA"],
            "directOperatorOnly": True,
            "stationIds": sorted(ids, key=lambda sid: int(sid.removeprefix("FRIZFPFAST"))),
            "connectorKinds": [kind],
            "minPowerKw": round(power - 0.5, 3),
            "maxPowerKw": round(power + 0.5, 3),
            "countries": ["FR"],
            "currency": "EUR",
            "priority": 125,
            "pricing": {"type": "rules", "priceSelectionBasis": "session_start_local_time",
                        "connectedTimeRounding": "started_minute", "rules": rules()},
            "source": "https://izivia.com/carte-bornes-de-recharge-izivia",
            "metadata": {"verifiedScope": "exact_station", "network": "IZIVIA FAST",
                         "timeZone": "Europe/Paris", "capturedAt": date,
                         "stationCount": len(ids), "connectorKind": kind, "powerKw": power,
                         "billing": "Started kWh and connected minutes; energy rate locked at connection start"},
        })
    offered = set(sid for offer in offers for sid in offer["stationIds"])
    return {
        "schemaVersion": 1, "country": "FR", "generatedAt": date,
        "mode": "exact_station_direct_tariff",
        "policy": {"exactStationIdsOnly": True, "networkDefault": False, "fastOnly": True,
                   "expressExcluded": True, "sourceEvidence": "Official IZIVIA map per-station pricing cards",
                   "capturedStations": len(stations), "pricedStations": len(offered),
                   "excludedStations": excluded,
                   "mapOnlyStationsWithoutNationalInventory": len(summary.get("unmatchedMapCodes") or [])},
        "directOffers": offers, "subscriptionOffers": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with gzip.open(args.capture, "rt", encoding="utf-8") as file:
        capture = json.load(file)
    offers = build(capture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(offers, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"pricedStations": offers["policy"]["pricedStations"],
                      "excludedStations": offers["policy"]["excludedStations"],
                      "mapOnlyStations": offers["policy"]["mapOnlyStationsWithoutNationalInventory"],
                      "offerGroups": [(o["connectorKinds"][0], o["metadata"]["powerKw"], len(o["stationIds"])) for o in offers["directOffers"]]}, ensure_ascii=False))
    if offers["policy"]["pricedStations"] < 600:
        raise SystemExit("National IZIVIA FAST offer coverage unexpectedly low")


if __name__ == "__main__":
    main()
