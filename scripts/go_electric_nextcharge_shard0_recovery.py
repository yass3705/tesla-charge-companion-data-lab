#!/usr/bin/env python3
"""Recover only the stalled Go Electric national shard 0 in smaller subshards.

The original national extraction uses 8 deterministic shards. This utility
reprocesses only original shard 0, split into 8 smaller parts, then can merge
those parts back into the exact original shard-0 artifact shape expected by the
existing national aggregator. Publication remains disabled.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from go_electric_nextcharge_national_batch_probe import TARGET_OPERATOR, load_catalogue, parse_go_electric, probe_target

PARENT_SHARD_COUNT = 8
PARENT_SHARD_INDEX = 0
SUBSHARD_COUNT = int(os.environ.get("GO_ELECTRIC_RECOVERY_PART_COUNT", "8"))
SUBSHARD_INDEX = int(os.environ.get("GO_ELECTRIC_RECOVERY_PART_INDEX", "0"))
REQUEST_PAUSE_SECONDS = float(os.environ.get("GO_ELECTRIC_REQUEST_PAUSE_SECONDS", "0.03"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def baseline() -> list[dict]:
    catalogue = sorted(parse_go_electric(load_catalogue()), key=lambda x: x["stationId"])
    if len(catalogue) != 1136:
        raise SystemExit(f"unexpected station baseline: {len(catalogue)}")
    if sum(len(x["evses"]) for x in catalogue) != 2413:
        raise SystemExit("unexpected EVSE baseline")
    return catalogue


def summarize(results: list[dict]) -> tuple[dict, dict]:
    exact = [r for r in results if r.get("uniqueExactStationMatch")]
    quarantine = [r for r in results if not r.get("uniqueExactStationMatch")]
    exact_connectors = [c for r in exact for c in r.get("exactConnectorMatches", [])]
    tariffed = [c for c in exact_connectors if (c.get("tariff") or {}).get("prices")]
    power_checked = [c for c in exact_connectors if c.get("powerCompatible") is not None]
    power_ok = [c for c in power_checked if c.get("powerCompatible") is True]
    reasons = Counter()
    for row in quarantine:
        if row.get("gridHttpStatus") != 200:
            reasons["grid_read_failure"] += 1
        elif row.get("exactCandidateCount", 0) == 0:
            reasons["no_exact_connector_identity"] += 1
        elif row.get("exactCandidateCount", 0) > 1:
            reasons["ambiguous_multiple_exact_candidates"] += 1
        else:
            reasons["other"] += 1
    return ({
        "processedStations": len(results),
        "gridSuccessStations": sum(r.get("gridHttpStatus") == 200 for r in results),
        "exactMatchedStations": len(exact),
        "quarantinedStations": len(quarantine),
        "targetPunEvses": sum(len(r["pun"]["evses"]) for r in results),
        "exactConnectorMatches": len(exact_connectors),
        "tariffedExactConnectors": len(tariffed),
        "powerCheckedExactConnectors": len(power_checked),
        "powerCompatibleExactConnectors": len(power_ok),
        "quarantineReasons": dict(reasons),
    }, {"exact": exact, "quarantine": quarantine})


def policy(reason: str) -> dict:
    return {
        "readOnly": True,
        "authenticated": False,
        "remoteMutation": False,
        "fullNationalExtraction": True,
        "sharded": True,
        "targetedRecovery": True,
        "exactPunEvseSuffixRequiredForAttribution": True,
        "coordinateOnlyAttributionAllowed": False,
        "chargingActionsAllowed": False,
        "paymentActionsAllowed": False,
        "reservationActionsAllowed": False,
        "accountActionsAllowed": False,
        "sessionMutationAllowed": False,
        "directCpoPublicationAllowed": False,
        "publicationReason": reason,
    }


def extract_part() -> None:
    if SUBSHARD_COUNT != 8 or not 0 <= SUBSHARD_INDEX < SUBSHARD_COUNT:
        raise SystemExit(f"invalid recovery part {SUBSHARD_INDEX}/{SUBSHARD_COUNT}")
    catalogue = baseline()
    parent = [station for idx, station in enumerate(catalogue) if idx % PARENT_SHARD_COUNT == PARENT_SHARD_INDEX]
    if len(parent) != 142:
        raise SystemExit(f"unexpected original shard-0 size: {len(parent)}")
    targets = [station for idx, station in enumerate(parent) if idx % SUBSHARD_COUNT == SUBSHARD_INDEX]
    request_log: list[dict] = []
    results: list[dict] = []
    for offset, station in enumerate(targets, start=1):
        result = probe_target(station, request_log)
        results.append(result)
        print(json.dumps({
            "parentShard": 0,
            "part": SUBSHARD_INDEX,
            "progress": offset,
            "total": len(targets),
            "stationId": station["stationId"],
            "exact": result.get("uniqueExactStationMatch"),
            "gridStatus": result.get("gridHttpStatus"),
        }), flush=True)
        if REQUEST_PAUSE_SECONDS:
            time.sleep(REQUEST_PAUSE_SECONDS)
    summary, _ = summarize(results)
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "targetOperator": TARGET_OPERATOR,
        "catalogueBaseline": {"stationCount": 1136, "evseCount": 2413},
        "parentShard": {"index": 0, "count": 8, "stationCount": 142},
        "recoveryPart": {"index": SUBSHARD_INDEX, "count": SUBSHARD_COUNT, "stationCount": len(targets)},
        "policy": policy("targeted_shard0_recovery_requires_merge_and_national_qa"),
        "summary": summary,
        "requestAudit": {
            "requestCount": len(request_log),
            "endpoints": sorted({r["endpoint"] for r in request_log}),
            "allRequestsDeclaredReadOnly": all(r.get("readOnly") is True for r in request_log),
        },
        "results": results,
    }
    out = Path(f"artifacts/go_electric_full_shard_00_part_{SUBSHARD_INDEX:02d}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"recoveryPart": report["recoveryPart"], "summary": summary}, indent=2))
    if not report["requestAudit"]["allRequestsDeclaredReadOnly"]:
        raise SystemExit("non-read-only request detected")


def merge_parts() -> None:
    files = sorted(Path("artifacts").glob("go_electric_full_shard_00_part_*.json"))
    if len(files) != 8:
        raise SystemExit(f"expected 8 recovery parts, found {len(files)}")
    parts = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    indices = sorted(p["recoveryPart"]["index"] for p in parts)
    if indices != list(range(8)):
        raise SystemExit(f"unexpected recovery part indices: {indices}")
    results = [row for part in parts for row in part.get("results", [])]
    station_ids = [r["pun"]["stationId"] for r in results]
    if len(station_ids) != 142 or len(set(station_ids)) != 142:
        raise SystemExit(f"recovered shard 0 coverage invalid: total={len(station_ids)} unique={len(set(station_ids))}")
    expected = [s["stationId"] for idx, s in enumerate(baseline()) if idx % 8 == 0]
    if sorted(station_ids) != sorted(expected):
        raise SystemExit("recovered station set differs from deterministic original shard 0")
    summary, _ = summarize(results)
    request_count = sum(p.get("requestAudit", {}).get("requestCount", 0) for p in parts)
    endpoints = sorted({e for p in parts for e in p.get("requestAudit", {}).get("endpoints", [])})
    all_read_only = all(p.get("requestAudit", {}).get("allRequestsDeclaredReadOnly") is True for p in parts)
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "targetOperator": TARGET_OPERATOR,
        "catalogueBaseline": {"stationCount": 1136, "evseCount": 2413},
        "shard": {"index": 0, "count": 8, "stationCount": 142},
        "policy": policy("recovered_shard0_requires_post_run_national_qa"),
        "summary": summary,
        "requestAudit": {"requestCount": request_count, "endpoints": endpoints, "allRequestsDeclaredReadOnly": all_read_only},
        "results": results,
        "recovery": {"partCount": 8, "exactOriginalStationSet": True},
    }
    out = Path("artifacts/go_electric_full_shard_00.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"shard": report["shard"], "summary": summary, "recovery": report["recovery"]}, indent=2))
    if not all_read_only:
        raise SystemExit("non-read-only request detected across recovery parts")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "merge":
        merge_parts()
    else:
        extract_part()
