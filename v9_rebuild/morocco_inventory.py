#!/usr/bin/env python3
"""Run preserved Morocco public-map inventories outside the Git checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

METHODS = {
    "fastvolt": ("scripts/morocco/extract_fastvolt_public_map_chargers.py",
                 "reports/morocco/fastvolt/latest-public-map-inventory.json"),
    "kilowatt": ("scripts/morocco/kilowatt_public_station_inventory.py",
                  "reports/morocco/kilowatt/latest-public-station-inventory.json"),
}
RECONCILIATION = ("scripts/morocco/kilowatt_location_reconciliation.py",
                  "artifacts/morocco-kilowatt-location-reconciliation/summary.json")
TARIFF_OVERLAY = ("scripts/morocco_kilowatt_build_v9_tariff_overlay.py",
                  "reports/morocco/kilowatt/latest-v9-tariff-overlay.json")
TARIFF_EVIDENCE = "reports/morocco/kilowatt/public-free-tariff-evidence-2026-08-24.json"


def validate_output(out: Path, method: str) -> dict:
    if method not in METHODS:
        raise ValueError("Unknown Morocco inventory method")
    report = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
    summary = report.get("summary") or {}
    policy = report.get("policy") or {}
    modeling = report.get("modeling") or {}
    if method == "fastvolt":
        rows = report.get("chargers")
        if (report.get("schema_version") != 3 or report.get("country") != "MA"
                or report.get("source_url") != "https://www.fastvolt.net/api/pages"
                or report.get("http_status") != 200 or report.get("truncated") is not False
                or policy.get("read_only") is not True or policy.get("get_only") is not True
                or policy.get("raw_response_body_persisted") is not False
                or policy.get("credentials_or_personal_data_persisted") is not False
                or modeling.get("site_brand") is not None or modeling.get("status_source") is not None
                or not isinstance(rows, list)
                or summary.get("charger_count") != len(rows)
                or summary.get("production_candidate_count") != sum(row.get("production_candidate") is True for row in rows)
                or summary.get("production_excluded_count") != sum(row.get("production_candidate") is False for row in rows)
                or any(row.get("cpo_operator") != "FastVolt / Afrimobility"
                       or row.get("status_source") is not None or row.get("site_brand") is not None
                       or row.get("tariff_channel") != "FastVolt direct" for row in rows)):
            raise ValueError("FastVolt public inventory contract invalid")
    else:
        rows = report.get("stations")
        if (report.get("schema_version") != 2 or report.get("source") != "https://kilowatt.ma/api/charging-stations"
                or policy.get("read_only") is not True
                or policy.get("public_get_only") is not True
                or modeling.get("cpo_operator") != "Kilowatt"
                or not isinstance(rows, list)
                or summary.get("raw_station_records") != len(rows)
                or summary.get("production_candidates") != sum(row.get("production_candidate") is True for row in rows)
                or summary.get("excluded_records") != sum(row.get("production_candidate") is False for row in rows)
                or any(row.get("cpo_operator") != "Kilowatt" or row.get("site_brand") is not None
                       or row.get("tariff_channel") is not None or not isinstance(row.get("connectors"), list)
                       for row in rows)):
            raise ValueError("Kilowatt public inventory contract invalid")
    return report


def run(out: Path, method: str, *, runner=subprocess.run) -> None:
    if method not in METHODS:
        raise ValueError("Unknown Morocco inventory method")
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Morocco inventory must run outside checkout")
    source, output = METHODS[method]
    script = out / source
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / source, script)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError(f"Historical Morocco {method} inventory failed")
    if method == "fastvolt":
        target = out / output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result.stdout, encoding="utf-8")
    validate_output(out, method)


def validate_reconciliation(out: Path) -> dict:
    source = validate_output(out, "kilowatt")
    report = json.loads((out / RECONCILIATION[1]).read_text(encoding="utf-8"))
    eligible = [row for row in source["stations"] if row.get("production_candidate") is True
                and isinstance(row.get("latitude"), (int, float))
                and isinstance(row.get("longitude"), (int, float))]
    summary = report.get("summary") or {}
    policy = report.get("policy") or {}
    rows = report.get("threshold_results")
    if (report.get("schema_version") != 1 or policy.get("offline_only") is not True
            or policy.get("no_production_merges_applied") is not True
            or summary.get("production_station_records") != len(eligible)
            or not isinstance(rows, list)
            or [row.get("threshold_m") for row in rows] != summary.get("thresholds_tested_m")
            or any(not isinstance(row.get("cluster_count"), int)
                   or row.get("records_absorbed_by_clustering") != len(eligible) - row["cluster_count"]
                   for row in rows)):
        raise ValueError("Kilowatt diagnostic reconciliation contract invalid")
    return report


def reconcile(out: Path, source: Path, *, runner=subprocess.run) -> None:
    out, source = out.resolve(), source.resolve()
    if out == ROOT or ROOT in out.parents or source == ROOT or ROOT in source.parents:
        raise ValueError("Kilowatt reconciliation must run outside checkout")
    validate_output(source, "kilowatt")
    input_path = out / METHODS["kilowatt"][1]
    input_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / METHODS["kilowatt"][1], input_path)
    script = out / RECONCILIATION[0]
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / RECONCILIATION[0], script)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Kilowatt reconciliation failed")
    validate_reconciliation(out)


def validate_tariff_overlay(out: Path) -> dict:
    source = validate_output(out, "kilowatt")
    report = json.loads((out / TARIFF_OVERLAY[1]).read_text(encoding="utf-8"))
    expected = {str(row.get("id")): row for row in source["stations"]
                if row.get("production_candidate") is True}
    rows = report.get("stations")
    summary = report.get("summary") or {}
    policy = report.get("policy") or {}
    evidence = out / TARIFF_EVIDENCE
    if (report.get("evidence_reports") != [TARIFF_EVIDENCE] or not evidence.is_file()
            or hashlib.sha256(evidence.read_bytes()).digest()
            != hashlib.sha256((ROOT / TARIFF_EVIDENCE).read_bytes()).digest()):
        raise ValueError("Kilowatt archived tariff evidence missing or changed")
    if (report.get("schema_version") != 1 or report.get("country") != "MA"
            or report.get("network") != "Kilowatt" or not isinstance(rows, list)
            or len(expected) != sum(row.get("production_candidate") is True for row in source["stations"])
            or policy.get("station_specific_free_only") is not True
            or policy.get("missing_native_tariff_does_not_mean_free") is not True
            or summary.get("production_station_count") != len(rows)
            or summary.get("free_tariff_count") != sum(row.get("tariff_production_eligible") is True for row in rows)
            or summary.get("unresolved_tariff_count") != sum(row.get("tariff_production_eligible") is False for row in rows)
            or len({row.get("station_id") for row in rows}) != len(rows)
            or {row.get("station_id") for row in rows} != set(expected)):
        raise ValueError("Kilowatt station tariff overlay contract invalid")
    for row in rows:
        original = expected[row["station_id"]]
        if (row.get("name") != original.get("name")
                or row.get("latitude") != original.get("latitude")
                or row.get("longitude") != original.get("longitude")
                or row.get("cpo_operator") != "Kilowatt"
                or row.get("tariff_currency") != "MAD"
                or row.get("native_tariff_field_present") is not False):
            raise ValueError("Kilowatt station identity changed")
        if row["tariff_production_eligible"] is True:
            if (row.get("tariff_state") != "free_station_specific_public_evidence"
                    or row.get("tariff_mad") != 0 or not row.get("tariff_evidence_rule")
                    or not row.get("tariff_source")):
                raise ValueError("Kilowatt free tariff evidence missing")
        elif (row.get("tariff_state") != "unresolved" or row.get("tariff_mad") is not None
              or row.get("tariff_source") is not None or row.get("tariff_evidence_rule") is not None):
            raise ValueError("Kilowatt unresolved tariff was promoted")
    return report


def build_tariff_overlay(out: Path, source: Path, *, runner=subprocess.run) -> None:
    out, source = out.resolve(), source.resolve()
    if out == ROOT or ROOT in out.parents or source == ROOT or ROOT in source.parents:
        raise ValueError("Kilowatt overlay must run outside checkout")
    validate_output(source, "kilowatt")
    input_path = out / METHODS["kilowatt"][1]
    input_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / METHODS["kilowatt"][1], input_path)
    evidence = out / TARIFF_EVIDENCE
    evidence.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / TARIFF_EVIDENCE, evidence)
    script = out / TARIFF_OVERLAY[0]
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / TARIFF_OVERLAY[0], script)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Kilowatt tariff overlay failed")
    validate_tariff_overlay(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=sorted(METHODS) + ["kilowatt_reconcile", "kilowatt_tariff_overlay"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.method == "kilowatt_reconcile" and args.source:
        reconcile(args.out, args.source)
    elif args.method == "kilowatt_tariff_overlay" and args.source:
        build_tariff_overlay(args.out, args.source)
    elif args.method in {"kilowatt_reconcile", "kilowatt_tariff_overlay"} or args.source:
        parser.error("--source is required only for Kilowatt derived methods")
    else:
        run(args.out, args.method)


if __name__ == "__main__":
    main()
