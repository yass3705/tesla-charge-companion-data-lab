#!/usr/bin/env python3
"""Preserved Zephyre IRVE/ePowerDirect extraction and exact-EVSE compilation."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
from pathlib import Path

from v9_rebuild.electroverse import ROOT

EXTRACT = Path("scripts/zephyre/extract_zephyre_france.mjs")
COMPILE = Path("scripts/zephyre/compile_zephyre_v9_offers.mjs")
DATA = Path("data/zephyre/france/current/zephyre.json.gz")
SUMMARY = Path("data/zephyre/france/current/summary.json")
OFFERS = Path("v9-production-runtime/data/v9/france-zephyre-offers.json")


def validate_output(out: Path) -> dict:
    with gzip.open(out / DATA, "rt", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    summary = json.loads((out / SUMMARY).read_text(encoding="utf-8"))
    offers = json.loads((out / OFFERS).read_text(encoding="utf-8"))
    stations = snapshot.get("stations")
    unresolved = snapshot.get("unresolved")
    rows = offers.get("directOffers")
    if (snapshot.get("schemaVersion") != 1 or snapshot.get("country") != "FR"
            or snapshot.get("partyId") != "FR*ZP1" or snapshot.get("summary") != summary
            or not isinstance(stations, list) or not isinstance(unresolved, list)
            or summary.get("liveDetailStations") != len(stations)
            or summary.get("nearbyErrors") or summary.get("detailErrors")
            or (snapshot.get("errors") or {}).get("nearby") or (snapshot.get("errors") or {}).get("detail")
            or offers.get("country") != "FR" or offers.get("mode") != "verified_zephyre_direct"
            or not isinstance(rows, list)):
        raise ValueError("Zephyre snapshot or technical execution invalid")
    source_ids = [row.get("evseId") for row in stations]
    if (len(source_ids) != len(set(source_ids)) or any(not item or not item.startswith("FR*ZP1*") for item in source_ids)
            or len({row.get("evse") for row in unresolved}) != len(unresolved)):
        raise ValueError("Zephyre source EVSE identities invalid")
    eligible = {row["evseId"] for row in stations if row.get("multitenantDirectPaymentAvailable") is True
                and any(isinstance(part.get("price"), (int, float)) and part["price"] > 0
                        for part in ((row.get("tariff") or {}).get("priceComponents") or []))}
    ids = [evse for offer in rows for evse in offer.get("evseIds", [])]
    if (set(ids) != eligible or len(ids) != len(set(ids))
            or any(offer.get("verifiedScope") != "exact_evse"
                   or offer.get("directOperatorOnly") is not True
                   or not offer.get("pricing") for offer in rows)
            or (offers.get("sourceEvidence") or {}).get("liveDirectEvse") != len(eligible)):
        raise ValueError("Zephyre compiled exact-EVSE offers mismatch")
    return offers


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Zephyre workspace must be off checkout")
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
            raise RuntimeError("Historical Zephyre method failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
