#!/usr/bin/env python3
"""Run the preserved exact-socket Midhope builder outside the checkout."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

PROOF = Path("reports/uk/connected-kerb-midhope-verified-2026-10-10.json")
RAW = Path("data/national/uk_connected_kerb_locations.json.gz")
OUTPUT = Path("data/national/uk_connected_kerb_midhope_verified_v9.json.gz")
REPORT = Path("reports/uk/connected-kerb-midhope-runtime-stage-2026-10-10.json")


def validate_output(out: Path) -> dict:
    proof = json.loads((out / PROOF).read_text(encoding="utf-8"))
    with gzip.open(out / RAW, "rt", encoding="utf-8") as stream:
        raw = json.load(stream)
    with gzip.open(out / OUTPUT, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    expected = {(row["evseId"], row["connectorId"], row["qrCode"])
                for row in proof["verifiedExactSockets"]}
    if len(expected) != len(proof["verifiedExactSockets"]):
        raise ValueError("Midhope proof has duplicate exact sockets")
    locations = payload.get("sources", [{}])[0].get("locations", [])
    if len(locations) != 1:
        raise ValueError("Midhope output must retain the exact station")
    station = locations[0]
    observed = {(evse.get("evse_id"), conn.get("id"), str(evse.get("physical_reference")))
                for evse in station.get("evses", []) for conn in evse.get("connectors", [])}
    source_station = [row for row in raw.get("locations", []) if row.get("id") == station.get("id")
                      and row.get("publish") is True]
    source_pairs = {(evse.get("evse_id"), conn.get("id"), str(evse.get("physical_reference")))
                    for row in source_station for evse in row.get("evses", [])
                    for conn in evse.get("connectors", [])}
    if (payload.get("country") != "GB" or payload.get("collectedAt") != raw.get("collectedAt")
            or observed != expected or not expected.issubset(source_pairs)
            or station.get("name") != "Midhope Road" or station.get("city") != "Woking"
            or report.get("exactConnectorCount") != len(expected)
            or report.get("stationId") != station.get("id")
            or set(report.get("evseIds", [])) != {item[0] for item in expected}
            or set(report.get("connectorIds", [])) != {item[1] for item in expected}
            or report.get("stagedFile") != str(OUTPUT)
            or report.get("evidence") != str(PROOF)
            or report.get("status") != "local_time_dst_verified_exact_connector_candidate"):
        raise ValueError("Midhope exact socket provenance or output mismatch")
    for evse in station["evses"]:
        for conn in evse["connectors"]:
            offer = conn.get("validatedV9Offer") or {}
            pricing = offer.get("pricing") or {}
            if (offer.get("evseIds") != [evse["evse_id"]]
                    or offer.get("connectorIds") != [conn["id"]]
                    or offer.get("currency") != "GBP"
                    or pricing.get("type") != "connected_kerb_midhope_guest_verified"
                    or offer.get("metadata", {}).get("pricingTimeZone") != "Europe/London"
                    or offer.get("metadata", {}).get("guestPreAuthorisationGbpNotCost") != 25):
                raise ValueError("Midhope offer scope or preauthorisation contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Midhope builder must run outside checkout")
    for path in (PROOF, RAW):
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, target)
    script = out / "scripts/uk_midhope_build_verified_runtime.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts/uk_midhope_build_verified_runtime.py", script)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical Midhope builder failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
