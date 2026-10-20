#!/usr/bin/env python3
"""Run the preserved operator API and snapshot audit in an isolated workspace."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

LOCATIONS = Path("data/national/uk_connected_kerb_locations.json.gz")
TARIFFS = Path("data/national/uk_connected_kerb_tariffs.json.gz")
REPORT = Path("reports/uk/connected-kerb-latest.json")
AUDIT = Path("reports/uk/connected-kerb-snapshot-audit-latest.json")
EXCLUSIONS = Path("reports/uk/connected-kerb-price-exclusions-latest.json")
ELIGIBLE = Path("data/national/uk_connected_kerb_price_unambiguous_locations.json.gz")
OUTPUTS = (LOCATIONS, TARIFFS, REPORT, AUDIT, EXCLUSIONS, ELIGIBLE)


def read_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def validate_output(out: Path) -> dict:
    locations = read_gzip(out / LOCATIONS)
    tariffs = read_gzip(out / TARIFFS)
    eligible = read_gzip(out / ELIGIBLE)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    audit = json.loads((out / AUDIT).read_text(encoding="utf-8"))
    exclusions = json.loads((out / EXCLUSIONS).read_text(encoding="utf-8"))
    rows = locations.get("locations")
    tariff_rows = tariffs.get("tariffs")
    if not isinstance(rows, list) or not isinstance(tariff_rows, list):
        raise ValueError("Connected Kerb raw lists missing")
    stamp = locations.get("collectedAt")
    page = report.get("pagination") or {}
    if (not stamp or tariffs.get("collectedAt") != stamp or report.get("collectedAt") != stamp
            or report.get("country") != "GB" or report.get("provider") != "Connected Kerb"
            or report.get("secretValuePersisted") is not False or report.get("publishedToV9") is not False
            or report.get("counts", {}).get("locations") != len(rows)
            or report.get("counts", {}).get("tariffs") != len(tariff_rows)
            or audit.get("snapshotCollectedAt") != stamp
            or audit.get("rawLocationRows") != len(rows)
            or audit.get("tariffs") != len(tariff_rows)
            or audit.get("publishedToV9") is not False
            or audit.get("missingReferencedTariffIds")
            or audit.get("substantiveConflictingLocationIds")
            or exclusions.get("snapshotCollectedAt") != stamp
            or eligible.get("collectedAt") != stamp
            or len(eligible.get("locations", [])) != exclusions.get("priceUnambiguousStationCount")):
        raise ValueError("Connected Kerb operator snapshot or audit contract invalid")
    for key, values in (("locations", rows), ("tariffs", tariff_rows)):
        pagination = page.get(key) or {}
        if (not isinstance(pagination.get("pages"), int) or pagination["pages"] < 1
                or pagination.get("count") != len(values)
                or pagination.get("reportedTotal") not in (None, len(values))):
            raise ValueError("Connected Kerb declared pagination incomplete")
    source_ids = [str(row.get("id") or "") for row in rows]
    tariff_ids = [str(row.get("id") or "") for row in tariff_rows]
    if any(not value for value in source_ids + tariff_ids):
        raise ValueError("Connected Kerb source identity contract invalid")
    return report


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Connected Kerb operator snapshot must run outside checkout")
    script_dir = out / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    for name in ("uk_connected_kerb_collect.py", "uk_connected_kerb_snapshot_audit.py"):
        shutil.copy2(ROOT / "scripts" / name, script_dir / name)
    for name in ("uk_connected_kerb_collect.py", "uk_connected_kerb_snapshot_audit.py"):
        result = runner([sys.executable, str(script_dir / name)], cwd=out,
                        capture_output=True, text=True, timeout=1200, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical Connected Kerb {name} failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
