#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

RESOURCE_ID = "bfb42e5a-5166-41dd-9d6d-2dd97b8b06cf"
API_BASE = f"https://tabular-api.data.gouv.fr/api/resources/{RESOURCE_ID}/data/"
OUT_DATA = Path("data/national/bump_direct_stations_france.json.gz")
OUT_REPORT = Path("data/reports/bump_direct_tariffs_report.json")


def fetch_json(url: str, attempts: int = 4) -> dict:
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TeslaChargeCompanionDataLab/1.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except Exception as exc:
            last = exc
            if i + 1 < attempts:
                time.sleep(2 ** i)
    raise RuntimeError(f"GET failed after {attempts} attempts: {url}: {last}")


def clean(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return v


def station_key(row: dict) -> str:
    return str(
        clean(row.get("id_station_itinerance"))
        or clean(row.get("id_station_local"))
        or clean(row.get("nom_station"))
        or f"row-{row.get('__id')}"
    )


def pdc_key(row: dict) -> str:
    return str(
        clean(row.get("id_pdc_itinerance"))
        or clean(row.get("id_pdc_local"))
        or f"row-{row.get('__id')}"
    )


def main() -> None:
    rows = []
    page = 1
    page_size = 1000
    total = None
    while True:
        q = urllib.parse.urlencode({"page": page, "page_size": page_size})
        payload = fetch_json(f"{API_BASE}?{q}")
        batch = payload.get("data") or []
        rows.extend(batch)
        meta = payload.get("meta") or {}
        total = meta.get("total", total)
        print(f"page={page} rows={len(batch)} collected={len(rows)} total={total}")
        if not batch or (total is not None and len(rows) >= int(total)):
            break
        page += 1
        if page > 1000:
            raise RuntimeError("pagination safety stop")

    stations = defaultdict(list)
    for r in rows:
        stations[station_key(r)].append(r)

    tariff_fields = ["tarification", "gratuit", "paiement_acte", "paiement_cb", "paiement_autre", "condition_acces", "observations"]
    tariff_counter = Counter()
    stations_with_tariff = set()
    pdc_with_tariff = 0
    examples = []

    for r in rows:
        t = clean(r.get("tarification"))
        if t is not None:
            txt = str(t)
            tariff_counter[txt] += 1
            stations_with_tariff.add(station_key(r))
            pdc_with_tariff += 1
            if len(examples) < 40:
                examples.append({
                    "stationId": station_key(r),
                    "pdcId": pdc_key(r),
                    "name": clean(r.get("nom_station")),
                    "address": clean(r.get("adresse_station")),
                    "city": clean(r.get("consolidated_commune")) or clean(r.get("nom_commune")),
                    "powerKw": clean(r.get("puissance_nominale")),
                    "tarification": txt,
                    "gratuit": clean(r.get("gratuit")),
                    "conditionAcces": clean(r.get("condition_acces")),
                    "observations": clean(r.get("observations")),
                })

    normalized_stations = []
    for sid, srows in stations.items():
        first = srows[0]
        tariffs = sorted({str(clean(r.get("tarification"))) for r in srows if clean(r.get("tarification")) is not None})
        normalized_stations.append({
            "stationId": sid,
            "name": clean(first.get("nom_station")),
            "address": clean(first.get("adresse_station")),
            "city": clean(first.get("consolidated_commune")) or clean(first.get("nom_commune")),
            "coordinates": clean(first.get("coordonneesXY")),
            "operator": clean(first.get("nom_operateur")) or "Bump",
            "stationCountPdc": len(srows),
            "tariffs": tariffs,
            "evses": [
                {
                    "pdcId": pdc_key(r),
                    "powerKw": clean(r.get("puissance_nominale")),
                    "tarification": clean(r.get("tarification")),
                    "gratuit": clean(r.get("gratuit")),
                    "paiementActe": clean(r.get("paiement_acte")),
                    "paiementCb": clean(r.get("paiement_cb")),
                    "paiementAutre": clean(r.get("paiement_autre")),
                    "conditionAcces": clean(r.get("condition_acces")),
                    "observations": clean(r.get("observations")),
                    "raw": r,
                }
                for r in srows
            ],
        })

    generated = datetime.now(timezone.utc).isoformat()
    dataset = {
        "operator": "Bump",
        "country": "FR",
        "generatedAt": generated,
        "source": {
            "type": "official-data-gouv",
            "dataset": "IRVE statique (organisation Bump)",
            "resourceId": RESOURCE_ID,
            "api": API_BASE,
        },
        "scope": {"operatorDirectOnly": True, "roamingIncluded": False},
        "counts": {
            "franceStationCount": len(stations),
            "franceEvseCount": len(rows),
            "stationsWithTarification": len(stations_with_tariff),
            "evsesWithTarification": pdc_with_tariff,
        },
        "stations": sorted(normalized_stations, key=lambda x: (str(x.get("city") or ""), str(x.get("name") or ""), x["stationId"])),
    }

    missing_by_field = {f: sum(1 for r in rows if clean(r.get(f)) is None) for f in tariff_fields}
    report = {
        "operator": "Bump",
        "generatedAt": generated,
        "sourceResourceId": RESOURCE_ID,
        "counts": dataset["counts"],
        "tarificationCoveragePctStations": round(100 * len(stations_with_tariff) / max(1, len(stations)), 2),
        "tarificationCoveragePctEvses": round(100 * pdc_with_tariff / max(1, len(rows)), 2),
        "uniqueTarificationStrings": len(tariff_counter),
        "topTarificationStrings": [{"tarification": k, "evseCount": v} for k, v in tariff_counter.most_common(100)],
        "missingValuesByField": missing_by_field,
        "examplesWithTarification": examples,
        "assessment": {
            "openDataCarriesTariff": bool(tariff_counter),
            "nextStep": "Parse tarification strings and validate against Bump app/AFIR" if tariff_counter else "Probe Bump app/AFIR price source using station/EVSE identifiers",
        },
    }

    OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_DATA.write_bytes(gzip.compress(json.dumps(dataset, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), compresslevel=9))
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
