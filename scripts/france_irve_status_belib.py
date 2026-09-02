#!/usr/bin/env python3
"""Build a PDC-level Belib direct-status enrichment for canonical France IRVE.

Belib realtime data is published by Ville de Paris. It uses an `ID PDC local`
whose punctuation can differ from the national PAN representation, so matching
is allowed only through a collision-free normalized identifier that resolves to
an existing current PAN `id_pdc_itinerance`. Unmatched Belib rows never create a
physical PDC. Occupation is deliberately ignored: an occupied/charging PDC is
still operational.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from france_irve_canonical import (
    IRVE_STATIC_URL,
    SOURCE_CPO_DIRECT,
    STATUS_IN_SERVICE,
    STATUS_OUT_OF_SERVICE,
    STATUS_UNKNOWN,
    iter_csv_rows,
    norm_id,
    now_iso,
    text,
    write_json,
)

BELIB_REALTIME_URL = "https://www.data.gouv.fr/api/1/datasets/r/fde557ec-b96e-49a5-9282-31407296282c"


def compact_id(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", text(value).upper())


def status_key(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", text(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", raw.lower()).strip()


def normalize_belib_status(value: Any) -> str:
    raw = status_key(value)
    if raw in {"disponible", "occupe (en charge)", "occupe", "en charge", "reserve"}:
        return STATUS_IN_SERVICE
    if raw in {"en maintenance", "hors service", "hors_service", "supprime"}:
        return STATUS_OUT_OF_SERVICE
    # Planned/commissioning and any new value fail closed to unknown.
    return STATUS_UNKNOWN


def canonical_pdc_map(static_source: str) -> tuple[dict[str, str], Counter]:
    mapping: dict[str, str] = {}
    collisions: set[str] = set()
    stats = Counter()
    for row in iter_csv_rows(static_source):
        raw = norm_id(row.get("id_pdc_itinerance"))
        if not raw:
            continue
        key = compact_id(raw)
        if not key:
            continue
        previous = mapping.get(key)
        if previous and previous != raw:
            collisions.add(key)
        else:
            mapping[key] = raw
    for key in collisions:
        mapping.pop(key, None)
    stats["canonicalPdcKeys"] = len(mapping)
    stats["canonicalNormalizationCollisions"] = len(collisions)
    return mapping, stats


def normalize_belib(source: str, static_source: str) -> dict[str, Any]:
    canonical, stats = canonical_pdc_map(static_source)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in iter_csv_rows(source):
        stats["inputRows"] += 1
        raw_id = text(row.get("ID PDC local"))
        key = compact_id(raw_id)
        if not key:
            stats["missingPdcId"] += 1
            continue
        if key in seen:
            stats["duplicateSourcePdc"] += 1
            continue
        seen.add(key)

        canonical_id = canonical.get(key)
        if not canonical_id:
            stats["unmatchedCurrentPan"] += 1
            continue

        raw_status = text(row.get("Statut du point de recharge"))
        state = normalize_belib_status(raw_status)
        as_of = text(row.get("Heure mise à jour")) or None
        records.append(
            {
                "idPdcItinerance": canonical_id,
                "status": state,
                "rawStatus": raw_status or None,
                "asOf": as_of,
                "sourceRecordId": raw_id,
                "matchMethod": "normalized_belib_id_to_exact_current_irve_pdc",
                "matchConfidence": "exact",
                "offers": [],
            }
        )
        stats["matchedCurrentPan"] += 1
        stats[f"status_{state}"] += 1

    stats["outputRecords"] = len(records)
    stats["uniqueSourcePdc"] = len(seen)
    records.sort(key=lambda r: r["idPdcItinerance"])

    return {
        "schemaVersion": "1.0.0",
        "sourceKind": SOURCE_CPO_DIRECT,
        "provider": "Belib",
        "generatedAt": now_iso(),
        "source": source,
        "scope": "current_irve_pdc_only",
        "identityRule": "punctuation-insensitive Belib ID PDC local must resolve uniquely to current PAN id_pdc_itinerance",
        "occupancyUsed": False,
        "summary": dict(stats),
        "records": records,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=BELIB_REALTIME_URL)
    ap.add_argument("--static", default=IRVE_STATIC_URL)
    ap.add_argument("--out", default="out/france_irve_status_belib.json")
    args = ap.parse_args()

    payload = normalize_belib(args.source, args.static)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(payload, out)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
