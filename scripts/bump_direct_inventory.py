#!/usr/bin/env python3
"""Build a strict inventory of public charging stations physically operated by Bump in France.

Source of truth: Bump's own daily IRVE dataset published on data.gouv.fr.
The script intentionally does NOT treat Bump roaming/partner locations as Bump-operated.
Bump's current official IRVE export does not publish a ``tarification`` column; that absence is
recorded explicitly and no price is inferred from power, brand, payment mode or any other field.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DATASET_API = "https://www.data.gouv.fr/api/1/datasets/irve-statique-organisation-bump-1/"
DEFAULT_OUT = Path("data/national/bump_direct_inventory_france.json.gz")
DEFAULT_REPORT = Path("reports/bump_direct_inventory_france.md")
USER_AGENT = "TeslaChargeCompanionDataLab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"


def get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def get_json(url: str) -> dict[str, Any]:
    return json.loads(get_bytes(url).decode("utf-8"))


def norm(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", norm(value)).encode("ascii", "ignore").decode("ascii")
    return text.casefold()


def is_bump_operator(value: Any) -> bool:
    text = fold(value)
    return text == "bump" or text.startswith("bump ") or "bump sas" in text


def resolve_csv_resource(dataset: dict[str, Any]) -> dict[str, Any]:
    resources = [r for r in dataset.get("resources", []) if str(r.get("format") or "").lower() == "csv"]
    if not resources:
        raise RuntimeError("Bump data.gouv dataset has no CSV resource")
    resources.sort(key=lambda r: str(r.get("last_modified") or r.get("modified") or ""), reverse=True)
    resource = resources[0]
    url = resource.get("url") or resource.get("latest")
    if not url:
        raise RuntimeError("Bump CSV resource has no URL")
    return resource


def decode_csv(blob: bytes) -> tuple[list[dict[str, str]], list[str]]:
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            text = blob.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise RuntimeError("Unable to decode Bump IRVE CSV")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ","
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = [dict(row) for row in reader]
    return rows, list(reader.fieldnames or [])


PRICE_PATTERNS = {
    "energyEurPerKwh": re.compile(r"(?<!\d)(\d+[\.,]\d+|\d+)\s*(?:€|eur)\s*(?:/|par)\s*kwh", re.I),
    "minuteEur": re.compile(r"(?<!\d)(\d+[\.,]\d+|\d+)\s*(?:€|eur)\s*(?:/|par)\s*(?:min|minute)", re.I),
    "hourEur": re.compile(r"(?<!\d)(\d+[\.,]\d+|\d+)\s*(?:€|eur)\s*(?:/|par)\s*(?:h|heure)", re.I),
    "sessionEur": re.compile(r"(?<!\d)(\d+[\.,]\d+|\d+)\s*(?:€|eur)\s*(?:/|par)\s*(?:session|charge)", re.I),
}


def parse_tariff(text: str) -> dict[str, Any]:
    raw = norm(text)
    low = fold(raw)
    components: dict[str, list[float]] = {}
    for key, pattern in PRICE_PATTERNS.items():
        values = sorted({round(float(m.group(1).replace(",", ".")), 6) for m in pattern.finditer(raw)})
        if values:
            components[key] = values
    if not raw:
        classification = "missing"
    elif components:
        classification = "explicit_price_candidate"
    elif any(token in low for token in ("application", "appli", "app bump", "voir tarif", "consulter")):
        classification = "app_reference"
    elif any(token in low for token in ("gratuit", "free")):
        classification = "free_text"
    else:
        classification = "unparsed_text"
    return {"raw": raw, "classification": classification, "components": components}


def station_key(row: dict[str, str]) -> str:
    for field in ("id_station_itinerance", "id_station_local"):
        value = norm(row.get(field))
        if value:
            return value
    return "|".join(
        [
            norm(row.get("nom_station")),
            norm(row.get("adresse_station")),
            norm(row.get("code_insee_commune")),
            norm(row.get("coordonneesXY")),
        ]
    )


def station_from_rows(key: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    first = rows[0]
    point_tariffs = []
    for row in rows:
        parsed = parse_tariff(row.get("tarification", ""))
        point_tariffs.append(
            {
                "idPdcItinerance": norm(row.get("id_pdc_itinerance")),
                "idPdcLocal": norm(row.get("id_pdc_local")),
                "powerKw": norm(row.get("puissance_nominale")),
                "tarification": parsed,
                "free": norm(row.get("gratuit")),
                "paymentAdHoc": norm(row.get("paiement_acte")),
                "paymentCard": norm(row.get("paiement_cb")),
                "paymentOther": norm(row.get("paiement_autre")),
            }
        )
    tariff_strings = sorted({p["tarification"]["raw"] for p in point_tariffs if p["tarification"]["raw"]})
    classes = Counter(p["tarification"]["classification"] for p in point_tariffs)
    return {
        "stationKey": key,
        "idStationItinerance": norm(first.get("id_station_itinerance")),
        "idStationLocal": norm(first.get("id_station_local")),
        "name": norm(first.get("nom_station")),
        "brand": norm(first.get("nom_enseigne")),
        "operator": norm(first.get("nom_operateur")),
        "operatorPhone": norm(first.get("telephone_operateur")),
        "address": norm(first.get("adresse_station")),
        "inseeCode": norm(first.get("code_insee_commune")),
        "coordinates": norm(first.get("coordonneesXY")),
        "hours": norm(first.get("horaires")),
        "accessCondition": norm(first.get("condition_acces")),
        "declaredPointCount": norm(first.get("nbre_pdc")),
        "observedPointCount": len(rows),
        "lastUpdate": max((norm(r.get("date_maj")) for r in rows), default=""),
        "tariffStrings": tariff_strings,
        "tariffClassCounts": dict(sorted(classes.items())),
        "points": point_tariffs,
    }


def build_payload(dataset: dict[str, Any], resource: dict[str, Any], blob: bytes) -> dict[str, Any]:
    rows, headers = decode_csv(blob)
    if not rows:
        raise RuntimeError("Bump IRVE dataset is empty")
    if "nom_operateur" not in headers:
        raise RuntimeError(f"Unexpected Bump IRVE schema: {headers}")
    tariff_field_present = "tarification" in headers

    operated = [r for r in rows if is_bump_operator(r.get("nom_operateur"))]
    rejected = [r for r in rows if not is_bump_operator(r.get("nom_operateur"))]
    if not operated:
        raise RuntimeError("No Bump-operated rows found in Bump official dataset")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in operated:
        grouped[station_key(row)].append(row)
    stations = [station_from_rows(key, value) for key, value in grouped.items()]
    stations.sort(key=lambda x: (x["name"].casefold(), x["stationKey"]))

    all_points = [p for s in stations for p in s["points"]]
    tariff_classes = Counter(p["tarification"]["classification"] for p in all_points)
    tariff_strings = Counter(p["tarification"]["raw"] for p in all_points if p["tarification"]["raw"])
    explicit_stations = sum(
        1 for s in stations if any(p["tarification"]["classification"] == "explicit_price_candidate" for p in s["points"])
    )
    source_hash = hashlib.sha256(blob).hexdigest()
    latest_row_update = max((norm(r.get("date_maj")) for r in operated), default="")

    return {
        "schemaVersion": "1.1.0",
        "dataset": "bump-direct-operated-stations-france-inventory",
        "operator": "Bump",
        "country": "FR",
        "scope": {
            "onlyOfficialBumpPublishedStations": True,
            "onlyRowsWhoseOperatorIsBump": True,
            "roamingPartnerStationsIncluded": False,
            "tariffFieldPresentInOfficialIrve": tariff_field_present,
            "tariffsAreCandidatesUntilValidated": True,
            "rankableTariffsPublished": False,
        },
        "source": {
            "datasetApi": DATASET_API,
            "datasetId": dataset.get("id"),
            "datasetTitle": dataset.get("title"),
            "resourceId": resource.get("id"),
            "resourceUrl": resource.get("url"),
            "resourceLastModified": resource.get("last_modified") or resource.get("modified"),
            "resourceSha256": source_hash,
            "latestRowUpdate": latest_row_update,
            "headers": headers,
        },
        "counts": {
            "sourceRows": len(rows),
            "bumpOperatedRows": len(operated),
            "rejectedNonBumpRows": len(rejected),
            "stationCount": len(stations),
            "pointCount": len(all_points),
            "stationsWithExplicitPriceCandidate": explicit_stations,
            "tariffClassCounts": dict(sorted(tariff_classes.items())),
            "uniqueNonEmptyTariffStrings": len(tariff_strings),
        },
        "tariffStringCounts": [
            {"tariff": text, "pointCount": count}
            for text, count in tariff_strings.most_common()
        ],
        "stations": stations,
    }


def render_report(payload: dict[str, Any]) -> str:
    c = payload["counts"]
    tariff_field = payload["scope"]["tariffFieldPresentInOfficialIrve"]
    lines = [
        "# Bump direct France — official station inventory",
        "",
        "Source: Bump's own daily IRVE dataset on data.gouv.fr. Roaming/partner locations are excluded by construction.",
        "",
        "## Coverage",
        "",
        f"- Official source rows: **{c['sourceRows']}**",
        f"- Bump-operated rows retained: **{c['bumpOperatedRows']}**",
        f"- Public stations: **{c['stationCount']}**",
        f"- Public charge points: **{c['pointCount']}**",
        f"- Official IRVE `tarification` field present: **{str(tariff_field).lower()}**",
        f"- Stations with at least one explicit price candidate: **{c['stationsWithExplicitPriceCandidate']}**",
        "",
        "## Pricing conclusion",
        "",
    ]
    if not tariff_field:
        lines.append("Bump's current official IRVE export does **not** publish a `tarification` column. The dataset can authoritatively define the direct-operated station/PDC perimeter, but cannot supply prices. Driver-facing Bump app/API data is required for station-level tariffs.")
    else:
        lines.append("The official export contains a tariff field; values remain non-rankable until confirmed against Bump's driver-facing tariff source.")
    lines += [
        "",
        "## Decision rule for TCC",
        "",
        "No Bump price is inferred from this inventory. Only explicit, unambiguous station/point prices confirmed against Bump's driver-facing source can be promoted to the TCC tariff layer.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    dataset = get_json(DATASET_API)
    resource = resolve_csv_resource(dataset)
    blob = get_bytes(str(resource.get("url") or resource.get("latest")))
    payload = build_payload(dataset, resource, blob)

    DEFAULT_OUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    DEFAULT_OUT.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))
    DEFAULT_REPORT.write_text(render_report(payload), encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))
    print(f"tariffFieldPresent={payload['scope']['tariffFieldPresentInOfficialIrve']}")


if __name__ == "__main__":
    main()
