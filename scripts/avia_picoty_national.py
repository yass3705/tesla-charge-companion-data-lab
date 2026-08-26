#!/usr/bin/env python3
"""Build the direct-operated AVIA VOLT / Picoty (FR*PY2) France inventory.

The inventory source is the official national IRVE consolidation.  We fail closed on
pricing: IRVE tariff text is retained and parsed as evidence, but a station is only
rankable when an explicit station-level direct price has been validated separately.
"""
from __future__ import annotations

import csv
import gzip
import io
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
OUT = Path("data/national/avia_picoty_direct_stations_france.json.gz")
REPORT = Path("data/reports/avia_picoty_station_inventory_report.json")
PREFIX = "FRPY2"

# Station-level price observations already cross-checked during the AVIA VOLT audit.
# These are retained as evidence only. They do NOT make a station rankable until a
# Picoty/AVIA direct source (app/API/official tariff page) confirms the same amount.
OBSERVED_PRICE_EVIDENCE: dict[str, dict[str, Any]] = {
    "FRPY2P443000100": {"eurPerKwh": 0.65, "source": "carbuprix", "note": "Nantes, 162 Route de Rennes"},
    "FRPY2P333100073": {"eurPerKwh": 0.65, "source": "carbuprix", "note": "Lormont, 3 Avenue de la Resistance"},
    "FRPY2P172200016": {"eurPerKwh": 0.65, "source": "carbuprix", "note": "Salles-sur-Mer"},
    "FRPY2P174200113": {"eurPerKwh": 0.65, "source": "cross-check", "note": "Saint-Palais-sur-Mer; roaming prices ignored"},
    "FRPY2P221200033": {"eurPerKwh": 0.65, "source": "cross-check", "note": "Hillion"},
    "FRPY2P785500029": {"eurPerKwh": 0.65, "source": "cross-check", "note": "Maulette - Aire de la Prairie"},
    "FRPY2P785500031": {"eurPerKwh": 0.65, "source": "cross-check", "note": "Maulette - Aire du Val Raymond"},
    "FRPY2P851000109": {"eurPerKwh": 0.65, "source": "cross-check", "note": "Les Sables-d'Olonne"},
}


def get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "TeslaChargeCompanion-data-lab/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def normalize_id(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def nonempty(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        v = str(row.get(key) or "").strip()
        if v:
            return v
    return None


