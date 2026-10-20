#!/usr/bin/env python3
"""Run the existing IONITY Direct FR/IT/DE/GB methods as one isolated family."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT


COUNTRIES = {"FR": "france", "IT": "italy", "DE": "germany", "GB": "uk"}


def output_path(country: str) -> Path:
    return Path(f"data/national/ionity_direct_stations_{COUNTRIES[country]}.json.gz")


def validate_country(out: Path, country: str) -> dict:
    with gzip.open(out / output_path(country), "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    scope = data.get("scope") or {}
    locations = data.get("locations")
    count_field = "ukLocationCount" if country == "GB" else "countryLocationCount"
    connector_field = "ukConnectorCount" if country == "GB" else "countryConnectorCount"
    if (data.get("dataset") != f"ionity-direct-operated-stations-{country.lower()}"
            or data.get("operator") != "IONITY" or data.get("country") != country
            or scope.get("requiredCpoIdentifier") != "IONITY_CPO"
            or scope.get("subscriberTariffsIncluded") is not False
            or scope.get("roamingTariffsIncluded") is not False
            or not isinstance(locations, list)
            or data.get("counts", {}).get(count_field) != len(locations)):
        raise ValueError(f"IONITY {country} output contract failed")
    if country == "GB" and scope.get("currency") != "GBP":
        raise ValueError("IONITY GB currency mismatch")
    ids: set[str] = set()
    connector_count = 0
    for location in locations:
        uid = location.get("uuid")
        connectors = location.get("connectors")
        if (not uid or uid in ids or location.get("country") != country
                or location.get("cpoIdentifier") != "IONITY_CPO" or not isinstance(connectors, list)
                or location.get("pricedConnectorCount") != len(connectors)):
            raise ValueError(f"IONITY {country} location identity invalid")
        ids.add(uid)
        connector_count += len(connectors)
        for connector in connectors:
            if (not connector.get("uuid") or not isinstance(connector.get("powerKw"), (float, int))
                    or connector["powerKw"] <= 0):
                raise ValueError(f"IONITY {country} connector invalid")
            price = connector.get("pricePerKwhGbp" if country == "GB" else "pricePerKwhEur")
            if not isinstance(price, (float, int)) or price <= 0:
                raise ValueError(f"IONITY {country} direct price field invalid")
    if data["counts"].get(connector_field) != connector_count:
        raise ValueError(f"IONITY {country} connector relation mismatch")
    return data


def validate_output(out: Path) -> dict[str, dict]:
    return {country: validate_country(out, country) for country in COUNTRIES}


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("IONITY output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    for country in COUNTRIES:
        command = ([sys.executable, str(ROOT / "scripts/ionity_station_tariffs_uk.py")]
                   if country == "GB" else [sys.executable, str(ROOT / "scripts/ionity_station_tariffs.py"),
                                             "--country", country, "--out", str(out / output_path(country))])
        result = runner(command, cwd=out, capture_output=True, text=True, timeout=1800, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical IONITY {country} extraction failed")
        validate_country(out, country)
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
