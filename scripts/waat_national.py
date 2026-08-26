#!/usr/bin/env python3
"""Build the direct-operated WAAT (FR*WA2) France public-station inventory.

Inventory comes from the official national IRVE consolidation. Pricing fails closed:
WAAT/Monta can configure tariffs per site/profile/time and the public IRVE rows do not
provide a reliable authoritative retail tariff feed, so no station is rankable here.
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import tempfile
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATASET_API = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "base-nationale-des-irve-data-gouv-infrastructures-de-recharge-pour-vehicules-electriques/"
)
OUT = Path("data/national/waat_direct_stations_france.json.gz")
REPORT = Path("data/reports/waat_station_inventory_report.json")
PREFIX = "FRWA2"


def get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "TeslaChargeCompanion-data-lab/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def normalize_id(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def nonempty(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return None


def parse_coordinates(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            lon, lat = float(value[0]), float(value[1])
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                return [round(lat, 7), round(lon, 7)]
    except Exception:
        pass
    nums = re.findall(r"-?\d+(?:[.,]\d+)?", raw)
    if len(nums) >= 2:
        lon, lat = (float(x.replace(",", ".")) for x in nums[:2])
        if -180 <= lon <= 180 and -90 <= lat <= 90:
            return [round(lat, 7), round(lon, 7)]
    return None


def parse_kw(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(str(raw).replace(",", "."))
    except Exception:
        return None


def choose_resource(meta: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    for resource in meta.get("resources") or []:
        title = str(resource.get("title") or "")
        fmt = str(resource.get("format") or "").lower()
        if fmt != "csv":
            continue
        if "consolidation de la derni" not in title.lower():
            continue
        if "schéma" not in title.lower() and "schema" not in title.lower():
            continue
        candidates.append(resource)
    if not candidates:
        raise RuntimeError("No current IRVE consolidated CSV resource found")
    candidates.sort(
        key=lambda r: str(r.get("latest") or r.get("last_modified") or r.get("title") or ""),
        reverse=True,
    )
    return candidates[0]


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "TeslaChargeCompanion-data-lab/1.0"})
    with urllib.request.urlopen(req, timeout=180) as src, dest.open("wb") as out:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def main() -> None:
    meta = get_json(DATASET_API)
    resource = choose_resource(meta)
    resource_url = str(resource.get("url") or "")
    if not resource_url:
        raise RuntimeError("Selected IRVE resource has no URL")

    with tempfile.TemporaryDirectory() as td:
        csv_path = Path(td) / "irve.csv"
        download(resource_url, csv_path)

        stations: dict[str, dict[str, Any]] = {}
        operator_names: Counter[str] = Counter()
        direct_rows = 0

        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                raise RuntimeError("IRVE CSV has no header")
            for row in reader:
                sid_raw = nonempty(row, "id_station_itinerance", "id_station_local") or ""
                pid_raw = nonempty(row, "id_pdc_itinerance", "id_pdc_local") or ""
                sid_norm = normalize_id(sid_raw)
                pid_norm = normalize_id(pid_raw)
                if not (sid_norm.startswith(PREFIX) or pid_norm.startswith(PREFIX)):
                    continue
                direct_rows += 1
                # Fail closed: require the station itself to carry WAAT's FR*WA2 prefix.
                if not sid_norm.startswith(PREFIX):
                    continue

                operator = nonempty(row, "nom_operateur") or "WAAT"
                operator_names[operator] += 1
                key = sid_norm
                coords = parse_coordinates(nonempty(row, "coordonneesXY"))
                station = stations.setdefault(
                    key,
                    {
                        "stationId": sid_raw,
                        "stationIdNormalized": sid_norm,
                        "operator": operator,
                        "operatorPrefix": "FR*WA2",
                        "stationName": nonempty(row, "nom_station", "nom_enseigne"),
                        "brand": nonempty(row, "nom_enseigne"),
                        "address": nonempty(row, "adresse_station"),
                        "cityCodeInsee": nonempty(row, "code_insee_commune"),
                        "coordinates": coords,
                        "coordinatesSource": "irve-data-gouv" if coords else None,
                        "implantation": nonempty(row, "implantation_station"),
                        "accessCondition": nonempty(row, "condition_acces"),
                        "hours": nonempty(row, "horaires"),
                        "evses": [],
                        "tarificationRawValues": [],
                        "paymentActRawValues": [],
                        "paymentCbRawValues": [],
                        "paymentOtherRawValues": [],
                        "directEurPerKwh": None,
                        "rankableDirect": False,
                        "blockingReason": "waat_monta_direct_retail_tariff_not_publicly_resolved",
                    },
                )
                if not station.get("coordinates") and coords:
                    station["coordinates"] = coords
                    station["coordinatesSource"] = "irve-data-gouv"
                tariff = nonempty(row, "tarification")
                if tariff:
                    station["tarificationRawValues"].append(tariff)
                for source_key, target_key in (
                    ("paiement_acte", "paymentActRawValues"),
                    ("paiement_cb", "paymentCbRawValues"),
                    ("paiement_autre", "paymentOtherRawValues"),
                ):
                    value = nonempty(row, source_key)
                    if value:
                        station[target_key].append(value)

                if pid_norm:
                    evse = {
                        "evseId": pid_raw,
                        "evseIdNormalized": pid_norm,
                        "powerKw": parse_kw(nonempty(row, "puissance_nominale")),
                        "type2": nonempty(row, "prise_type_2"),
                        "comboCcs": nonempty(row, "prise_type_combo_ccs"),
                        "chademo": nonempty(row, "prise_type_chademo"),
                        "otherConnector": nonempty(row, "prise_type_autre"),
                        "directEurPerKwh": None,
                        "rankableDirect": False,
                        "blockingReason": "waat_monta_direct_retail_tariff_not_publicly_resolved",
                    }
                    existing = {x["evseIdNormalized"] for x in station["evses"]}
                    if pid_norm not in existing:
                        station["evses"].append(evse)

    station_list = []
    for station in stations.values():
        station["evses"].sort(key=lambda e: e["evseIdNormalized"])
        for key in ("tarificationRawValues", "paymentActRawValues", "paymentCbRawValues", "paymentOtherRawValues"):
            station[key] = sorted(set(station[key]))
        station["evseCount"] = len(station["evses"])
        powers = [float(e["powerKw"]) for e in station["evses"] if e.get("powerKw") is not None]
        station["powerKwValues"] = sorted(set(powers))
        station["maxPowerKw"] = max(powers) if powers else None
        station_list.append(station)

    station_list.sort(key=lambda s: (str(s.get("cityCodeInsee") or ""), s["stationIdNormalized"]))
    all_evses = [e for s in station_list for e in s["evses"]]
    counts = {
        "directIrveRows": direct_rows,
        "franceStationCount": len(station_list),
        "franceEvseCount": len(all_evses),
        "stationsWithCoordinates": sum(1 for s in station_list if s.get("coordinates")),
        "stationsWithTarificationText": sum(1 for s in station_list if s.get("tarificationRawValues")),
        "rankableStationCount": 0,
        "rankableEvseCount": 0,
        "blockedStationCount": len(station_list),
        "blockedEvseCount": len(all_evses),
    }

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "waat-direct-stations-france",
        "operator": "WAAT",
        "country": "FR",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "type": "official-irve-consolidation",
            "datasetApi": DATASET_API,
            "resourceTitle": resource.get("title"),
            "resourceUrl": resource_url,
        },
        "scope": {
            "operatorDirectOnly": True,
            "operatorPrefix": "FR*WA2",
            "roamingIncluded": False,
            "myWaatRoamingIncluded": False,
            "residentialTariffsIncluded": False,
            "pricesFailClosed": True,
            "countryDefaultsAreRankable": False,
            "stationTariffsRequireAuthoritativeAutomaticSource": True,
        },
        "pricingStatus": {
            "backend": "Monta white-label confirmed",
            "publicNationalFixedTariff": False,
            "publicMachineReadableStationTariffFeedFound": False,
            "montaPartnerPriceApiRequiresAuthentication": True,
            "safeFallback": "inventory_only_do_not_rank_without_direct_station_price",
        },
        "counts": counts,
        "operatorNamesSeen": dict(operator_names),
        "stations": station_list,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    OUT.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    REPORT.write_text(
        json.dumps(
            {
                "generatedAt": payload["generatedAt"],
                "resourceTitle": resource.get("title"),
                "counts": counts,
                "operatorNamesSeen": dict(operator_names),
                "stationIds": [s["stationIdNormalized"] for s in station_list],
                "stationsWithTarificationText": [
                    {"stationId": s["stationIdNormalized"], "values": s["tarificationRawValues"]}
                    for s in station_list if s.get("tarificationRawValues")
                ],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
