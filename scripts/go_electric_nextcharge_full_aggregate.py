#!/usr/bin/env python3
"""Aggregate all Go Electric full-extraction shards into one QA artifact."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_SHARDS = 8
EXPECTED_STATIONS = 1136
EXPECTED_EVSES = 2413


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    # Only canonical national shard files are valid inputs. Recovery part/slot
    # artifacts deliberately share the shard prefix and must never enter the
    # national aggregation.
    files = [Path(f"artifacts/go_electric_full_shard_{index:02d}.json") for index in range(EXPECTED_SHARDS)]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise SystemExit(f"missing canonical national shard files: {missing}")

    shards = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    indices = sorted(x["shard"]["index"] for x in shards)
    if indices != list(range(EXPECTED_SHARDS)):
        raise SystemExit(f"unexpected shard indices: {indices}")

    results = [row for shard in shards for row in shard.get("results", [])]
    station_ids = [row["pun"]["stationId"] for row in results]
    if len(station_ids) != EXPECTED_STATIONS:
        raise SystemExit(f"expected {EXPECTED_STATIONS} stations, got {len(station_ids)}")
    if len(set(station_ids)) != len(station_ids):
        duplicates = [sid for sid, count in Counter(station_ids).items() if count > 1]
        raise SystemExit(f"duplicate station ids across shards: {duplicates[:20]}")

    target_evses = sum(len(row["pun"]["evses"]) for row in results)
    if target_evses != EXPECTED_EVSES:
        raise SystemExit(f"expected {EXPECTED_EVSES} target EVSE, got {target_evses}")

    exact = [row for row in results if row.get("uniqueExactStationMatch")]
    quarantine = [row for row in results if not row.get("uniqueExactStationMatch")]
    exact_connectors = [c for row in exact for c in row.get("exactConnectorMatches", [])]
    tariffed = [c for c in exact_connectors if (c.get("tariff") or {}).get("prices")]
    power_checked = [c for c in exact_connectors if c.get("powerCompatible") is not None]
    power_ok = [c for c in power_checked if c.get("powerCompatible") is True]

    quarantine_reasons = Counter()
    for row in quarantine:
        if row.get("gridHttpStatus") != 200:
            quarantine_reasons["grid_read_failure"] += 1
        elif row.get("exactCandidateCount", 0) == 0:
            quarantine_reasons["no_exact_connector_identity"] += 1
        elif row.get("exactCandidateCount", 0) > 1:
            quarantine_reasons["ambiguous_multiple_exact_candidates"] += 1
        else:
            quarantine_reasons["other"] += 1

    class_stats = defaultdict(lambda: {
        "stations": 0,
        "exactStations": 0,
        "quarantinedStations": 0,
        "targetEvses": 0,
        "exactConnectors": 0,
        "tariffedConnectors": 0,
    })
    for row in results:
        cls = row["pun"].get("powerClass") or "unknown"
        class_stats[cls]["stations"] += 1
        class_stats[cls]["targetEvses"] += len(row["pun"].get("evses", []))
        if row.get("uniqueExactStationMatch"):
            class_stats[cls]["exactStations"] += 1
            matches = row.get("exactConnectorMatches", [])
            class_stats[cls]["exactConnectors"] += len(matches)
            class_stats[cls]["tariffedConnectors"] += sum(bool((c.get("tariff") or {}).get("prices")) for c in matches)
        else:
            class_stats[cls]["quarantinedStations"] += 1

    accepted = []
    for row in exact:
        accepted.append({
            "punStationId": row["pun"]["stationId"],
            "name": row["pun"].get("name"),
            "address": row["pun"].get("address"),
            "lat": row["pun"].get("lat"),
            "lon": row["pun"].get("lon"),
            "powerClass": row["pun"].get("powerClass"),
            "nextChargeStationId": row.get("matchedNextChargeStationId"),
            "distanceM": row.get("matchedDistanceM"),
            "connectors": row.get("exactConnectorMatches", []),
        })

    quarantine_rows = []
    for row in quarantine:
        quarantine_rows.append({
            "punStationId": row["pun"]["stationId"],
            "name": row["pun"].get("name"),
            "address": row["pun"].get("address"),
            "lat": row["pun"].get("lat"),
            "lon": row["pun"].get("lon"),
            "powerClass": row["pun"].get("powerClass"),
            "gridHttpStatus": row.get("gridHttpStatus"),
            "gridError": row.get("gridError"),
            "exactCandidateCount": row.get("exactCandidateCount"),
            "candidateCountWithinThreshold": row.get("candidateCountWithinThreshold"),
            "expectedPunEvseSuffixes": row.get("expectedPunEvseSuffixes"),
            "candidates": row.get("candidates"),
        })

    request_count = sum(shard.get("requestAudit", {}).get("requestCount", 0) for shard in shards)
    endpoints = sorted({endpoint for shard in shards for endpoint in shard.get("requestAudit", {}).get("endpoints", [])})
    all_read_only = all(shard.get("requestAudit", {}).get("allRequestsDeclaredReadOnly") is True for shard in shards)

    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "catalogueBaseline": {"stationCount": EXPECTED_STATIONS, "evseCount": EXPECTED_EVSES},
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "fullNationalExtraction": True,
            "allShardsPresent": True,
            "exactPunEvseSuffixRequiredForAttribution": True,
            "coordinateOnlyAttributionAllowed": False,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
            "accountActionsAllowed": False,
            "sessionMutationAllowed": False,
            "directCpoPublicationAllowed": False,
            "publicationReason": "national_extraction_complete_but_quarantine_and_tariff_semantics_qa_required",
        },
        "summary": {
            "processedStations": len(results),
            "gridSuccessStations": sum(row.get("gridHttpStatus") == 200 for row in results),
            "exactMatchedStations": len(exact),
            "quarantinedStations": len(quarantine),
            "exactStationMatchRate": round(len(exact) / len(results), 6) if results else 0.0,
            "targetPunEvses": target_evses,
            "exactConnectorMatches": len(exact_connectors),
            "tariffedExactConnectors": len(tariffed),
            "tariffCoverageOnExactConnectors": round(len(tariffed) / len(exact_connectors), 6) if exact_connectors else 0.0,
            "powerCheckedExactConnectors": len(power_checked),
            "powerCompatibleExactConnectors": len(power_ok),
            "powerCompatibilityRate": round(len(power_ok) / len(power_checked), 6) if power_checked else 0.0,
            "quarantineReasons": dict(quarantine_reasons),
            "classBreakdown": dict(class_stats),
        },
        "requestAudit": {
            "requestCount": request_count,
            "endpoints": endpoints,
            "allRequestsDeclaredReadOnly": all_read_only,
        },
        "acceptedExactTariffs": accepted,
        "quarantine": quarantine_rows,
    }

    out = Path("artifacts/go_electric_italy_v9_full_extraction.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "requestAudit": report["requestAudit"], "publicationAllowed": False}, indent=2))

    if not all_read_only:
        raise SystemExit("not all shard requests were read-only")
    if report["summary"]["processedStations"] != EXPECTED_STATIONS:
        raise SystemExit("national station coverage incomplete")


if __name__ == "__main__":
    main()
