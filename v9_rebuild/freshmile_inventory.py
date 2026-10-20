#!/usr/bin/env python3
"""Run strict Freshmile CPO inventory and regional exclusion off checkout."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

BASE = Path("data/national/freshmile_direct_before_regional_prune.json.gz")
FINAL = Path("data/national/freshmile_direct_stations_france.json.gz")
CONFIG = Path("config/freshmile_regional_network_exclusions.json")
REPORT = Path("reports/freshmile/direct-inventory-provenance.json")


def read_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("Freshmile inventory is not an object")
    return payload


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_output(out: Path) -> dict:
    base = read_gzip(out / BASE)
    final = read_gzip(out / FINAL)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    config = json.loads((out / CONFIG).read_text(encoding="utf-8"))
    for payload in (base, final):
        stations = payload.get("stations")
        stats = payload.get("stats") or {}
        if (payload.get("schemaVersion") != "1.0.0"
                or payload.get("dataset") != "freshmile-direct-cpo-stations-france"
                or payload.get("country") != "FR" or payload.get("operator") != "Freshmile"
                or not isinstance(stations, list)
                or stats.get("stationCount") != len(stations)
                or stats.get("chargePointCount") != sum(len(station.get("chargePoints") or []) for station in stations)
                or stats.get("chargePointCountRankableBeforeFreshmileValidation") != 0
                or payload.get("tccIntegration", {}).get("directTariffLayerReady") is not False):
            raise ValueError("Freshmile direct inventory contract invalid")
    if (final.get("regionalNetworkAudit", {}).get("configuredNetworkCount") != len(config.get("networks") or [])
            or final.get("stats", {}).get("umbrellaStationCountBeforeRegionalExclusion") != len(base["stations"])
            or final.get("stats", {}).get("excludedRegionalStationCount") != len(base["stations"]) - len(final["stations"])
            or final.get("tccIntegration", {}).get("regionalExclusionLayerReady") is not True
            or final.get("tccIntegration", {}).get("publishToStableAllowed") is not False
            or report.get("baseSha256") != sha(out / BASE)
            or report.get("finalSha256") != sha(out / FINAL)
            or report.get("configSha256") != sha(out / CONFIG)):
        raise ValueError("Freshmile regional exclusion or SHA contract invalid")
    before = {station.get("stationId") for station in base["stations"]}
    after = {station.get("stationId") for station in final["stations"]}
    if (None in before or None in after or len(before) != len(base["stations"])
            or len(after) != len(final["stations"]) or not after.issubset(before)):
        raise ValueError("Freshmile station identities invalid")
    return final


def run(out: Path, *, input_csv: Path | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Freshmile output must be outside checkout")
    for relative in (BASE, FINAL, CONFIG, REPORT):
        (out / relative).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / CONFIG, out / CONFIG)
    build = [sys.executable, str(ROOT / "scripts/freshmile_direct_inventory.py"), "--output", str(out / BASE)]
    if input_csv is not None:
        build.extend(["--input", str(input_csv)])
    result = runner(build, cwd=out, capture_output=True, text=True, timeout=1200, check=False)
    if result.returncode:
        raise RuntimeError("Historical Freshmile CPO inventory failed")
    shutil.copy2(out / BASE, out / FINAL)
    prune = [sys.executable, str(ROOT / "scripts/freshmile_prune_regional_networks.py"),
             "--dataset", str(out / FINAL), "--config", str(out / CONFIG)]
    result = runner(prune, cwd=out, capture_output=True, text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Freshmile regional exclusion failed")
    report = {"baseSha256": sha(out / BASE), "finalSha256": sha(out / FINAL),
              "configSha256": sha(out / CONFIG), "sourceMethod": "Freshmile direct CPO IRVE plus explicit regional pruning"}
    (out / REPORT).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
