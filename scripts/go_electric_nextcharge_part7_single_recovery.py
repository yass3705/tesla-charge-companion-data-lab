#!/usr/bin/env python3
"""Deep recovery for original shard-0 recovery part 7, one station per job.

This is a fail-closed escape hatch for unusually slow NextCharge reads. It caps
NextCharge HTTP reads to a short timeout, so a slow station becomes a normal
quarantine result rather than blocking the whole national extraction.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import go_electric_nextcharge_national_batch_probe as probe
from go_electric_nextcharge_shard0_recovery import baseline, policy, summarize

SLOT_COUNT = 17
SLOT_INDEX = int(os.environ.get("GO_ELECTRIC_PART7_SLOT", "0"))
SHORT_TIMEOUT = float(os.environ.get("GO_ELECTRIC_SHORT_TIMEOUT_SECONDS", "6"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def part7_targets() -> list[dict]:
    catalogue = baseline()
    parent = [station for idx, station in enumerate(catalogue) if idx % 8 == 0]
    if len(parent) != 142:
        raise SystemExit(f"unexpected parent shard size: {len(parent)}")
    rows = [station for idx, station in enumerate(parent) if idx % 8 == 7]
    if len(rows) != SLOT_COUNT:
        raise SystemExit(f"unexpected recovery part-7 size: {len(rows)}")
    return rows


def install_timeout_cap() -> None:
    original = probe.urllib.request.urlopen

    def capped(req, *args, **kwargs):
        url = getattr(req, "full_url", str(req))
        host = (urlparse(url).hostname or "").lower()
        if host == "nextcharge.app" or host.endswith(".nextcharge.app"):
            supplied = kwargs.get("timeout")
            if supplied is None and args:
                supplied = args[0]
            cap = SHORT_TIMEOUT if supplied is None else min(float(supplied), SHORT_TIMEOUT)
            kwargs["timeout"] = cap
            if args:
                args = args[1:]
        return original(req, *args, **kwargs)

    probe.urllib.request.urlopen = capped


def extract_slot() -> None:
    if not 0 <= SLOT_INDEX < SLOT_COUNT:
        raise SystemExit(f"invalid slot {SLOT_INDEX}/{SLOT_COUNT}")
    target = part7_targets()[SLOT_INDEX]
    install_timeout_cap()
    request_log: list[dict] = []
    result = probe.probe_target(target, request_log)
    summary, _ = summarize([result])
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "targetOperator": probe.TARGET_OPERATOR,
        "catalogueBaseline": {"stationCount": 1136, "evseCount": 2413},
        "parentShard": {"index": 0, "count": 8, "stationCount": 142},
        "recoveryPart": {"index": 7, "count": 8, "stationCount": SLOT_COUNT},
        "deepRecoverySlot": {"index": SLOT_INDEX, "count": SLOT_COUNT, "stationCount": 1},
        "policy": {
            **policy("deep_part7_recovery_requires_merge_and_national_qa"),
            "shortReadTimeoutSeconds": SHORT_TIMEOUT,
            "timeoutMeansQuarantineNotAttribution": True,
        },
        "summary": summary,
        "requestAudit": {
            "requestCount": len(request_log),
            "endpoints": sorted({r["endpoint"] for r in request_log}),
            "allRequestsDeclaredReadOnly": all(r.get("readOnly") is True for r in request_log),
        },
        "results": [result],
    }
    out = Path(f"artifacts/go_electric_full_shard_00_part_07_slot_{SLOT_INDEX:02d}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "slot": report["deepRecoverySlot"],
        "stationId": target["stationId"],
        "summary": summary,
        "gridStatus": result.get("gridHttpStatus"),
        "gridError": result.get("gridError"),
    }, indent=2))
    if not report["requestAudit"]["allRequestsDeclaredReadOnly"]:
        raise SystemExit("non-read-only request detected")


def merge_slots() -> None:
    files = sorted(Path("artifacts").glob("go_electric_full_shard_00_part_07_slot_*.json"))
    if len(files) != SLOT_COUNT:
        raise SystemExit(f"expected {SLOT_COUNT} deep recovery slots, found {len(files)}")
    slots = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    indices = sorted(x["deepRecoverySlot"]["index"] for x in slots)
    if indices != list(range(SLOT_COUNT)):
        raise SystemExit(f"unexpected deep slot indices: {indices}")
    results = [row for slot in slots for row in slot.get("results", [])]
    expected_ids = sorted(x["stationId"] for x in part7_targets())
    actual_ids = sorted(row["pun"]["stationId"] for row in results)
    if actual_ids != expected_ids:
        raise SystemExit("deep recovery station set differs from deterministic part 7")
    summary, _ = summarize(results)
    request_count = sum(x.get("requestAudit", {}).get("requestCount", 0) for x in slots)
    endpoints = sorted({e for x in slots for e in x.get("requestAudit", {}).get("endpoints", [])})
    all_read_only = all(x.get("requestAudit", {}).get("allRequestsDeclaredReadOnly") is True for x in slots)
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "targetOperator": probe.TARGET_OPERATOR,
        "catalogueBaseline": {"stationCount": 1136, "evseCount": 2413},
        "parentShard": {"index": 0, "count": 8, "stationCount": 142},
        "recoveryPart": {"index": 7, "count": 8, "stationCount": SLOT_COUNT},
        "policy": {
            **policy("deep_part7_recovered_requires_shard0_merge_and_national_qa"),
            "shortReadTimeoutSeconds": SHORT_TIMEOUT,
            "timeoutMeansQuarantineNotAttribution": True,
        },
        "summary": summary,
        "requestAudit": {"requestCount": request_count, "endpoints": endpoints, "allRequestsDeclaredReadOnly": all_read_only},
        "results": results,
        "deepRecovery": {"slotCount": SLOT_COUNT, "exactDeterministicStationSet": True},
    }
    out = Path("artifacts/go_electric_full_shard_00_part_07.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"recoveryPart": report["recoveryPart"], "summary": summary, "deepRecovery": report["deepRecovery"]}, indent=2))
    if not all_read_only:
        raise SystemExit("non-read-only request detected across deep recovery slots")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "merge":
        merge_slots()
    else:
        extract_slot()
