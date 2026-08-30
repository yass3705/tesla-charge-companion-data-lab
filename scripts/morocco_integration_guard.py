#!/usr/bin/env python3
"""Offline guardrails for Morocco non-Tesla TCC candidate datasets.

This script performs no network requests and requires no credentials. It validates a
normalized JSON candidate before integration, preserving source-model dimensions and
failing closed on EVOne roaming statuses.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_SOURCE_FIELDS = (
    "cpo_operator",
    "site_brand",
    "app_source_access_network",
    "tariff_channel",
    "status_source",
)

EVONE_ALLOWED = {"available", "occupied", "charging"}
EVONE_EXCLUDED = {"faulted", "offline", "unknown", "unavailable"}


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def rows_from(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("stations", "evses", "connectors", "records", "production_candidates"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    raise ValueError("Unsupported candidate shape: expected list or object containing stations/evses/connectors/records/production_candidates")


def is_evone(row: dict[str, Any]) -> bool:
    hay = " ".join(
        norm(row.get(k))
        for k in ("app_source_access_network", "status_source", "tariff_channel")
    )
    return "evone" in hay or "evplug" in hay


def is_production(row: dict[str, Any]) -> bool:
    if row.get("production_candidate") is False:
        return False
    if norm(row.get("dataset_scope")) == "diagnostic":
        return False
    return True


def status_of(row: dict[str, Any]) -> str:
    for key in ("normalized_status", "status"):
        if row.get(key) is not None:
            return norm(row[key])
    return ""


def validate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    status_counts = Counter()

    for idx, row in enumerate(rows):
        rid = row.get("id") or row.get("station_id") or row.get("evse_id") or idx
        missing = [k for k in REQUIRED_SOURCE_FIELDS if k not in row]
        if missing:
            violations.append({"record": rid, "rule": "source_dimensions_present", "missing": missing})

        if not is_production(row):
            continue

        st = status_of(row)
        if st:
            status_counts[st] += 1

        if is_evone(row):
            if st in EVONE_EXCLUDED:
                violations.append({
                    "record": rid,
                    "rule": "evone_production_status_whitelist",
                    "status": st,
                    "reason": "EVOne Faulted/Offline/Unknown/Unavailable are diagnostic-only",
                })
            elif st and st not in EVONE_ALLOWED:
                violations.append({
                    "record": rid,
                    "rule": "evone_unknown_production_status_fail_closed",
                    "status": st,
                    "reason": "Only Available/Occupied/Charging may enter production",
                })
            elif not st:
                violations.append({
                    "record": rid,
                    "rule": "evone_missing_status_fail_closed",
                    "reason": "EVOne production candidates require an allowed live status",
                })

        # Avoid accidental CPO attribution from the site brand alone.
        if norm(row.get("cpo_operator")) == norm(row.get("site_brand")) and row.get("cpo_operator"):
            evidence = norm(row.get("cpo_evidence")) or norm(row.get("operator_evidence"))
            if not evidence:
                warnings.append({
                    "record": rid,
                    "rule": "cpo_not_inferred_from_site_brand",
                    "message": "CPO equals site_brand but no explicit attribution evidence field is present",
                })

        # Native CPO status must not be silently replaced by EVOne roaming on overlapping EVGO records.
        cpo = norm(row.get("cpo_operator"))
        status_source = norm(row.get("status_source"))
        app_source = norm(row.get("app_source_access_network"))
        if ("evgo" in cpo or "nareva" in cpo) and ("evone" in status_source or "evplug" in status_source):
            violations.append({
                "record": rid,
                "rule": "native_status_priority",
                "reason": "EVGO/Nareva production status must prefer cp.evgo.ma native status over EVOne roaming when native data exists",
            })
        if ("evgo" in cpo or "nareva" in cpo) and app_source and "evgo" not in app_source and "nareva" not in app_source:
            warnings.append({
                "record": rid,
                "rule": "evgo_access_network_review",
                "message": "EVGO/Nareva CPO record uses a non-EVGO access network; verify roaming intent",
            })

    return {
        "schema_version": 1,
        "policy": {
            "offline_only": True,
            "network_requests": False,
            "credentials_required": False,
            "read_only": True,
            "evone_production_allowed_statuses": sorted(EVONE_ALLOWED),
            "evone_diagnostic_only_statuses": sorted(EVONE_EXCLUDED),
            "required_source_dimensions": list(REQUIRED_SOURCE_FIELDS),
            "native_status_priority": "native CPO > official static operator > EVOne/EVPlug roaming",
        },
        "summary": {
            "records_checked": len(rows),
            "violations": len(violations),
            "warnings": len(warnings),
            "production_status_counts": dict(sorted(status_counts.items())),
            "pass": not violations,
        },
        "violations": violations,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="Normalized Morocco candidate JSON")
    ap.add_argument("--output", type=Path, help="Optional JSON validation report")
    args = ap.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = validate(rows_from(payload))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if result["summary"]["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
