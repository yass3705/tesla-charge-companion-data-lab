#!/usr/bin/env python3
"""Run the historical GRIDSERVE PCPR collector and exact connector builder off checkout."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import runpy
from pathlib import Path

from v9_rebuild.electroverse import ROOT
from v9_rebuild.uk_blink import load_script

LOCATIONS = Path("data/national/uk_gridserve_pcpr_locations.json.gz")
TARIFFS = Path("data/national/uk_gridserve_pcpr_tariffs.json.gz")
STAGED = Path("data/national/uk_gridserve_v9.json.gz")
CROSSWALK = Path("reports/uk/gridserve-v9-connector-crosswalk.json.gz")
COLLECT_REPORT = Path("reports/uk/gridserve-pcpr-latest.json")
INTEGRATION_REPORT = Path("reports/uk/gridserve-v9-integration-latest.json")


def read_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("GRIDSERVE gzip payload is not an object")
    return value


def validate_output(out: Path) -> dict:
    locations = read_gzip(out / LOCATIONS)
    tariffs = read_gzip(out / TARIFFS)
    staged = read_gzip(out / STAGED)
    crosswalk = read_gzip(out / CROSSWALK)
    collected = json.loads((out / COLLECT_REPORT).read_text(encoding="utf-8"))
    report = json.loads((out / INTEGRATION_REPORT).read_text(encoding="utf-8"))
    sources = staged.get("sources") or []
    if (collected.get("provider") != "GRIDSERVE" or collected.get("country") != "GB"
            or collected.get("secretValuePersisted") is not False
            or collected.get("locations", {}).get("count") != len(locations.get("locations") or [])
            or collected.get("tariffs", {}).get("count") != len(tariffs.get("tariffs") or [])
            or locations.get("collectedAt") != tariffs.get("collectedAt")
            or staged.get("collectedAt") != locations.get("collectedAt")
            or report.get("collectedAt") != staged.get("collectedAt")
            or report.get("provider") != "GRIDSERVE"
            or len(sources) != 1 or sources[0].get("id") != "gridserve-pcpr-direct"
            or not isinstance(sources[0].get("locations"), list)
            or not isinstance(sources[0].get("tariffs"), list)
            or report.get("publicLocations") != len(sources[0]["locations"])
            or report.get("publicConnectors") != len(crosswalk.get("links") or [])
            or report.get("exactPricedConnectors") + report.get("unpricedPublicConnectors") != report.get("publicConnectors")
            or report.get("validatedForV9") is not bool(report.get("exactPricedConnectors"))):
        raise ValueError("GRIDSERVE PCPR technical contract invalid")
    tariffs_by_id = {row.get("id"): row for row in sources[0]["tariffs"]}
    if len(tariffs_by_id) != len(sources[0]["tariffs"]):
        raise ValueError("GRIDSERVE duplicate tariff IDs")
    seen = set()
    for link in crosswalk["links"]:
        key = (link.get("locationId"), link.get("evseUid"), link.get("connectorId"))
        if not all(key) or key in seen:
            raise ValueError("GRIDSERVE connector identity invalid")
        seen.add(key)
        refs = link.get("tariffIds") or []
        if link.get("priceVerified") is not bool(refs) or any(ref not in tariffs_by_id for ref in refs):
            raise ValueError("GRIDSERVE connector tariff reference invalid")
    return staged


def execute_collector(script: Path, out: Path) -> None:
    previous = Path.cwd()
    try:
        os.chdir(out)
        runpy.run_path(str(script), run_name="__main__")
    finally:
        os.chdir(previous)


def run(out: Path, *, collector=execute_collector) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("GRIDSERVE output must be outside checkout")
    if not os.environ.get("GRIDSERVE_PCPR_API_KEY", "").strip():
        raise RuntimeError("Missing named GRIDSERVE PCPR secret")
    (out / LOCATIONS).parent.mkdir(parents=True, exist_ok=True)
    (out / COLLECT_REPORT).parent.mkdir(parents=True, exist_ok=True)
    collector(ROOT / "scripts/uk_gridserve_pcpr_collect.py", out)
    builder = load_script(ROOT / "scripts/uk_gridserve_v9_prepare.py", "v9_historical_gridserve_prepare")
    builder.ROOT = out
    builder.LOCATION_SOURCE = out / LOCATIONS
    builder.TARIFF_SOURCE = out / TARIFFS
    builder.DATA_OUT = out / STAGED
    builder.CROSSWALK_OUT = out / CROSSWALK
    builder.AUDIT_OUT = out / INTEGRATION_REPORT
    builder.main()
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
