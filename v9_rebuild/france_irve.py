#!/usr/bin/env python3
"""Run the preserved national static, dynamic and exact-ID audit chain."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from v9_rebuild.electroverse import ROOT

STATIC = Path("data/national/france-irve-static-v9")
DYNAMIC = Path("data/national/france-irve-dynamic-status-v9.json.gz")
REPORT = Path("reports/france/irve/irve-residual-crosswalk-latest.json")
RESIDUAL = Path("data/platforms/electra/france/residuals.json.gz")
INPUT = Path("raw/france-irve")
STATIC_URL = "https://proxy.transport.data.gouv.fr/resource/consolidation-transport-irve-statique"
DYNAMIC_URL = "https://proxy.transport.data.gouv.fr/resource/consolidation-nationale-irve-dynamique"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url: str, path: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "TeslaChargeCompanionDataLab/1.0"})
    with urllib.request.urlopen(request, timeout=900) as response:
        path.write_bytes(response.read())


def validate_output(out: Path) -> dict:
    manifest = json.loads((out / STATIC / "manifest.json").read_text(encoding="utf-8"))
    with gzip.open(out / STATIC / "all.json.gz", "rt", encoding="utf-8") as handle:
        stations = json.load(handle)
    tiles = manifest.get("tiles") or []
    if (manifest.get("schemaVersion") != 2 or manifest.get("dataset") != "france-irve-static-v9"
            or manifest.get("sourceUrl") != STATIC_URL
            or manifest.get("sourceSha256") != sha(out / INPUT / "static.csv")
            or manifest.get("sourceBytes") != (out / INPUT / "static.csv").stat().st_size
            or manifest.get("builderSha256") != sha(ROOT / "scripts/france/build_france_irve_static_v9.py")
            or manifest.get("allSha256") != sha(out / STATIC / "all.json.gz")
            or manifest.get("allBytes") != (out / STATIC / "all.json.gz").stat().st_size
            or manifest.get("stationCount") != len(stations)
            or manifest.get("tileCount") != len(tiles)
            or len({station[0] for station in stations}) != len(stations)):
        raise ValueError("France static IRVE technical contract invalid")
    seen = set()
    stations_by_id = {row[0]: row for row in stations}
    evse_owner = {}
    for station in stations:
        station_evses = set()
        for group in station[8]:
            for evse in group[6]:
                if evse in evse_owner and evse_owner[evse] != station[0]:
                    raise ValueError("France IRVE EVSE belongs to two stations")
                evse_owner[evse] = station[0]
                station_evses.add(evse)
        if station[6] != len(station_evses):
            raise ValueError("France IRVE station EVSE count mismatch")
    if manifest.get("pdcCount") != len(evse_owner):
        raise ValueError("France IRVE manifest EVSE count mismatch")
    for tile in tiles:
        relative = Path(tile["file"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "tiles":
            raise ValueError("France IRVE tile path invalid")
        tile_path = out / STATIC / relative
        with gzip.open(tile_path, "rt", encoding="utf-8") as handle:
            rows = json.load(handle)
        if sha(tile_path) != tile.get("sha256") or tile_path.stat().st_size != tile.get("bytes") or len(rows) != tile.get("count"):
            raise ValueError("France IRVE tile integrity mismatch")
        for row in rows:
            if row[0] in seen:
                raise ValueError("France IRVE station duplicated across tiles")
            if stations_by_id.get(row[0]) != row:
                raise ValueError("France IRVE tile differs from complete dataset")
            seen.add(row[0])
    if seen != {row[0] for row in stations}:
        raise ValueError("France IRVE tile coverage incomplete")
    with gzip.open(out / DYNAMIC, "rt", encoding="utf-8") as handle:
        dynamic = json.load(handle)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    active_ids = dynamic.get("enServicePdcIds", [])
    excluded = dynamic.get("records", [])
    excluded_ids = [row.get("id_pdc_itinerance") for row in excluded]
    if (dynamic.get("schemaVersion") != 1 or dynamic.get("country") != "FR"
            or dynamic.get("sourceUrl") != DYNAMIC_URL
            or dynamic.get("sourceSha256") != sha(out / INPUT / "dynamic.csv")
            or dynamic.get("matchedPdc") != len(active_ids) + len(excluded)
            or len(active_ids) != len(set(active_ids)) or len(excluded_ids) != len(set(excluded_ids))
            or set(active_ids) & set(excluded_ids)
            or not (set(active_ids) | set(excluded_ids)).issubset(evse_owner)
            or any(row.get("id_station_itinerance") != evse_owner.get(row.get("id_pdc_itinerance")) for row in excluded)
            or report.get("sources", {}).get("static", {}).get("sourceSha256") != manifest["sourceSha256"]
            or report.get("sources", {}).get("dynamic", {}).get("sha256") != dynamic["sourceSha256"]
            or report.get("sources", {}).get("residualSnapshotSha256") != sha(out / RESIDUAL)):
        raise ValueError("France dynamic IRVE or exact-ID audit contract invalid")
    return manifest


def run(out: Path, *, static_csv: Path | None = None, dynamic_csv: Path | None = None,
        runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("France IRVE output must be outside checkout")
    (out / INPUT).mkdir(parents=True, exist_ok=True)
    (out / RESIDUAL).parent.mkdir(parents=True, exist_ok=True)
    for path, url, name in ((static_csv, STATIC_URL, "static.csv"), (dynamic_csv, DYNAMIC_URL, "dynamic.csv")):
        destination = out / INPUT / name
        if path is None:
            download(url, destination)
        else:
            shutil.copy2(path, destination)
        if not destination.is_file():
            raise RuntimeError(f"National IRVE source missing: {name}")
    shutil.copy2(ROOT / RESIDUAL, out / RESIDUAL)
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    commands = [
        [sys.executable, str(ROOT / "scripts/france/build_france_irve_static_v9.py"),
         "--input", str(out / INPUT / "static.csv"), "--out-dir", str(out / STATIC),
         "--source-sha256", sha(out / INPUT / "static.csv"),
         "--source-bytes", str((out / INPUT / "static.csv").stat().st_size),
         "--source-retrieved-at", retrieved_at],
        [sys.executable, str(ROOT / "scripts/france/build_france_irve_dynamic_status_v9.py"),
         "--static-all", str(out / STATIC / "all.json.gz"),
         "--dynamic-csv", str(out / INPUT / "dynamic.csv"), "--retrieved-at", retrieved_at,
         "--out", str(out / DYNAMIC)],
        [sys.executable, str(ROOT / "scripts/france/audit_france_irve_residuals.py"),
         "--static-all", str(out / STATIC / "all.json.gz"),
         "--static-manifest", str(out / STATIC / "manifest.json"),
         "--dynamic-csv", str(out / INPUT / "dynamic.csv"),
         "--residuals", str(out / RESIDUAL), "--out", str(out / REPORT)],
    ]
    for command in commands:
        result = runner(command, cwd=out, capture_output=True, text=True, timeout=1200, check=False)
        if result.returncode:
            raise RuntimeError("Historical national IRVE chain failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
