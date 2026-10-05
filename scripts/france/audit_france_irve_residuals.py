#!/usr/bin/env python3
"""Exact-ID audit of France residual EVSEs against current national IRVE sources."""
import argparse
import csv
import gzip
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DYNAMIC_URL = "https://proxy.transport.data.gouv.fr/resource/consolidation-nationale-irve-dynamique"


def norm(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def open_json(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--static-all", required=True)
    ap.add_argument("--static-manifest", required=True)
    ap.add_argument("--dynamic-csv", required=True)
    ap.add_argument("--residuals", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    static_rows = open_json(args.static_all)
    static_ids = set()
    for station in static_rows:
        if len(station) > 8:
            for group in station[8] or []:
                if len(group) > 6:
                    static_ids.update(norm(x) for x in (group[6] or []) if norm(x))

    dyn_path = Path(args.dynamic_csv)
    dynamic_sha = hashlib.sha256(dyn_path.read_bytes()).hexdigest()
    dynamic_rows = 0
    dynamic_ids = set()
    with dyn_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        header_map = {re.sub(r"[^a-z0-9]", "", str(k or "").lower()): k for k in (reader.fieldnames or [])}
        id_col = header_map.get("idpdcitinerance")
        if not id_col:
            raise SystemExit("Dynamic IRVE CSV lacks id_pdc_itinerance")
        for row in reader:
            dynamic_rows += 1
            item = norm(row.get(id_col))
            if item:
                dynamic_ids.add(item)

    residual_sha = hashlib.sha256(Path(args.residuals).read_bytes()).hexdigest()
    residual_payload = open_json(args.residuals)
    locations = residual_payload.get("locations", [])
    by_cpo = defaultdict(lambda: {
        "locations": 0, "locationsStatic": 0, "locationsDynamic": 0,
        "locationsEither": 0, "locationsUnmatched": 0, "evses": 0,
        "evsesStatic": 0, "evsesDynamic": 0, "evsesDynamicOnly": 0,
        "evsesEither": 0, "evsesUnmatched": 0, "unmatchedExamples": []
    })
    for location in locations:
        cpo = str(location.get("cpo") or "(non renseigné)").strip()
        evse_ids = list(dict.fromkeys(norm(e.get("evseId")) for e in location.get("evses", []) if norm(e.get("evseId"))))
        if not evse_ids:
            continue
        static_hits = [x for x in evse_ids if x in static_ids]
        dynamic_hits = [x for x in evse_ids if x in dynamic_ids]
        either_hits = set(static_hits) | set(dynamic_hits)
        row = by_cpo[cpo]
        row["locations"] += 1
        row["evses"] += len(evse_ids)
        row["evsesStatic"] += len(static_hits)
        row["evsesDynamic"] += len(dynamic_hits)
        row["evsesDynamicOnly"] += sum(1 for x in dynamic_hits if x not in static_ids)
        row["evsesEither"] += len(either_hits)
        row["evsesUnmatched"] += len(evse_ids) - len(either_hits)
        if static_hits:
            row["locationsStatic"] += 1
        if dynamic_hits:
            row["locationsDynamic"] += 1
        if either_hits:
            row["locationsEither"] += 1
        else:
            row["locationsUnmatched"] += 1
            if len(row["unmatchedExamples"]) < 8:
                row["unmatchedExamples"].append({
                    "name": location.get("name"),
                    "city": location.get("city"),
                    "postalCode": location.get("postalCode"),
                    "evseIds": [e.get("evseId") for e in location.get("evses", []) if e.get("evseId")]
                })

    total = {k: sum(row[k] for row in by_cpo.values()) for k in (
        "locations", "locationsStatic", "locationsDynamic", "locationsEither",
        "locationsUnmatched", "evses", "evsesStatic", "evsesDynamic",
        "evsesDynamicOnly", "evsesEither", "evsesUnmatched"
    )}
    for row in by_cpo.values():
        row["evseMatchRatePercent"] = round(100 * row["evsesEither"] / row["evses"], 2) if row["evses"] else 0
    manifest = json.loads(Path(args.static_manifest).read_text(encoding="utf-8"))
    result = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": "exact EVSE ID only after uppercase alphanumeric normalization; no geographic or fuzzy matches",
        "normalization": "FRCPIE6887515*1 and FRCPIE68875151 resolve to the same normalized identifier",
        "sources": {
            "static": {"url": manifest.get("sourceUrl"), "sourceRetrievedAt": manifest.get("sourceRetrievedAt"), "sourceSha256": manifest.get("sourceSha256"), "stationCount": manifest.get("stationCount"), "pdcCount": manifest.get("pdcCount")},
            "dynamic": {"url": DYNAMIC_URL, "rows": dynamic_rows, "uniqueIds": len(dynamic_ids), "sha256": dynamic_sha},
            "residualSnapshotGeneratedAt": residual_payload.get("generatedAt"),
            "residualSnapshotSha256": residual_sha
        },
        "totals": total,
        "byCpo": dict(sorted(by_cpo.items(), key=lambda item: (-item[1]["evses"], item[0].casefold())))
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"totals": total, "cpoCount": len(by_cpo), "electra": by_cpo.get("Electra")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
