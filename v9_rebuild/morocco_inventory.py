#!/usr/bin/env python3
"""Run preserved Morocco public-map inventories outside the Git checkout."""

from __future__ import annotations

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=sorted(METHODS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.method)


if __name__ == "__main__":
    main()
