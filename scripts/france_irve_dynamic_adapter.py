#!/usr/bin/env python3
"""Normalize the PAN national IRVE dynamic feed into TCC status enrichments.

Only `etat_pdc` is retained. Occupancy is intentionally discarded. Because the
PAN dynamic consolidation is not deduplicated, duplicate PDC identifiers are
resolved conservatively using the newest timestamp; same-time conflicts are
reported and omitted instead of guessing.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from france_irve_canonical import (
    SOURCE_IRVE_DYNAMIC,
    STATUS_UNKNOWN,
    iter_csv_rows,
    norm_id,
    normalize_status,
    now_iso,
    text,
    write_json,
)

IRVE_DYNAMIC_URL = "https://www.data.gouv.fr/api/1/datasets/r/89185b1f-f958-4c5b-9282-399a66ecee97"


def timestamp_key(value: Any) -> tuple[int, str]:
    raw = text(value)
    if not raw:
        return (0, "")
    candidate = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (1, dt.astimezone(timezone.utc).isoformat())
    except ValueError:
        # Still deterministic; valid ISO timestamps always beat unknown formats.
        return (0, raw)


def normalize_dynamic(source: str, limit: int | None = None) -> dict[str, Any]:
    selected: dict[str, dict[str, Any]] = {}
    stats = Counter()

    for row in iter_csv_rows(source):
        stats["inputRows"] += 1
        pdc_id = norm_id(row.get("id_pdc_itinerance"))
        if not pdc_id:
            stats["missingPdcId"] += 1
            if limit and stats["inputRows"] >= limit:
                break
            continue

        state = normalize_status(row.get("etat_pdc"))
        if state == STATUS_UNKNOWN:
            stats["unknownState"] += 1
            if limit and stats["inputRows"] >= limit:
                break
            continue

        as_of = text(row.get("horodatage")) or None
        candidate = {
            "idPdcItinerance": pdc_id,
            "idStationItinerance": norm_id(row.get("id_station_itinerance")),
            "status": state,
            "asOf": as_of,
        }

        current = selected.get(pdc_id)
        if current is None:
            selected[pdc_id] = candidate
        else:
            stats["duplicatePdcRows"] += 1
            current_key = timestamp_key(current.get("asOf"))
            candidate_key = timestamp_key(as_of)
            if candidate_key > current_key:
                selected[pdc_id] = candidate
                stats["newerDuplicateSelected"] += 1
            elif candidate_key == current_key and candidate["status"] != current["status"]:
                # Same recency, contradictory status: omit this PDC entirely so
                # the canonical layer falls back to direct CPO or unknown.
                selected[pdc_id] = {
                    "idPdcItinerance": pdc_id,
                    "idStationItinerance": candidate.get("idStationItinerance") or current.get("idStationItinerance"),
                    "_conflict": True,
                }
                stats["sameTimestampConflicts"] += 1

        if limit and stats["inputRows"] >= limit:
            break

    records = [
        record for record in selected.values()
        if not record.get("_conflict")
    ]
    stats["outputRecords"] = len(records)

    return {
        "schemaVersion": "1.0",
        "provider": "PAN IRVE dynamique",
        "sourceKind": SOURCE_IRVE_DYNAMIC,
        "generatedAt": now_iso(),
        "source": source,
        "rules": {
            "etatPdcOnly": True,
            "occupationPdcUsed": False,
            "deduplication": "newest_horodatage_per_id_pdc_itinerance",
            "sameTimestampConflict": "omit",
        },
        "summary": dict(stats),
        "records": records,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=IRVE_DYNAMIC_URL)
    ap.add_argument("--out", default="out/france_irve_dynamic_enrichment.json")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    payload = normalize_dynamic(args.source, args.limit)
    write_json(payload, Path(args.out))
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
