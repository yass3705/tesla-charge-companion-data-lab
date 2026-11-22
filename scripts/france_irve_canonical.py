#!/usr/bin/env python3
"""Build the canonical non-Tesla France IRVE layer for Tesla Charge Companion.

The national IRVE static dataset is the physical source of truth. Operator/CPO
feeds enrich status and direct/subscription tariffs. Electroverse and Electra
are tariff-only enrichments. The national IRVE dynamic feed is status fallback
only; occupancy is deliberately ignored.

This module uses only the Python standard library so it can run in GitHub
Actions without repository-wide dependency changes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from itertools import chain
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, TextIO

IRVE_STATIC_URL = "https://www.data.gouv.fr/api/1/datasets/r/4ca78c71-4ea4-475d-bd3a-d4aef88f7bf8"
SCHEMA_VERSION = "0.1.0"

STATUS_UNKNOWN = "unknown"
STATUS_IN_SERVICE = "in_service"
STATUS_OUT_OF_SERVICE = "out_of_service"

SOURCE_CPO_DIRECT = "cpo_direct"
SOURCE_IRVE_DYNAMIC = "irve_dynamic"
SOURCE_ELECTROVERSE = "electroverse"
SOURCE_ELECTRA = "electra"

STATUS_PRIORITY = {
    SOURCE_CPO_DIRECT: 300,
    SOURCE_IRVE_DYNAMIC: 200,
}

ALLOWED_OFFER_TYPES = {
    "DIRECT_PUBLIC",
    "CPO_SUBSCRIPTION",
    "ELECTROVERSE",
    "ELECTRA",
}
IRVE_FALLBACK_TYPE = "IRVE_FALLBACK_PARSED"

TESLA_TOKEN = re.compile(r"(?i)(?:^|[^a-z0-9])tesla(?:[^a-z0-9]|$)")
EUR_KWH = re.compile(
    r"(?i)(?<![\d.,])(\d{1,2}(?:[.,]\d{1,4})?)\s*(?:€|eur(?:os?)?)\s*(?:/|par\s+)?\s*kwh\b"
)
AMBIGUOUS_TARIFF_TOKENS = (
    "minute", "/min", " par min", "session", "heure", "/h", "parking",
    "stationnement", "abonnement", "membre", "selon", "a partir", "à partir",
    "minimum", "forfait", "occupation", "connexion", "plafond",
)

TRUE_VALUES = {"1", "true", "vrai", "yes", "oui", "y"}
FALSE_VALUES = {"0", "false", "faux", "no", "non", "n"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def norm_id(value: Any) -> str | None:
    value = text(value).upper().replace(" ", "")
    return value or None


def parse_bool(value: Any) -> bool | None:
    value = text(value).lower()
    if not value:
        return None
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return None


def parse_float(value: Any) -> float | None:
    raw = text(value).replace(",", ".")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_coordinates(value: Any) -> dict[str, float] | None:
    raw = text(value)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, (list, tuple)) and len(parsed) >= 2:
            lon, lat = float(parsed[0]), float(parsed[1])
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                return {"lat": lat, "lon": lon}
    except (ValueError, TypeError, json.JSONDecodeError):
        pass

    nums = re.findall(r"-?\d+(?:[.,]\d+)?", raw)
    if len(nums) >= 2:
        try:
            lon = float(nums[0].replace(",", "."))
            lat = float(nums[1].replace(",", "."))
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                return {"lat": lat, "lon": lon}
        except ValueError:
            pass
    return None


def is_tesla_row(row: dict[str, Any]) -> bool:
    """Exclude Tesla only when an identity field identifies Tesla."""
    for field in ("nom_operateur", "nom_amenageur", "nom_enseigne"):
        if TESLA_TOKEN.search(text(row.get(field))):
            return True
    return False


def connector_types(row: dict[str, Any]) -> list[str]:
    mapping = {
        "prise_type_ef": "EF",
        "prise_type_2": "TYPE_2",
        "prise_type_combo_ccs": "CCS",
        "prise_type_chademo": "CHADEMO",
        "prise_type_autre": "OTHER",
    }
    return [label for field, label in mapping.items() if parse_bool(row.get(field)) is True]


def canonical_key(row: dict[str, Any]) -> tuple[str, str]:
    pdc_itin = norm_id(row.get("id_pdc_itinerance"))
    if pdc_itin:
        return f"irve:pdc:{pdc_itin}", "id_pdc_itinerance"

    pdc_local = text(row.get("id_pdc_local"))
    operator = text(row.get("nom_operateur")).lower()
    if pdc_local and operator:
        digest = hashlib.sha256(f"{operator}|{pdc_local}".encode("utf-8")).hexdigest()[:20]
        return f"irve:local:{digest}", "operator+id_pdc_local"

    stable_parts = [
        text(row.get("id_station_itinerance")),
        text(row.get("nom_station")),
        text(row.get("adresse_station")),
        text(row.get("coordonneesXY")),
        text(row.get("puissance_nominale")),
        text(row.get("id_pdc_local")),
    ]
    digest = hashlib.sha256("|".join(stable_parts).encode("utf-8")).hexdigest()[:20]
    return f"irve:row:{digest}", "deterministic_row_hash"


def parse_irve_tariff(row: dict[str, Any]) -> dict[str, Any] | None:
    """Return a calculative IRVE fallback only for unambiguous cases."""
    gratuit = parse_bool(row.get("gratuit"))
    raw = text(row.get("tarification"))

    if gratuit is True:
        return {
            "type": IRVE_FALLBACK_TYPE,
            "provider": "IRVE",
            "calculative": True,
            "currency": "EUR",
            "energyEurPerKwh": 0.0,
            "sourceField": "gratuit",
            "rawText": raw or None,
        }

    if not raw:
        return None

    lowered = raw.lower()
    if any(token in lowered for token in AMBIGUOUS_TARIFF_TOKENS):
        return None

    matches = [float(m.replace(",", ".")) for m in EUR_KWH.findall(raw)]
    unique = sorted(set(matches))
    if len(unique) != 1:
        return None

    return {
        "type": IRVE_FALLBACK_TYPE,
        "provider": "IRVE",
        "calculative": True,
        "currency": "EUR",
        "energyEurPerKwh": unique[0],
        "sourceField": "tarification",
        "rawText": raw,
    }


def normalize_static_row(row: dict[str, Any]) -> dict[str, Any]:
    key, key_quality = canonical_key(row)
    station_itin = norm_id(row.get("id_station_itinerance"))
    pdc_itin = norm_id(row.get("id_pdc_itinerance"))
    raw_tariff = text(row.get("tarification")) or None
    irve_fallback = parse_irve_tariff(row)

    return {
        "canonicalId": key,
        "canonicalIdQuality": key_quality,
        "idStationItinerance": station_itin,
        "idStationLocal": text(row.get("id_station_local")) or None,
        "idPdcItinerance": pdc_itin,
        "idPdcLocal": text(row.get("id_pdc_local")) or None,
        "operator": text(row.get("nom_operateur")) or None,
        "operatorContact": text(row.get("contact_operateur")) or None,
        "brand": text(row.get("nom_enseigne")) or None,
        "owner": text(row.get("nom_amenageur")) or None,
        "stationName": text(row.get("nom_station")) or None,
        "address": text(row.get("adresse_station")) or None,
        "inseeCode": text(row.get("code_insee_commune")) or None,
        "coordinates": parse_coordinates(row.get("coordonneesXY")),
        "nominalPowerKw": parse_float(row.get("puissance_nominale")),
        "connectors": connector_types(row),
        "access": {
            "condition": text(row.get("condition_acces")) or None,
            "hours": text(row.get("horaires")) or None,
            "reservation": parse_bool(row.get("reservation")),
        },
        "payment": {
            "free": parse_bool(row.get("gratuit")),
            "payAtAct": parse_bool(row.get("paiement_acte")),
            "bankCard": parse_bool(row.get("paiement_cb")),
            "other": parse_bool(row.get("paiement_autre")),
        },
        "status": {
            "state": STATUS_UNKNOWN,
            "source": None,
            "priority": 0,
            "asOf": None,
        },
        "tariffOffers": [],
        "irveTariff": {
            "rawText": raw_tariff,
            "calculativeFallback": irve_fallback,
        },
        "irve": {
            "lastUpdated": text(row.get("date_maj")) or None,
            "commissionedAt": text(row.get("date_mise_en_service")) or None,
            "observations": text(row.get("observations")) or None,
        },
    }


def normalize_status(value: Any) -> str:
    raw = text(value).lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "en_service": STATUS_IN_SERVICE,
        "in_service": STATUS_IN_SERVICE,
        "available": STATUS_IN_SERVICE,
        "disponible": STATUS_IN_SERVICE,
        "operational": STATUS_IN_SERVICE,
        "hors_service": STATUS_OUT_OF_SERVICE,
        "out_of_service": STATUS_OUT_OF_SERVICE,
        "unavailable": STATUS_OUT_OF_SERVICE,
        "indisponible": STATUS_OUT_OF_SERVICE,
        "faulted": STATUS_OUT_OF_SERVICE,
        "unknown": STATUS_UNKNOWN,
        "inconnu": STATUS_UNKNOWN,
        "": STATUS_UNKNOWN,
    }
    return mapping.get(raw, STATUS_UNKNOWN)


def normalize_offer(offer: dict[str, Any], provider_kind: str, provider_name: str) -> dict[str, Any] | None:
    offer_type = text(offer.get("type")).upper()
    if provider_kind == SOURCE_ELECTROVERSE:
        offer_type = "ELECTROVERSE"
    elif provider_kind == SOURCE_ELECTRA:
        offer_type = "ELECTRA"

    if offer_type not in ALLOWED_OFFER_TYPES:
        return None

    result = dict(offer)
    result["type"] = offer_type
    result["provider"] = text(offer.get("provider")) or provider_name
    result["calculative"] = bool(offer.get("calculative", True))
    result["sourceKind"] = provider_kind
    return result


def load_enrichment(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError(f"{path}: enrichment must be an object with a records array")
    kind = text(payload.get("sourceKind")).lower()
    if kind not in {SOURCE_CPO_DIRECT, SOURCE_IRVE_DYNAMIC, SOURCE_ELECTROVERSE, SOURCE_ELECTRA}:
        raise ValueError(f"{path}: unsupported sourceKind {kind!r}")
    return payload


def build_indexes(points: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_pdc: dict[str, dict[str, Any]] = {}
    by_station: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        if point["idPdcItinerance"]:
            by_pdc[point["idPdcItinerance"]] = point
        if point["idStationItinerance"]:
            by_station[point["idStationItinerance"]].append(point)
    return by_pdc, by_station


def apply_enrichment(points: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, int]:
    kind = text(payload.get("sourceKind")).lower()
    provider = text(payload.get("provider")) or kind
    by_pdc, by_station = build_indexes(points)
    stats = Counter()

    for record in payload["records"]:
        if not isinstance(record, dict):
            stats["invalid_record"] += 1
            continue

        pdc_id = norm_id(record.get("idPdcItinerance"))
        station_id = norm_id(record.get("idStationItinerance"))
        targets: list[dict[str, Any]] = []

        if pdc_id and pdc_id in by_pdc:
            targets = [by_pdc[pdc_id]]
            stats["matched_by_pdc"] += 1
        elif station_id and station_id in by_station:
            # Station-level tariff rules are legitimate; status is not, because
            # TCC must preserve per-PDC operational state.
            if kind in {SOURCE_ELECTROVERSE, SOURCE_ELECTRA, SOURCE_CPO_DIRECT} and record.get("offers"):
                targets = by_station[station_id]
                stats["matched_by_station"] += 1

        if not targets:
            stats["unmatched"] += 1
            continue

        if kind in STATUS_PRIORITY and pdc_id:
            state = normalize_status(record.get("status", record.get("etat_pdc")))
            if state != STATUS_UNKNOWN:
                for target in targets:
                    current = target["status"]
                    priority = STATUS_PRIORITY[kind]
                    if priority >= int(current.get("priority") or 0):
                        target["status"] = {
                            "state": state,
                            "source": provider,
                            "sourceKind": kind,
                            "priority": priority,
                            "asOf": text(record.get("asOf", record.get("horodatage"))) or None,
                        }
                        stats["status_applied"] += 1

        # Electra/Electroverse status fields are intentionally ignored.
        offers = record.get("offers") or []
        if kind == SOURCE_IRVE_DYNAMIC:
            offers = []
        if not isinstance(offers, list):
            offers = []

        for target in targets:
            for offer in offers:
                if not isinstance(offer, dict):
                    stats["invalid_offer"] += 1
                    continue
                normalized = normalize_offer(offer, kind, provider)
                if normalized is not None:
                    target["tariffOffers"].append(normalized)
                    stats["offer_applied"] += 1

    return dict(stats)


def finalize_tariffs(point: dict[str, Any]) -> None:
    """Apply IRVE tariff only when no structured external offer exists."""
    if point["tariffOffers"]:
        return
    fallback = point["irveTariff"]["calculativeFallback"]
    if fallback:
        point["tariffOffers"].append(fallback)


def open_source(source: str) -> tuple[TextIO, Any]:
    """Open local path or URL as UTF-8-sig text; return stream and owner to close."""
    if re.match(r"^https?://", source):
        req = urllib.request.Request(
            source,
            headers={
                "User-Agent": "TeslaChargeCompanionDataLab/1.0",
                "Accept": "text/csv,application/csv,text/plain,*/*;q=0.5",
            },
        )
        response = urllib.request.urlopen(req, timeout=120)
        wrapper = io.TextIOWrapper(response, encoding="utf-8-sig", errors="replace", newline="")
        return wrapper, response
    f = Path(source).open("r", encoding="utf-8-sig", errors="replace", newline="")
    return f, f


def iter_csv_rows(source: str) -> Iterator[dict[str, Any]]:
    stream, owner = open_source(source)
    try:
        sample_lines: list[str] = []
        sample_size = 0
        while sample_size < 65536:
            line = stream.readline()
            if not line:
                break
            sample_lines.append(line)
            sample_size += len(line)
        if not sample_lines:
            return

        sample = "".join(sample_lines)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

        reader = csv.DictReader(chain(sample_lines, stream), delimiter=delimiter)
        for row in reader:
            yield dict(row)
    finally:
        owner.close()


def build(static_source: str, enrichment_paths: Iterable[Path], limit: int | None = None) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    stats = Counter()

    for row in iter_csv_rows(static_source):
        stats["static_rows"] += 1
        if is_tesla_row(row):
            stats["tesla_rows_excluded"] += 1
            continue
        points.append(normalize_static_row(row))
        stats["non_tesla_points"] += 1
        if limit and stats["static_rows"] >= limit:
            break

    enrichment_stats: dict[str, Any] = {}
    for path in enrichment_paths:
        payload = load_enrichment(path)
        enrichment_stats[str(path)] = apply_enrichment(points, payload)

    for point in points:
        finalize_tariffs(point)

    status_counts = Counter(p["status"]["state"] for p in points)
    offer_counts = Counter(
        offer["type"] for point in points for offer in point["tariffOffers"]
    )
    raw_tariff_count = sum(bool(p["irveTariff"]["rawText"]) for p in points)
    calculative_irve_count = sum(
        bool(p["irveTariff"]["calculativeFallback"]) for p in points
    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "dataset": "tcc-france-irve-canonical",
        "generatedAt": now_iso(),
        "country": "FR",
        "scope": "public_non_tesla_irve",
        "source": {
            "irveStatic": static_source,
            "teslaExcluded": True,
        },
        "rules": {
            "inventoryAuthority": "IRVE_STATIC",
            "statusPriority": ["CPO_DIRECT", "IRVE_DYNAMIC", "UNKNOWN"],
            "occupancyUsed": False,
            "electroverseStatusUsed": False,
            "electraStatusUsed": False,
            "tariffSources": ["CPO_DIRECT", "CPO_SUBSCRIPTION", "ELECTROVERSE", "ELECTRA"],
            "irveTariffPolicy": "fallback_only_if_no_structured_offer",
            "statusGranularity": "PDC",
        },
        "summary": {
            **dict(stats),
            "statusCounts": dict(status_counts),
            "offerCounts": dict(offer_counts),
            "pointsWithIrveTariffText": raw_tariff_count,
            "pointsWithSafeIrveFallback": calculative_irve_count,
            "enrichments": enrichment_stats,
        },
        "chargePoints": points,
    }


def write_json(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--static", default=IRVE_STATIC_URL, help="IRVE static CSV path or URL")
    ap.add_argument(
        "--enrichment",
        action="append",
        default=[],
        help="Normalized enrichment JSON; repeat for each CPO/eMSP/dynamic source",
    )
    ap.add_argument("--out", default="out/france_irve_canonical.json")
    ap.add_argument("--summary-out", default=None)
    ap.add_argument("--limit", type=int, default=None, help="Smoke-test only: cap input rows")
    args = ap.parse_args()

    payload = build(args.static, [Path(p) for p in args.enrichment], args.limit)
    write_json(payload, Path(args.out))
    if args.summary_out:
        summary = {
            k: payload[k]
            for k in ("schemaVersion", "dataset", "generatedAt", "country", "scope", "source", "rules", "summary")
        }
        write_json(summary, Path(args.summary_out))

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
