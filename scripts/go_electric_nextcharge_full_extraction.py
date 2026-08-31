#!/usr/bin/env python3
"""Full read-only Go Electric Italy V9 tariff extraction, one deterministic shard.

The extraction reuses the bounded national probe's already validated public-read
functions. It does not publish data. Exact PUN `ITGESE...` EVSE suffix ↔
NextCharge `uidConnector` identity is mandatory for attribution; every other
station is quarantined for review.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from go_electric_nextcharge_national_batch_probe import (
    TARGET_OPERATOR,
    load_catalogue,
    parse_go_electric,
    probe_target,
)

SHARD_COUNT = int(os.environ.get("GO_ELECTRIC_SHARD_COUNT", "8"))
SHARD_INDEX = int(os.environ.get("GO_ELECTRIC_SHARD_INDEX", "0"))
REQUEST_PAUSE_SECONDS = float(os.environ.get("GO_ELECTRIC_REQUEST_PAUSE_SECONDS", "0.05"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    if SHARD_COUNT < 1 or SHARD_COUNT > 32:
        raise SystemExit(f"invalid shard count: {SHARD_COUNT}")
    if SHARD_INDEX < 0 or SHARD_INDEX >= SHARD_COUNT:
        raise SystemExit(f"invalid shard index: {SHARD_INDEX}/{SHARD_COUNT}")

    catalogue = sorted(parse_go_electric(load_catalogue()), key=lambda x: x["stationId"])
    if len(catalogue) != 1136:
        raise SystemExit(f"unexpected Go Electric station baseline: {len(catalogue)}")
    evse_count = sum(len(x["evses"]) for x in catalogue)
    if evse_count != 2413:
        raise SystemExit(f"unexpected Go Electric EVSE baseline: {evse_count}")

    targets = [station for index, station in enumerate(catalogue) if index % SHARD_COUNT == SHARD_INDEX]
    request_log: list[dict] = []
    results: list[dict] = []

    for offset, station in enumerate(targets, start=1):
        result = probe_target(station, request_log)
        results.append(result)
        print(json.dumps({
            "shard": SHARD_INDEX,
            "progress": offset,
            "total": len(targets),
            "stationId": station["stationId"],
            "exact": result.get("uniqueExactStationMatch"),
            "exactConnectors": len(result.get("exactConnectorMatches") or []),
            "gridStatus": result.get("gridHttpStatus"),
        }, ensure_ascii=False), flush=True)
        if REQUEST_PAUSE_SECONDS > 0:
            time.sleep(REQUEST_PAUSE_SECONDS)

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

    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "targetOperator": TARGET_OPERATOR,
        "catalogueBaseline": {"stationCount": len(catalogue), "evseCount": evse_count},
        "shard": {"index": SHARD_INDEX, "count": SHARD_COUNT, "stationCount": len(targets)},
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "fullNationalExtraction": True,
            "sharded": True,
            "exactPunEvseSuffixRequiredForAttribution": True,
            "coordinateOnlyAttributionAllowed": False,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
            "accountActionsAllowed": False,
            "sessionMutationAllowed": False,
            "directCpoPublicationAllowed": False,
            "publicationReason": "full_extraction_requires_post_run_national_qa",
        },
        "summary": {
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
        },
        "requestAudit": {
            "requestCount": len(request_log),
            "endpoints": sorted({r["endpoint"] for r in request_log}),
            "allRequestsDeclaredReadOnly": all(r.get("readOnly") is True for r in request_log),
        },
        "results": results,
    }

    out = Path(f"artifacts/go_electric_full_shard_{SHARD_INDEX:02d}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"shard": report["shard"], "summary": report["summary"], "requestAudit": report["requestAudit"]}, indent=2))

    if len(results) != len(targets):
        raise SystemExit("not all shard targets were processed")
    if not report["requestAudit"]["allRequestsDeclaredReadOnly"]:
        raise SystemExit("request audit contains a non-read-only request")


if __name__ == "__main__":
    main()
