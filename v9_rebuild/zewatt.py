#!/usr/bin/env python3
"""Isolated preserved Ze-Watt static/dynamic/company extraction and compilation."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
from pathlib import Path

from v9_rebuild.electroverse import ROOT

EXTRACT = Path("scripts/zewatt/extract_zewatt_france.mjs")
COMPILE = Path("scripts/zewatt/compile_zewatt_v9_offers.mjs")
DATA = Path("data/zewatt/france/current/zewatt.json.gz")
SUMMARY = Path("data/zewatt/france/current/summary.json")
OFFERS = Path("v9-production-runtime/data/v9/france-zewatt-offers.json")


def validate_output(out: Path) -> dict:
    with gzip.open(out / DATA, "rt", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    summary = json.loads((out / SUMMARY).read_text(encoding="utf-8"))
    offers = json.loads((out / OFFERS).read_text(encoding="utf-8"))
    stations = snapshot.get("stations")
    rows = offers.get("directOffers")
    if (snapshot.get("schemaVersion") != 1 or snapshot.get("country") != "FR"
            or snapshot.get("network") != "Ze-Watt" or snapshot.get("summary") != summary
            or not isinstance(stations, list) or summary.get("uniqueSerials") != len(stations)
            or summary.get("companyErrors") or any(row.get("ok") is not True for row in stations)
            or offers.get("country") != "FR" or offers.get("mode") != "verified_zewatt_direct"
            or not isinstance(rows, list)):
        raise ValueError("Ze-Watt source or technical collection invalid")
    serials = [row.get("serial") for row in stations]
    if len(serials) != len(set(serials)) or any(not serial for serial in serials):
        raise ValueError("Ze-Watt station serial collision")
    eligible = {evse.get("idPdcItinerance") for row in stations
                if row.get("visitorStripe") is True and row.get("hasPositivePrice") is True
                for evse in ((row.get("static") or {}).get("evses") or []) if evse.get("idPdcItinerance")}
    ids = [evse for offer in rows for evse in offer.get("evseIds", [])]
    if (set(ids) != eligible or len(ids) != len(set(ids))
            or any(offer.get("verifiedScope") != "exact_evse" or offer.get("directOperatorOnly") is not True
                   or offer.get("metadata", {}).get("visitorStripeRequired") is not True
                   or not offer.get("pricing") for offer in rows)
            or (offers.get("sourceEvidence") or {}).get("exactEvseIds") != len(eligible)):
        raise ValueError("Ze-Watt exact EVSE compilation mismatch")
    return offers


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Ze-Watt workspace must be off checkout")
    for script in (EXTRACT, COMPILE):
        target = out / script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / script, target)
    commands = (["node", str(out / EXTRACT), "--concurrency", "4", "--out", str(out / DATA),
                 "--summary", str(out / SUMMARY)],
                ["node", str(out / COMPILE), "--snapshot", str(out / DATA), "--out", str(out / OFFERS)])
    for command in commands:
        result = runner(command, cwd=out, capture_output=True, text=True, timeout=3600, check=False)
        if result.returncode:
            raise RuntimeError("Historical Ze-Watt method failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
