#!/usr/bin/env python3
"""Run the preserved Belib tariff and operated-station scripts in order, off checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from v9_rebuild.electroverse import ROOT


TARIFF = Path("data/operator_direct/belib_official_paris.json")
STATIONS = Path("data/national/belib_stations_paris.json")
SUMMARY = Path("reports/belib/latest_summary.md")
BASE_REPORT = Path("reports/belib/station_base_summary.md")
RUN_STATUS = Path("reports/belib/latest_run_status.json")
DIAGNOSTIC = Path("reports/belib/latest_diagnostic.json")


def failure_report(out: Path, stage: str) -> None:
    path = out / DIAGNOSTIC
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"dataset": "belib-extraction-diagnostic", "sanitized": True,
                                "stage": stage, "status": "failed"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Belib output must be a JSON object: {path}")
    return value


def validate_tariff(root: Path) -> dict:
    data = read(root / TARIFF)
    evidence = data.get("sourceEvidence") or {}
    if (data.get("dataset") != "belib-official-paris" or data.get("country") != "FR"
            or data.get("operator") != "Belib'" or data.get("city") != "Paris"
            or evidence.get("officialOnly") is not True
            or not evidence.get("bookingPdfSha256") or not evidence.get("chargingPdfSha256")
            or not evidence.get("relevantTariffFingerprintSha256")
            or not isinstance(data.get("visitor"), dict)
            or not isinstance(data.get("subscriptions"), dict)
            or not isinstance(data.get("fees"), dict)):
        raise ValueError("Belib official tariff technical contract failed")
    return data


def validate_output(root: Path) -> dict:
    tariff = validate_tariff(root)
    data = read(root / STATIONS)
    scope = data.get("scope") or {}
    stats = data.get("stats") or {}
    stations = data.get("stations")
    profiles = data.get("directTariffProfiles")
    if (data.get("dataset") != "belib-operated-stations-paris" or data.get("country") != "FR"
            or scope.get("strictOperatorValue") != "TOTALENERGIES" or scope.get("strictBrandValue") != "Belib'"
            or scope.get("thirdPartyRoamingStationsExcluded") is not True
            or scope.get("motorcycleOnlyPointsExcluded") is not True
            or scope.get("teslaCompatibleConnectorsOnly") is not True
            or scope.get("parkingFeesIncluded") is not False
            or not isinstance(stations, list) or not isinstance(profiles, list)
            or stats.get("stationCount") != len(stations)
            or stats.get("tariffProfileCount") != len(profiles)
            or data.get("source", {}).get("officialParisOpenData") is not True
            or not data.get("source", {}).get("sha256")):
        raise ValueError("Belib station-base technical contract failed")
    ids: set[str] = set()
    evses: set[str] = set()
    for station in stations:
        key = station.get("stationId")
        if (not key or key in ids or station.get("operatorSourceValue") != "TOTALENERGIES"
                or station.get("brandSourceValue") != "Belib'" or not isinstance(station.get("configurations"), list)):
            raise ValueError("Belib station identity or operator mismatch")
        ids.add(key)
        for config in station["configurations"]:
            if config.get("kind") not in {"AC", "DC"} or not isinstance(config.get("evseIds"), list):
                raise ValueError("Belib connector grouping invalid")
            for evse in config["evseIds"]:
                if not isinstance(evse, str) or not evse.startswith("FR*V75*"):
                    raise ValueError("Belib source EVSE identifier invalid")
                evses.add(evse)
    if stats.get("chargePointCount") != len(evses):
        raise ValueError("Belib EVSE relation count differs from output")
    if not (root / SUMMARY).is_file() or not (root / BASE_REPORT).is_file():
        raise ValueError("Belib technical report missing")
    return {"tariff": tariff, "stations": data}


def run(out: Path, *, source: Path = ROOT, static_input: Path | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Belib output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    baseline = source / TARIFF
    if not baseline.is_file():
        raise FileNotFoundError(baseline)
    prior = out / TARIFF
    prior.parent.mkdir(parents=True, exist_ok=True)
    if not prior.exists():
        shutil.copy2(baseline, prior)
    tariff_command = [sys.executable, str(ROOT / "scripts/belib_official.py"), "--out", "out/belib"]
    result = runner(tariff_command, cwd=out, capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        failure_report(out, "official_tariff")
        raise RuntimeError("Historical Belib official extraction failed")
    candidate = out / "out/belib/belib_official_paris.json"
    if not candidate.is_file():
        raise ValueError("Historical Belib tariff output missing")
    candidate.replace(prior)
    summary = out / SUMMARY
    summary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out / "out/belib/SUMMARY.md", summary)
    validate_tariff(out)
    station_command = [sys.executable, str(ROOT / "scripts/belib_station_base.py"),
                       "--tariffs", str(prior), "--out", str(out / STATIONS), "--report", str(out / BASE_REPORT)]
    if static_input is not None:
        station_command.extend(["--input", str(static_input)])
    result = runner(station_command, cwd=out, capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        failure_report(out, "station_base")
        raise RuntimeError("Historical Belib station-base build failed")
    validate_output(out)
    status = {"dataset": "belib-run-status", "operator": "Belib'", "status": "success",
              "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    (out / RUN_STATUS).write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()
    run(args.out, source=args.source)


if __name__ == "__main__":
    main()
