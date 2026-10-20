#!/usr/bin/env python3
"""Run the two preserved Picoty PAN processors on the known IRVE export."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

PAN_IRVE_URL = "https://transport.data.gouv.fr/resources/84013/download"
RAW = Path("raw/avia_picoty_pan_irve.csv")
EXTRACT = Path("data/national/avia_volt_picoty_irve_extract.json")
INDEX = Path("data/national/avia_volt_picoty_station_index.json")


def validate_output(out: Path) -> dict:
    raw = out / RAW
    if not raw.is_file() or not raw.stat().st_size:
        raise ValueError("AVIA Picoty PAN CSV missing or empty")
    extracted = json.loads((out / EXTRACT).read_text(encoding="utf-8"))
    index = json.loads((out / INDEX).read_text(encoding="utf-8"))
    stations = extracted.get("stations")
    compact = index.get("stations")
    counts = extracted.get("counts") or {}
    if (extracted.get("schemaVersion") != "1.0.0"
            or extracted.get("dataset") != "avia-volt-picoty-pan-irve-extract"
            or extracted.get("source", {}).get("url") != PAN_IRVE_URL
            or extracted.get("scope", {}).get("operatorPrefixNormalized") != "FRPY2"
            or extracted.get("scope", {}).get("physicalCpoDirectInventory") is not True
            or extracted.get("scope", {}).get("roamingTariffsIncluded") is not False
            or not isinstance(stations, list) or counts.get("stationCount") != len(stations)
            or index.get("dataset") != "avia-volt-picoty-station-index"
            or index.get("generatedAt") != extracted.get("generatedAt")
            or index.get("sourceDataset") != extracted.get("dataset")
            or index.get("counts") != counts
            or not isinstance(compact, list) or len(compact) != len(stations)):
        raise ValueError("AVIA Picoty PAN extract contract invalid")
    original_ids = [station.get("stationId") for station in stations]
    compact_ids = [station.get("stationId") for station in compact]
    if (any(not sid for sid in original_ids)
            or len(original_ids) != len(set(original_ids))
            or original_ids != compact_ids
            or counts.get("panRowsMatched") != sum(len(station.get("evses") or []) for station in stations)
            or any(station.get("pdcCount") != len(station.get("pdcIds") or []) for station in compact)):
        raise ValueError("AVIA Picoty PAN station or connector identities invalid")
    return extracted


def run(out: Path, *, input_csv: Path | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("AVIA Picoty extraction output must be outside checkout")
    raw = out / RAW
    raw.parent.mkdir(parents=True, exist_ok=True)
    (out / EXTRACT).parent.mkdir(parents=True, exist_ok=True)
    if input_csv is not None:
        shutil.copy2(input_csv, raw)
    else:
        # Exact historical URL and curl options from avia-picoty-irve-extract.yml.
        result = runner(["curl", "--fail", "--silent", "--show-error", "--location", "--retry", "4",
                         "--retry-all-errors", "--connect-timeout", "30", "--max-time", "600",
                         PAN_IRVE_URL, "-o", str(raw)], capture_output=True, text=True, timeout=700, check=False)
        if result.returncode:
            raise RuntimeError("Historical AVIA Picoty PAN download failed")
    if not raw.is_file() or not raw.stat().st_size:
        raise ValueError("AVIA Picoty PAN CSV missing or empty")
    for command in ([sys.executable, str(ROOT / "scripts/avia_picoty_irve_extract.py"), str(raw), str(out / EXTRACT), "--source-url", PAN_IRVE_URL],
                    [sys.executable, str(ROOT / "scripts/avia_picoty_compact_index.py"), str(out / EXTRACT), str(out / INDEX)]):
        result = runner(command, cwd=out, capture_output=True, text=True, timeout=600, check=False)
        if result.returncode:
            raise RuntimeError("Historical AVIA Picoty PAN processing failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
