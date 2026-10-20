#!/usr/bin/env python3
"""Run the preserved Fastned direct inventories for France and the UK off checkout."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT


FILES = {"FR": Path("data/national/fastned_direct_stations_france.json.gz"),
         "GB": Path("data/national/fastned_direct_stations_uk.json.gz")}
UK_REPORT = Path("reports/uk/fastned-direct-uk-latest.json")


def validate_country(out: Path, country: str) -> dict:
    with gzip.open(out / FILES[country], "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    scope = data.get("scope") or {}
    locations = data.get("locations")
    profiles = data.get("pricingProfiles")
    count_key = "franceLocationCount" if country == "FR" else "ukLocationCount"
    point_key = "franceChargingPointCount" if country == "FR" else "ukChargingPointCount"
    if (data.get("dataset") != ("fastned-direct-operated-stations-france" if country == "FR" else "fastned-direct-operated-stations-uk")
            or data.get("operator") != "Fastned" or data.get("country") != country
            or scope.get("onlyFastnedCpoLocations") is not True
            or scope.get("partnerOperatorLocationsIncluded") is not False
            or scope.get("roamingTariffsIncluded") is not False
            or not isinstance(locations, list) or not isinstance(profiles, list)
            or data.get("counts", {}).get(count_key) != len(locations)
            or not data.get("source", {}).get("fingerprintSha256")):
        raise ValueError(f"Fastned {country} output contract failed")
    ids: set[str] = set()
    points = 0
    for station in locations:
        sid = station.get("stationId")
        if (not sid or sid in ids or not sid.startswith("fastned:") or station.get("country") != country
                or not isinstance(station.get("connectorTypes"), list)
                or not isinstance(station.get("chargingPoints"), int) or station["chargingPoints"] < 0):
            raise ValueError(f"Fastned {country} station identity invalid")
        ids.add(sid)
        points += station["chargingPoints"]
    if points != data["counts"].get(point_key):
        raise ValueError(f"Fastned {country} charging-point relation mismatch")
    if {row.get("id") for row in profiles} != {"fastned-standard", "fastned-app-direct", "fastned-gold"}:
        raise ValueError(f"Fastned {country} channel profile mismatch")
    if country == "GB":
        report = json.loads((out / UK_REPORT).read_text(encoding="utf-8"))
        if report.get("status") != "complete" or report.get("counts") != data["counts"]:
            raise ValueError("Fastned GB report differs from output")
    return data


def validate_output(out: Path) -> dict[str, dict]:
    return {country: validate_country(out, country) for country in FILES}


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Fastned output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    for country, script in (("FR", "fastned_station_inventory.py"), ("GB", "fastned_station_inventory_uk.py")):
        command = [sys.executable, str(ROOT / "scripts" / script)]
        if country == "FR":
            command.extend(["--out", str(out / FILES[country])])
        result = runner(command, cwd=out, capture_output=True, text=True, timeout=1800, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical Fastned {country} inventory failed")
        validate_country(out, country)
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
