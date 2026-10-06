#!/usr/bin/env python3
"""Keep the daily IRVE dynamic state separate from the static station inventory."""
import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://proxy.transport.data.gouv.fr/resource/consolidation-nationale-irve-dynamique"
STATES = {"en_service", "hors_service", "inconnu"}


def build(static_rows, dynamic_csv, retrieved_at):
    station_by_pdc = {}
    for station in static_rows:
        for group in station[8]:
            for pdc in group[6]:
                if pdc in station_by_pdc and station_by_pdc[pdc] != station[0]:
                    raise ValueError(f"PDC belongs to two stations: {pdc}")
                station_by_pdc[pdc] = station[0]
    latest = {}
    counts = Counter()
    with dynamic_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"id_pdc_itinerance", "etat_pdc", "horodatage"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Dynamic IRVE columns missing: {required - set(reader.fieldnames or [])}")
        for row in reader:
            counts["sourceRows"] += 1
            pdc = (row.get("id_pdc_itinerance") or "").strip()
            state = (row.get("etat_pdc") or "").strip().lower()
            timestamp = (row.get("horodatage") or "").strip()
            if not pdc or state not in STATES or not timestamp:
                counts["invalidRows"] += 1
                continue
            station_id = station_by_pdc.get(pdc)
            if not station_id:
                counts["unmatchedPdc"] += 1
                continue
            value = {"id_station_itinerance": station_id, "id_pdc_itinerance": pdc, "etat_pdc": state, "horodatage": timestamp}
            if pdc not in latest or timestamp > latest[pdc]["horodatage"]:
                latest[pdc] = value
    counts.update(row["etat_pdc"] for row in latest.values())
    records = sorted((row for row in latest.values() if row["etat_pdc"] != "en_service"), key=lambda row: (row["id_station_itinerance"], row["id_pdc_itinerance"]))
    return {
        "schemaVersion": 1,
        "country": "FR",
        "generatedAt": retrieved_at,
        "sourceUrl": SOURCE_URL,
        "sourceSha256": hashlib.sha256(dynamic_csv.read_bytes()).hexdigest(),
        "sourceRows": counts["sourceRows"],
        "matchedPdc": len(latest),
        "displayExcludedPdc": len(records),
        "unmatchedPdc": counts["unmatchedPdc"],
        "invalidRows": counts["invalidRows"],
        "states": {state: counts[state] for state in sorted(STATES)},
        "policy": "Dynamic state is a daily display flag; static IRVE rows are retained.",
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-all", type=Path, required=True)
    parser.add_argument("--dynamic-csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--retrieved-at", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    with gzip.open(args.static_all, "rt", encoding="utf-8") as stream:
        payload = build(json.load(stream), args.dynamic_csv, args.retrieved_at)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with args.out.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, compresslevel=9, mtime=0) as output:
            output.write(raw)
    print(json.dumps({key: payload[key] for key in ("generatedAt", "sourceRows", "matchedPdc", "unmatchedPdc", "invalidRows", "states")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