def parse_coordinates(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        v = json.loads(raw)
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            lon, lat = float(v[0]), float(v[1])
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                return [round(lat, 7), round(lon, 7)]
    except Exception:
        pass
    nums = re.findall(r"-?\d+(?:[.,]\d+)?", raw)
    if len(nums) >= 2:
        a, b = (float(x.replace(",", ".")) for x in nums[:2])
        # IRVE coordonneesXY is [longitude, latitude].
        if -180 <= a <= 180 and -90 <= b <= 90:
            return [round(b, 7), round(a, 7)]
    return None


def parse_kw(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(str(raw).replace(",", "."))
    except Exception:
        return None


def parse_kwh_prices(text: str) -> list[float]:
    if not text:
        return []
    text = text.lower().replace("eur", "€")
    values: list[float] = []
    for m in re.finditer(r"(\d{1,3}(?:[.,]\d{1,4})?)\s*€\s*(?:/|par\s*)?\s*kwh", text):
        try:
            v = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if 0 < v < 5:
            values.append(round(v, 6))
    return sorted(set(values))


def choose_resource(meta: dict[str, Any]) -> dict[str, Any]:
    resources = meta.get("resources") or []
    candidates = []
    for r in resources:
        title = str(r.get("title") or "")
        fmt = str(r.get("format") or "").lower()
        if fmt != "csv":
            continue
        if "consolidation de la derni" not in title.lower():
            continue
        if "schéma" not in title.lower() and "schema" not in title.lower():
            continue
        candidates.append(r)
    if not candidates:
        raise RuntimeError("No current IRVE consolidated CSV resource found")
    candidates.sort(key=lambda r: str(r.get("latest") or r.get("last_modified") or r.get("title") or ""), reverse=True)
    return candidates[0]


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "TeslaChargeCompanion-data-lab/1.0"})
    with urllib.request.urlopen(req, timeout=120) as src, dest.open("wb") as out:
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
        pdc_seen: set[str] = set()
        direct_rows = 0
        operator_names = Counter()

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
                if not sid_norm.startswith(PREFIX):
                    # We deliberately require a direct Picoty station identifier.  A PDC-only
                    # match without a direct station id is held outside the publication set.
                    continue

                operator = nonempty(row, "nom_operateur") or ""
                operator_names[operator] += 1
                key = sid_norm
                st = stations.setdefault(
                    key,
                    {
                        "stationId": sid_raw,
                        "stationIdNormalized": sid_norm,
                        "operator": operator or "Picoty",
                        "operatorPrefix": "FR*PY2",
                        "stationName": nonempty(row, "nom_station", "nom_enseigne"),
                        "address": nonempty(row, "adresse_station"),
                        "cityCodeInsee": nonempty(row, "code_insee_commune"),
                        "coordinates": parse_coordinates(nonempty(row, "coordonneesXY")),
                        "coordinatesSource": "irve-data-gouv" if parse_coordinates(nonempty(row, "coordonneesXY")) else None,
                        "evseIds": [],
                        "powerKwValues": [],
                        "tarificationRawValues": [],
                        "gratuitRawValues": [],
                        "paiementActeRawValues": [],
                        "paiementCbRawValues": [],
                        "observedPriceEvidence": None,
                        "irveExplicitEurPerKwhValues": [],
                        "directEurPerKwh": None,
                        "rankableDirect": False,
                        "blockingReason": "direct_picoty_price_not_officially_confirmed",
                    },
                )
                if not st.get("stationName"):
                    st["stationName"] = nonempty(row, "nom_station", "nom_enseigne")
                if not st.get("address"):
                    st["address"] = nonempty(row, "adresse_station")
                if not st.get("coordinates"):
                    c = parse_coordinates(nonempty(row, "coordonneesXY"))
                    if c:
                        st["coordinates"] = c
                        st["coordinatesSource"] = "irve-data-gouv"

                if pid_norm and pid_norm not in pdc_seen:
                    pdc_seen.add(pid_norm)
                    st["evseIds"].append(pid_raw)
                kw = parse_kw(nonempty(row, "puissance_nominale"))
                if kw is not None:
                    st["powerKwValues"].append(round(kw, 4))
                tariff = nonempty(row, "tarification")
                if tariff:
                    st["tarificationRawValues"].append(tariff)
                    st["irveExplicitEurPerKwhValues"].extend(parse_kwh_prices(tariff))
                for source_key, target_key in (
                    ("gratuit", "gratuitRawValues"),
                    ("paiement_acte", "paiementActeRawValues"),
                    ("paiement_cb", "paiementCbRawValues"),
                ):
                    v = nonempty(row, source_key)
                    if v:
                        st[target_key].append(v)

    station_list = []
    exact_irve_price_counts = Counter()
    for key, st in stations.items():
        for k in ("evseIds", "powerKwValues", "tarificationRawValues", "gratuitRawValues", "paiementActeRawValues", "paiementCbRawValues", "irveExplicitEurPerKwhValues"):
            st[k] = sorted(set(st[k]))
        st["evseCount"] = len(st["evseIds"])
        st["maxPowerKw"] = max(st["powerKwValues"]) if st["powerKwValues"] else None
        evidence = OBSERVED_PRICE_EVIDENCE.get(key)
        if evidence:
            st["observedPriceEvidence"] = evidence
        for p in st["irveExplicitEurPerKwhValues"]:
            exact_irve_price_counts[str(p)] += 1
        station_list.append(st)

    station_list.sort(key=lambda s: (str(s.get("cityCodeInsee") or ""), str(s.get("stationIdNormalized") or "")))
    counts = {
        "directIrveRows": direct_rows,
        "franceStationCount": len(station_list),
        "franceEvseCount": sum(int(s["evseCount"]) for s in station_list),
        "stationsWithCoordinates": sum(1 for s in station_list if s.get("coordinates")),
        "stationsWithObservedPriceEvidence": sum(1 for s in station_list if s.get("observedPriceEvidence")),
        "stationsWithIrveExplicitKwhPrice": sum(1 for s in station_list if s.get("irveExplicitEurPerKwhValues")),
        "rankableStationCount": sum(1 for s in station_list if s.get("rankableDirect")),
        "blockedStationCount": sum(1 for s in station_list if not s.get("rankableDirect")),
    }
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "avia-volt-picoty-direct-stations-france",
        "operator": "Picoty",
        "brand": "AVIA VOLT",
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
            "operatorPrefix": "FR*PY2",
            "roamingIncluded": False,
            "aviaBrandSitesOperatedByOtherCposIncluded": False,
            "pricesFailClosed": True,
            "observedThirdPartyPricesAreRankable": False,
        },
        "counts": counts,
        "operatorNamesSeen": dict(operator_names),
        "irveExplicitKwhPriceCounts": dict(exact_irve_price_counts),
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
                "irveExplicitKwhPriceCounts": dict(exact_irve_price_counts),
                "stationIds": [s["stationIdNormalized"] for s in station_list],
                "stationsWithObservedPriceEvidence": [s["stationIdNormalized"] for s in station_list if s.get("observedPriceEvidence")],
                "stationsWithIrveExplicitKwhPrice": [
                    {"stationId": s["stationIdNormalized"], "prices": s["irveExplicitEurPerKwhValues"], "tarification": s["tarificationRawValues"]}
                    for s in station_list if s.get("irveExplicitEurPerKwhValues")
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(counts, indent=2))
    print("IRVE explicit €/kWh values:", dict(exact_irve_price_counts))


if __name__ == "__main__":
    main()
