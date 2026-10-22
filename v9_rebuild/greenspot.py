#!/usr/bin/env python3
"""Run the preserved Greenspot collector outside the Git checkout."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/greenspot/extract_greenspot.py")
DATA = Path("data/greenspot/france/greenspot-france-current.json")
REPORT = Path("docs/france-greenspot-direct-report-current.json")


def validate_output(out: Path) -> dict:
    plain = json.loads((out / DATA).read_text(encoding="utf-8"))
    with gzip.open(out / (str(DATA) + ".gz"), "rt", encoding="utf-8") as stream:
        compressed = json.load(stream)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    rows = plain.get("records")
    if (plain != compressed or plain.get("schemaVersion") != 1 or plain.get("country") != "FR"
            or plain.get("cpo") != "Greenspot" or not isinstance(rows, list)
            or not isinstance(plain.get("unmatchedInventoryEvses"), list)
            or not isinstance(plain.get("siteErrors"), list)
            or report.get("schemaVersion") != 1 or report.get("country") != "FR"
            or report.get("cpo") != "Greenspot" or report.get("liveRecords") != len(rows)
            or report.get("siteErrors") != len(plain["siteErrors"])):
        raise ValueError("Greenspot snapshot/report mismatch")
    ids = [row.get("evseKey") for row in rows]
    priced = [row for row in rows if row.get("directTariff") is not None]
    if (len(ids) != len(set(ids)) or any(not isinstance(key, str) or not key.startswith("FRGSPE") for key in ids)
            or any(row.get("match") not in {"exact_irve_evse", "live_extra_same_queried_site"}
                   or row.get("source") != "greenspot_evcnet_public_map"
                   or row.get("tariffProvider") != 422
                   or row.get("directTariff") != (row.get("live") or {}).get("simpleTariff")
                   for row in rows)
            or any(row.get("match") == "exact_irve_evse" and
                   "".join(ch for ch in str((row.get("irve") or {}).get("id_pdc_itinerance", "")).upper() if ch.isalnum()) != row["evseKey"]
                   for row in rows)
            or report.get("liveRecordsWithSimpleTariff") != len(priced)
            or report.get("liveRecordsWithoutSimpleTariff") != len(rows) - len(priced)
            or report.get("unmatchedIrveEvses") != len(plain["unmatchedInventoryEvses"])):
        raise ValueError("Greenspot exact EVSE or tariff scope invalid")
    # A failed site means the archived output is diagnostic, not a complete collection.
    if plain["siteErrors"] or report.get("queriedSites") != report.get("uniqueCoordinateSites"):
        raise ValueError("Greenspot collection has incomplete site pagination")
    return plain


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Greenspot output must be off checkout")
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    result = runner([sys.executable, str(script), "--workers", "4", "--out", str(out / DATA),
                     "--report", str(out / REPORT)], cwd=out, capture_output=True,
                    text=True, timeout=2400, check=False)
    if result.returncode:
        raise RuntimeError("Historical Greenspot method failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
