#!/usr/bin/env python3
"""Run preserved E55C static and exact Scan Pay methods outside checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

BASE = Path("data/national/electric55_static_france.json")
FINAL = Path("data/national/electric55_stations_france.json")
REPORT = Path("reports/electric55/station_base_summary.md")
PROVENANCE = Path("reports/electric55/v9-chain-provenance.json")
PRIOR = Path("input/electric55_last_good.json")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_catalogue(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    stations = payload.get("stations")
    stats = payload.get("stats") or {}
    scope = payload.get("scope") or {}
    if (payload.get("schemaVersion") not in {"1.0.0", "1.1.0"}
            or payload.get("dataset") != "electric55-operated-stations-france"
            or payload.get("country") != "FR"
            or payload.get("operator") != "Electric 55 Charging (E55C)"
            or scope.get("roamingTariffsIncluded") is not False
            or scope.get("dynamicStatusIncluded") is not False
            or not isinstance(stations, list)
            or stats.get("stationCount") != len(stations)
            or stats.get("chargePointCount") != sum(len(row.get("chargePoints") or []) for row in stations)):
        raise ValueError("E55C catalogue technical contract invalid")
    ids = set()
    evse_ids = set()
    for station in stations:
        sid = station.get("stationId")
        if not sid or sid in ids or not isinstance(station.get("chargePoints"), list):
            raise ValueError("E55C station identity invalid")
        ids.add(sid)
        for point in station["chargePoints"]:
            eid = point.get("evseId")
            if not eid or eid in evse_ids:
                raise ValueError("E55C EVSE identity invalid")
            evse_ids.add(eid)
    return payload


def validate_output(out: Path) -> dict:
    base = validate_catalogue(out / BASE)
    final = validate_catalogue(out / FINAL)
    provenance = json.loads((out / PROVENANCE).read_text(encoding="utf-8"))
    def identities(payload):
        return {(station["stationId"], point["evseId"], point.get("localEvseId"))
                for station in payload["stations"] for point in station["chargePoints"]}
    if (not (out / REPORT).read_text(encoding="utf-8").strip()
            or provenance.get("baseSha256") != digest(out / BASE)
            or provenance.get("finalSha256") != digest(out / FINAL)
            or provenance.get("previousSha256") != digest(out / PRIOR)
            or final.get("source", {}).get("sha256") != base.get("source", {}).get("sha256")
            or final.get("stats", {}).get("stationCount") != base.get("stats", {}).get("stationCount")
            or final.get("stats", {}).get("chargePointCount") != base.get("stats", {}).get("chargePointCount")
            or identities(final) != identities(base)
            or not isinstance(final.get("directTariffProfiles"), list)):
        raise ValueError("E55C static/direct handoff invalid")
    return final


def run(out: Path, *, source: Path = ROOT, input_csv: Path | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("E55C output must be outside checkout")
    for path in (BASE, FINAL, REPORT, PRIOR):
        (out / path).parent.mkdir(parents=True, exist_ok=True)
    previous = source / FINAL
    validate_catalogue(previous)
    shutil.copy2(previous, out / PRIOR)
    build = [sys.executable, str(ROOT / "scripts/electric55_station_base.py"),
             "--out", str(out / BASE), "--report", str(out / REPORT)]
    if input_csv is not None:
        build.extend(["--input-csv", str(input_csv)])
    result = runner(build, cwd=out, capture_output=True, text=True, timeout=1200, check=False)
    if result.returncode:
        raise RuntimeError("Historical E55C static method failed")
    validate_catalogue(out / BASE)
    enrich = [sys.executable, str(ROOT / "scripts/electric55_direct_tariffs.py"),
              "--input", str(out / BASE), "--output", str(out / FINAL),
              "--report", str(out / REPORT), "--previous", str(out / PRIOR), "--workers", "8", "--full-refresh"]
    result = runner(enrich, cwd=out, capture_output=True, text=True, timeout=2400, check=False)
    if result.returncode:
        raise RuntimeError("Historical E55C direct tariff method failed")
    provenance = {"baseSha256": digest(out / BASE), "finalSha256": digest(out / FINAL),
                  "previousSha256": digest(out / PRIOR), "sourceMethod": "E55C official static plus exact Scan Pay"}
    (out / PROVENANCE).write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()
    run(args.out, source=args.source)


if __name__ == "__main__":
    main()
