#!/usr/bin/env python3
"""Run the preserved WAAT/Monta public evidence collector off checkout."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from v9_rebuild.cwd_script import METHODS, validate_output as validate_inventory
from v9_rebuild.electroverse import ROOT

INPUT = Path("data/national/waat_direct_stations_france.json.gz")
OUTPUT = Path("data/national/waat_monta_public_tariffs_france.json.gz")
REPORT = Path("data/reports/waat_monta_public_tariffs_report.json")
PROVENANCE = Path("data/reports/waat_monta_public_provenance.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def validate_output(out: Path) -> dict:
    inventory = load_gzip(out / INPUT)
    payload = load_gzip(out / OUTPUT)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    provenance = json.loads((out / PROVENANCE).read_text(encoding="utf-8"))
    source_stations = [row for row in inventory.get("stations", [])
                       if isinstance(row.get("coordinates"), list) and len(row["coordinates"]) >= 2]
    stations = payload.get("stations")
    groups = payload.get("directGroups")
    counts = payload.get("counts") or {}
    if not isinstance(stations, list) or not isinstance(groups, list):
        raise ValueError("WAAT/Monta public station or group list missing")
    ids = [row.get("stationIdNormalized") for row in stations]
    expected = [row.get("stationIdNormalized") for row in source_stations]
    group_keys = [row.get("key") for row in groups]
    if (inventory.get("dataset") != "waat-direct-stations-france"
            or payload.get("schemaVersion") != "2.0.0"
            or payload.get("dataset") != "waat-monta-public-direct-tariffs-france"
            or payload.get("country") != "FR" or payload.get("operatorPrefix") != "FR*WA2"
            or payload.get("scope", {}).get("pricesFailClosedUntilNormalized") is not True
            or ids != expected or len(ids) != len(set(ids))
            or any(row.get("rankableDirect") is not False for row in stations)
            or any(not key for key in group_keys) or len(group_keys) != len(set(group_keys))
            or any(row.get("detailStatus") != 200 or
                   (row.get("group", {}).get("document") == "charge_point_group" and row.get("childrenStatus") != 200)
                   for row in groups)
            or counts.get("irveStationCount") != len(stations)
            or counts.get("mapErrors") != 0 or counts.get("detailErrors") != 0
            or counts.get("mapCalls", -1) < len(stations)
            or counts.get("directWaatGroupCount") != len(groups)
            or report.get("counts") != counts
            or provenance.get("inventorySha256") != sha(out / INPUT)
            or provenance.get("outputSha256") != sha(out / OUTPUT)
            or provenance.get("reportSha256") != sha(out / REPORT)):
        raise ValueError("WAAT/Monta public evidence technical contract invalid")
    return payload


def run(out: Path, inventory_state: Path, *, fixture_map: Path | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("WAAT/Monta public output must be outside checkout")
    validate_inventory(inventory_state, "waat_inventory")
    (out / INPUT).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(inventory_state / METHODS["waat_inventory"][1], out / INPUT)
    env = os.environ.copy()
    if fixture_map is not None:
        env["WAAT_PUBLIC_OFFLINE_FIXTURE"] = str(fixture_map)
    result = runner(["node", str(ROOT / "scripts/waat_monta_public_tariffs.mjs")], cwd=out, env=env,
                    capture_output=True, text=True, timeout=1800, check=False)
    if result.returncode:
        raise RuntimeError("Historical WAAT/Monta public method failed")
    if not (out / OUTPUT).is_file() or not (out / REPORT).is_file():
        raise ValueError("WAAT/Monta public output incomplete")
    provenance = {"inventorySha256": sha(out / INPUT), "outputSha256": sha(out / OUTPUT),
                  "reportSha256": sha(out / REPORT)}
    (out / PROVENANCE).write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.inventory)


if __name__ == "__main__":
    main()
