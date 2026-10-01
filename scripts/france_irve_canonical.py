#!/usr/bin/env python3
"""Build the canonical non-Tesla France PDC inventory from national IRVE static data.

This first stage deliberately does not derive live availability from roaming apps.
Status and structured tariff offers are enrichment layers applied downstream.
"""

from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

SCHEMA_VERSION = "tcc.fr.irve.canonical.v1"

TRUE_VALUES = {"1", "true", "vrai", "yes", "oui"}
FALSE_VALUES = {"0", "false", "faux", "no", "non"}

PRICE_KWH_RE = re.compile(
    r"(?<!\d)(\d{1,3}(?:[\.,]\d{1,4})?)\s*(?:€|eur)\s*(?:/|par)\s*kwh\b",
    re.IGNORECASE,
)
AMBIGUOUS_TARIFF_RE = re.compile(
    r"\b(abonn|minute|min\b|heure|session|occupation|parking|stationnement|forfait|"
    r"variable|selon|partir\s+de)\b",
    re.IGNORECASE,
)


def clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def slug_text(value: Any) -> str:
    text = clean(value) or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().casefold()


def parse_bool(value: Any) -> Optional[bool]:
    text = slug_text(value)
    if not text:
        return None
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return None


def parse_float(value: Any) -> Optional[float]:
    text = clean(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def parse_int(value: Any) -> Optional[int]:
    number = parse_float(value)
    if number is None:
        return None
    return int(number)


def parse_coordinates(value: Any) -> Tuple[Optional[float], Optional[float]]:
    text = clean(value)
    if not text:
        return None, None
    parsed: Any = None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return None, None
    if not isinstance(parsed, (list, tuple)) or len(parsed) < 2:
        return None, None
    try:
        lon = float(parsed[0])
        lat = float(parsed[1])
    except (TypeError, ValueError):
        return None, None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None, None
    return lon, lat


def is_tesla(row: Dict[str, Any]) -> bool:
    # Tesla stays in its dedicated TCC pipeline. We intentionally use CPO/brand/
    # infrastructure-owner identity only; connector names are not considered.
    identity_fields = ("nom_operateur", "nom_enseigne", "nom_amenageur")
    return any("tesla" in slug_text(row.get(field)) for field in identity_fields)


def stable_fallback_id(prefix: str, parts: Iterable[Any]) -> str:
    normalized = "|".join(slug_text(part) for part in parts)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def canonical_station_id(row: Dict[str, Any], lon: Optional[float], lat: Optional[float]) -> str:
    for field in ("id_station_itinerance", "id_station_local"):
        value = clean(row.get(field))
        if value and slug_text(value) != "non concerne":
            return value.replace("*", "").replace("-", "")
    return stable_fallback_id(
        "fr-station",
        (row.get("nom_station"), row.get("adresse_station"), lon, lat),
    )


def canonical_pdc_id(row: Dict[str, Any], station_id: str) -> str:
    for field in ("id_pdc_itinerance", "id_pdc_local"):
        value = clean(row.get(field))
        if value and slug_text(value) != "non concerne":
            return value.replace("*", "").replace("-", "")
    return stable_fallback_id(
        "fr-pdc",
        (station_id, row.get("puissance_nominale"), row.get("id_pdc_local")),
    )


def parse_irve_tariff_fallback(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = clean(row.get("tarification"))
    if parse_bool(row.get("gratuit")) is True:
        return {
            "parse_status": "parsed",
            "kind": "free",
            "energy_eur_per_kwh": 0.0,
            "raw": raw,
            "source": "irve_static",
        }
    if not raw:
        return {
            "parse_status": "none",
            "kind": None,
            "energy_eur_per_kwh": None,
            "raw": None,
            "source": "irve_static",
        }

    matches = PRICE_KWH_RE.findall(raw)
    if len(matches) == 1 and not AMBIGUOUS_TARIFF_RE.search(slug_text(raw)):
        value = float(matches[0].replace(",", "."))
        return {
            "parse_status": "parsed",
            "kind": "energy",
            "energy_eur_per_kwh": value,
            "raw": raw,
            "source": "irve_static",
        }

    return {
        "parse_status": "text_only",
        "kind": None,
        "energy_eur_per_kwh": None,
        "raw": raw,
        "source": "irve_static",
    }


def canonicalize(row: Dict[str, Any]) -> Dict[str, Any]:
    lon, lat = parse_coordinates(row.get("coordonneesXY"))
    station_id = canonical_station_id(row, lon, lat)
    pdc_id = canonical_pdc_id(row, station_id)

    connector_map = {
        "type_ef": parse_bool(row.get("prise_type_ef")),
        "type_2": parse_bool(row.get("prise_type_2")),
        "combo_ccs": parse_bool(row.get("prise_type_combo_ccs")),
        "chademo": parse_bool(row.get("prise_type_chademo")),
        "other": parse_bool(row.get("prise_type_autre")),
        "cable_t2_attached": parse_bool(row.get("cable_t2_attache")),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "country": "FR",
        "station": {
            "id": station_id,
            "id_itinerance": clean(row.get("id_station_itinerance")),
            "id_local": clean(row.get("id_station_local")),
            "name": clean(row.get("nom_station")),
            "brand": clean(row.get("nom_enseigne")),
            "operator": clean(row.get("nom_operateur")),
            "infrastructure_owner": clean(row.get("nom_amenageur")),
            "address": clean(row.get("adresse_station")),
            "insee_code": clean(row.get("code_insee_commune")),
            "longitude": lon,
            "latitude": lat,
            "installation_type": clean(row.get("implantation_station")),
            "declared_pdc_count": parse_int(row.get("nbre_pdc")),
            "hours": clean(row.get("horaires")),
            "access_condition": clean(row.get("condition_acces")),
        },
        "pdc": {
            "id": pdc_id,
            "id_itinerance": clean(row.get("id_pdc_itinerance")),
            "id_local": clean(row.get("id_pdc_local")),
            "nominal_power_kw": parse_float(row.get("puissance_nominale")),
            "connectors": connector_map,
            "reservation": parse_bool(row.get("reservation")),
            "payment_adhoc": parse_bool(row.get("paiement_acte")),
            "payment_card": parse_bool(row.get("paiement_cb")),
            "payment_other": parse_bool(row.get("paiement_autre")),
            "commissioned_on": clean(row.get("date_mise_en_service")),
            "source_updated_on": clean(row.get("date_maj")),
        },
        "status": {
            "value": "inconnu",
            "source": None,
            "observed_at": None,
        },
        "tariff_offers": [],
        "tariff_fallback": parse_irve_tariff_fallback(row),
        "source": {
            "inventory": "irve_static_national",
            "id_pdc_itinerance": clean(row.get("id_pdc_itinerance")),
        },
    }


def open_text_csv(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def open_jsonl_output(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "wt", encoding="utf-8", newline="\n")
    return path.open("w", encoding="utf-8", newline="\n")


def build(input_path: Path, output_path: Path, stats_path: Path) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "rows_seen": 0,
        "rows_written": 0,
        "tesla_rows_excluded": 0,
        "fallback_tariff_parsed": 0,
        "fallback_tariff_text_only": 0,
        "fallback_tariff_none": 0,
        "missing_coordinates": 0,
        "duplicate_pdc_ids_skipped": 0,
    }
    seen_pdc_ids = set()

    with open_text_csv(input_path) as handle, open_jsonl_output(output_path) as out:
        reader = csv.DictReader(handle)
        for row in reader:
            stats["rows_seen"] += 1
            if is_tesla(row):
                stats["tesla_rows_excluded"] += 1
                continue

            record = canonicalize(row)
            pdc_id = record["pdc"]["id"]
            if pdc_id in seen_pdc_ids:
                stats["duplicate_pdc_ids_skipped"] += 1
                continue
            seen_pdc_ids.add(pdc_id)

            if record["station"]["longitude"] is None or record["station"]["latitude"] is None:
                stats["missing_coordinates"] += 1
            parse_status = record["tariff_fallback"]["parse_status"]
            stats[f"fallback_tariff_{parse_status}"] += 1

            out.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            stats["rows_written"] += 1

    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    args = parser.parse_args()

    stats = build(args.input, args.output, args.stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if stats["rows_written"] == 0:
        raise SystemExit("No non-Tesla IRVE rows were produced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
