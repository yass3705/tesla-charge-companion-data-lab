#!/usr/bin/env python3
"""Collect preserved CK guest details against one signed operator snapshot."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT
from v9_rebuild.uk_connected_kerb_operator import LOCATIONS, OUTPUTS, TARIFFS, validate_output as validate_operator

DETAILS = Path("data/national/uk_connected_kerb_app_details.json.gz")
OFFERS = Path("data/national/uk_connected_kerb_app_direct_offers.json.gz")
REPORT = Path("reports/uk/connected-kerb-app-collection-latest.json")
V9 = Path("data/national/uk_connected_kerb_v9.json.gz")
CANDIDATE = Path("v9-production-runtime/data/v9/uk-connected-kerb-offers.candidate.json")
DOC = Path("docs/connected-kerb-uk-integration-2026-10-07.json")


def read_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def validate_app_output(out: Path) -> dict:
    operator = validate_operator(out)
    baseline = read_gzip(out / LOCATIONS)
    details = read_gzip(out / DETAILS)
    offers = read_gzip(out / OFFERS)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    v9 = read_gzip(out / V9)
    candidate = json.loads((out / CANDIDATE).read_text(encoding="utf-8"))
    doc = json.loads((out / DOC).read_text(encoding="utf-8"))
    stamp = baseline.get("collectedAt")
    public = {row["id"]: row for row in baseline.get("locations", []) if row.get("publish") is True}
    source_offers = offers.get("offers")
    unresolved = report.get("unresolved")
    records = details.get("records")
    if not all(isinstance(rows, list) for rows in (source_offers, unresolved, records)):
        raise ValueError("Connected Kerb guest detail lists missing")
    exact = {(item.get("locationId"), item.get("evseUid"), item.get("connectorId")) for item in source_offers}
    if (not stamp or operator.get("collectedAt") != stamp
            or details.get("operatorBaselineCollectedAt") != stamp
            or offers.get("pricingScope") != "cpo_direct_standard_guest"
            or report.get("operatorBaselineCollectedAt") != stamp
            or report.get("requestedLocations") != len(public)
            or len(records) != len(public)
            or {item.get("operatorLocationId") for item in records} != set(public)
            or report.get("detailedLocationMatches") != sum("location" in item for item in records)
            or report.get("resolvedConnectors") != len(source_offers)
            or report.get("unresolvedConnectors") != len(unresolved)
            or len(exact) != len(source_offers)
            or report.get("searchPricesUsed") is not False
            or report.get("credentialsPersisted") is not False
            or report.get("publishedToV9") is not False
            or any(item.get("operatorBaselineCollectedAt") != stamp
                   or item.get("pricingScope") != "cpo_direct_standard_guest"
                   or item.get("locationId") not in public
                   or item.get("pricing", {}).get("currency") != "GBP"
                   or item.get("pricing", {}).get("timeBasis") != "UTC"
                   or not item.get("pricing", {}).get("energySlices") for item in source_offers)
            or v9.get("operatorBaselineCollectedAt") != stamp
            or v9.get("collectedAt") != offers.get("collectedAt")
            or candidate.get("activationStatus") != "pending_runtime_timezone_and_station_loader"
            or len(candidate.get("directOffers", [])) != len(source_offers)
            or doc.get("publishedToV9") is not False
            or doc.get("activeRuntime") is not None):
        raise ValueError("Connected Kerb guest provenance or publication contract invalid")
    runtime = v9.get("sources", [{}])[0]
    if runtime.get("pricingScope") != "cpo_direct_standard_guest":
        raise ValueError("Connected Kerb runtime channel changed")
    assigned = {(loc.get("id"), evse.get("uid"), conn.get("id"))
                for loc in runtime.get("locations", []) for evse in loc.get("evses", [])
                for conn in evse.get("connectors", []) if conn.get("validatedV9Offer")}
    if assigned != exact:
        raise ValueError("Connected Kerb exact connector assignment mismatch")
    return report


def run(out: Path, operator_state: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Connected Kerb guest method must run outside checkout")
    operator_state = operator_state.resolve()
    validate_operator(operator_state)
    for path in OUTPUTS:
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(operator_state / path, target)
    target_doc = out / DOC
    target_doc.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / DOC, target_doc)
    script_dir = out / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    for name in ("uk_connected_kerb_app_collect.py", "uk_connected_kerb_reconcile.py"):
        script = script_dir / name
        shutil.copy2(ROOT / "scripts" / name, script)
        result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                        text=True, timeout=1800, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical Connected Kerb {name} failed")
    validate_app_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--operator-state", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.operator_state)


if __name__ == "__main__":
    main()
