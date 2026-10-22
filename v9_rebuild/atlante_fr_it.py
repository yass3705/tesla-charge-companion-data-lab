#!/usr/bin/env python3
"""Run the preserved myAtlante FR/IT extractor with isolated, checked resume data."""

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

SCRIPT = Path("scripts/atlante/extract_atlante.py")
BASE = Path("results/atlante-live")
OUTPUTS = {
    "FR": Path("data/national/atlante_direct_stations_france_latest.json.gz"),
    "IT": Path("data/national/atlante_direct_stations_italy_latest.json.gz"),
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_checkpoint(checkpoint: Path) -> None:
    manifest = json.loads((checkpoint / "manifest.json").read_text(encoding="utf-8"))
    files = manifest.get("files")
    if manifest.get("schemaVersion") != 1 or not isinstance(files, dict):
        raise ValueError("Atlante checkpoint manifest invalid")
    actual = {}
    for path in checkpoint.rglob("*.json"):
        if path.name == "manifest.json":
            continue
        json.loads(path.read_text(encoding="utf-8"))
        actual[path.relative_to(checkpoint).as_posix()] = _digest(path)
    if actual != files or any(not name.startswith(("FR/raw/", "IT/raw/")) for name in files):
        raise ValueError("Atlante checkpoint files or SHA invalid")


def save_checkpoint(out: Path, checkpoint: Path) -> None:
    raw_files = [p for country in OUTPUTS for p in (out / BASE / country / "raw").rglob("*.json")]
    if not raw_files:
        return
    tmp = checkpoint.with_name(checkpoint.name + ".new")
    if tmp.exists():
        shutil.rmtree(tmp)
    for path in raw_files:
        rel = path.relative_to(out / BASE)
        target = tmp / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        json.loads(path.read_text(encoding="utf-8"))
        shutil.copy2(path, target)
    files = {p.relative_to(tmp).as_posix(): _digest(p) for p in tmp.rglob("*.json")}
    (tmp / "manifest.json").write_text(json.dumps({"schemaVersion": 1, "files": files}, sort_keys=True) + "\n")
    validate_checkpoint(tmp)
    if checkpoint.exists():
        shutil.rmtree(checkpoint)
    tmp.rename(checkpoint)


def validate_output(out: Path) -> dict:
    reports = {}
    for country, output in OUTPUTS.items():
        report = json.loads((out / BASE / country / "report.json").read_text(encoding="utf-8"))
        stations = json.loads((out / BASE / country / "stations.json").read_text(encoding="utf-8"))
        with gzip.open(out / output, "rt", encoding="utf-8") as handle:
            compressed = json.load(handle)
        rows = stations.get("locations")
        if (stations != compressed or not isinstance(rows, list) or stations.get("metadata") != report
                or report.get("country") != country or report.get("cpo") != {"FR": "FRATL", "IT": "ITATE"}[country]
                or report.get("errors") or report.get("inventoryStations") != len(rows)
                or report.get("extractedStations") != len(rows)
                or report.get("connectorCount") != sum(len(row.get("connectors") or []) for row in rows)
                or report.get("pricedConnectors", 0) + report.get("unpricedConnectors", 0) != report.get("connectorCount")):
            raise ValueError("Atlante country snapshot or technical completion invalid")
        ids = [row.get("id") for row in rows]
        connector_ids = [(connector.get("evseId"), connector.get("connectorId"))
                         for row in rows for connector in row.get("connectors") or []]
        if (len(ids) != len(set(ids)) or any(not item for item in ids)
                or len(connector_ids) != len(set(connector_ids))
                or any(row.get("countryCode") != country or row.get("partyId") != {"FR": "ATL", "IT": "ATE"}[country]
                       or (row.get("operatorName") and "atlante" not in row["operatorName"].lower())
                       or any(not c.get("evseId") or not c.get("connectorId")
                              or any((t.get("identifiers") or {}).get("evseId") != c["evseId"]
                                     or (t.get("identifiers") or {}).get("connectorId") != c["connectorId"]
                                     for t in c.get("tariffs") or [])
                              for c in row.get("connectors") or []) for row in rows)):
            raise ValueError("Atlante station, EVSE or connector identity invalid")
        reports[country] = report
    return reports


def run(out: Path, *, checkpoint: Path, runner=subprocess.run) -> None:
    out = out.resolve()
    checkpoint = checkpoint.resolve()
    if out == ROOT or ROOT in out.parents or checkpoint == ROOT or ROOT in checkpoint.parents:
        raise ValueError("Atlante work and checkpoint must be off checkout")
    target = out / SCRIPT
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, target)
    if checkpoint.exists():
        validate_checkpoint(checkpoint)
        for raw in checkpoint.rglob("*.json"):
            if raw.name == "manifest.json":
                continue
            dest = out / BASE / raw.relative_to(checkpoint)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(raw, dest)
    command = [sys.executable, str(target), "--countries", "FR", "IT", "--out", str(out / BASE),
               "--workers", "8", "--resume"]
    try:
        completed = runner(command, cwd=out, capture_output=True, text=True, timeout=5400, check=False)
        if completed.returncode:
            raise RuntimeError("Historical Atlante FR/IT method failed")
        for country, output in OUTPUTS.items():
            source = out / BASE / country / "stations.json"
            payload = source.read_bytes()
            output_path = out / output
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
        validate_output(out)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        save_checkpoint(out, checkpoint)
        raise
    if checkpoint.exists():
        shutil.rmtree(checkpoint)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, checkpoint=args.checkpoint)


if __name__ == "__main__":
    main()
