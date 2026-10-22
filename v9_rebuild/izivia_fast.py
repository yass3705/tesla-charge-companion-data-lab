#!/usr/bin/env python3
"""Run the preserved IZIVIA FAST capture and exact-station compiler off checkout."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

CAPTURE_SCRIPT = Path("scripts/izivia_fast_capture.py")
PROBE = Path("scripts/izivia_fast_probe.py")
BUILD_SCRIPT = Path("scripts/build_izivia_fast_offers.py")
NATIONAL = Path("reports/france/izivia/pan-national-pricing.json.gz")
CAPTURE = Path("data/operator_direct/izivia_fast_national_capture_2026_10_06.json.gz")
SUMMARY = Path("reports/france/izivia/izivia-fast-national-summary-2026-10-06.json")
OFFERS = Path("data/operator_direct/izivia_fast_direct_france_2026_10_06.json")
INVENTORY = Path("data/operator_direct/izivia_fast_inventory_france_2026_10_06.json")
TEMP_CAPTURE = Path("out/izivia-fast-national-capture.json.gz")
TEMP_SUMMARY = Path("out/izivia-fast-national-summary.json")
TEMP_OFFERS = Path("out/izivia-fast-direct-france.json")
TEMP_INVENTORY = Path("out/izivia-fast-inventory-france.json")


def _gz(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def validate_output(out: Path) -> dict:
    national = _gz(out / NATIONAL)
    capture = _gz(out / CAPTURE)
    summary = json.loads((out / SUMMARY).read_text(encoding="utf-8"))
    offers = json.loads((out / OFFERS).read_text(encoding="utf-8"))
    inventory = json.loads((out / INVENTORY).read_text(encoding="utf-8"))
    source_rows = [row for row in national.get("stations", []) if row.get("network") == "IZIVIA FAST"]
    source_ids = [row.get("stationId") for row in source_rows]
    rows = capture.get("stations")
    if (not isinstance(rows, list) or capture.get("summary") != summary
            or summary.get("network") != "IZIVIA FAST" or summary.get("inventoryStations") != len(rows)
            or len(source_ids) != len(set(source_ids))
            or set(source_ids) != {row.get("stationId") for row in rows}
            or len(rows) != len({row.get("stationId") for row in rows})
            or sum((summary.get("statuses") or {}).values()) != len(rows)
            or summary.get("detailFailureCount") or summary.get("unresolvedDetailRequests")
            or (summary.get("statuses") or {}).get("pricing_request_failed", 0)):
        raise ValueError("IZIVIA FAST capture incomplete or source identity changed")
    priced = {row["stationId"] for row in rows if row.get("status") == "direct_price_published"}
    offer_rows = offers.get("directOffers")
    inventory_rows = inventory.get("stations")
    archived_rules = json.loads((ROOT / OFFERS).read_text(encoding="utf-8"))["directOffers"][0]["pricing"]["rules"]
    if (offers.get("country") != "FR" or offers.get("mode") != "exact_station_direct_tariff"
            or inventory.get("country") != "FR" or not isinstance(offer_rows, list)
            or not isinstance(inventory_rows, list)
            or (offers.get("policy") or {}).get("capturedStations") != len(rows)
            or (offers.get("policy") or {}).get("pricedStations") != len({sid for offer in offer_rows for sid in offer.get("stationIds", [])})
            or any(offer.get("directOperatorOnly") is not True
                   or offer.get("metadata", {}).get("verifiedScope") != "exact_station"
                   or (offer.get("pricing") or {}).get("type") != "rules"
                   or (offer.get("pricing") or {}).get("rules") != archived_rules
                   for offer in offer_rows)):
        raise ValueError("IZIVIA FAST compiled offer contract invalid")
    offered = [sid for offer in offer_rows for sid in offer.get("stationIds", [])]
    if (any(len(row.get("stationIds", [])) != len(set(row.get("stationIds", []))) for row in offer_rows)
            or not set(offered) <= priced
            or any(row.get("sourceStationId") not in priced for row in inventory_rows)
            or len({row.get("sourceStationId") for row in inventory_rows}) != len(inventory_rows)):
        raise ValueError("IZIVIA FAST exact station scope invalid")
    return offers


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("IZIVIA FAST output must be off checkout")
    for source in (CAPTURE_SCRIPT, PROBE, BUILD_SCRIPT, NATIONAL):
        target = out / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / source, target)
    commands = (
        [sys.executable, str(out / CAPTURE_SCRIPT)],
        [sys.executable, str(out / BUILD_SCRIPT), str(out / TEMP_CAPTURE), str(out / TEMP_OFFERS),
         "--inventory-output", str(out / TEMP_INVENTORY)],
    )
    for command in commands:
        result = runner(command, cwd=out, capture_output=True, text=True, timeout=5400, check=False)
        if result.returncode:
            raise RuntimeError("Historical IZIVIA FAST method failed")
    for old, new in ((TEMP_CAPTURE, CAPTURE), (TEMP_SUMMARY, SUMMARY),
                     (TEMP_OFFERS, OFFERS), (TEMP_INVENTORY, INVENTORY)):
        target = out / new
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out / old, target)
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
