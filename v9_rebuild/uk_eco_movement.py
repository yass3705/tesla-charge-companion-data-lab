#!/usr/bin/env python3
"""Run archived Eco-Movement PCPR collection and fail-closed staging off checkout."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

RAW = Path("data/national/uk_eco_movement_pcpr.json.gz")
COLLECTION = Path("reports/uk/eco-movement-pcpr-latest.json")
AUDIT = Path("reports/uk/eco-movement-pcpr-connector-audit.json")
STAGED = Path("data/national/uk_eco_movement_pcpr_v9.json.gz")
STAGING = Path("reports/uk/eco-movement-pcpr-v9-staging.json")


def read_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def validate_output(out: Path) -> dict:
    raw = read_gzip(out / RAW)
    collection = json.loads((out / COLLECTION).read_text(encoding="utf-8"))
    audit = json.loads((out / AUDIT).read_text(encoding="utf-8"))
    staged = read_gzip(out / STAGED)
    staging = json.loads((out / STAGING).read_text(encoding="utf-8"))
    token = os.environ.get("ECO_MOVEMENT_PCPR_TOKEN", "")
    if token and any(token in json.dumps(item, ensure_ascii=False) for item in (raw, collection, audit, staged, staging)):
        raise ValueError("Eco-Movement credential reflected in artifact")
    locations, tariffs, statuses = (raw.get(key) for key in ("locations", "tariffs", "statuses"))
    if not all(isinstance(rows, list) for rows in (locations, tariffs, statuses)):
        raise ValueError("Eco-Movement PCPR raw lists missing")
    stamp = raw.get("retrievedAt")
    sources = staged.get("sources")
    if (not stamp or raw.get("source") != "Eco-Movement PCPR"
            or collection.get("retrievedAt") != stamp
            or collection.get("locationCount") != len(locations)
            or collection.get("tariffCount") != len(tariffs)
            or collection.get("statusCount") != len(statuses)
            or audit.get("inputCollectedAt") != stamp
            or audit.get("rawCounts", {}).get("locations") != len(locations)
            or audit.get("rawCounts", {}).get("tariffs") != len(tariffs)
            or audit.get("rawCounts", {}).get("statuses") != len(statuses)
            or staged.get("country") != "GB" or staged.get("collectedAt") != stamp
            or staged.get("integrationStatus") != "pcpr_cpo_arithmetic_staging_payg_and_vat_not_verified"
            or not isinstance(sources, list) or len(sources) != 1
            or sources[0].get("id") != "eco-movement-pcpr-cpo-direct"
            or sources[0].get("pricingScope") != "cpo_pcpr_adhoc_attribution_pending"
            or staging.get("sourceCollectedAt") != stamp
            or staging.get("sourceLocations") != len(locations)
            or staging.get("sourceTariffCount") != len(tariffs)
            or staging.get("stagedPublicLocations") != len(sources[0].get("locations") or [])
            or staging.get("GBPConvertedTariffs") != len(sources[0].get("tariffs") or [])
            or staging.get("readyForTariffRanking") is not False
            or staging.get("integrationStatus") != staged["integrationStatus"]
            or staging.get("stagedDataset") != str(STAGED)):
        raise ValueError("Eco-Movement PCPR source or fail-closed staging contract invalid")
    if any(not row.get("id") for row in locations + tariffs):
        raise ValueError("Eco-Movement PCPR source ID missing")
    source_ids = {row["id"] for row in locations}
    tariff_ids = {row["id"] for row in tariffs}
    staged_ids = [row.get("id") for row in sources[0]["locations"]]
    staged_tariff_ids = [row.get("id") for row in sources[0]["tariffs"]]
    if (any(not value or value not in source_ids for value in staged_ids)
            or len(staged_ids) != len(set(staged_ids))
            or any(not value or value not in tariff_ids for value in staged_tariff_ids)
            or len(staged_tariff_ids) != len(set(staged_tariff_ids))):
        raise ValueError("Eco-Movement PCPR staged identities not from source")
    return staged


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Eco-Movement PCPR method must run outside checkout")
    script_dir = out / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    (out / "data/national").mkdir(parents=True, exist_ok=True)
    (out / "reports/uk").mkdir(parents=True, exist_ok=True)
    for name in ("uk_eco_movement_pcpr_collect.py", "uk_eco_movement_pcpr_audit.py"):
        script = script_dir / name
        shutil.copy2(ROOT / "scripts" / name, script)
        result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                        text=True, timeout=1200, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical Eco-Movement {name} failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
