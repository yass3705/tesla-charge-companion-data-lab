#!/usr/bin/env python3
"""Preserved OZECAR producer/Monta method, isolated and checked per EVSE."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/ozecar/extract_ozecar.py")
PLAIN = Path("data/ozecar/france/ozecar-france-current.json")
DATA = Path(str(PLAIN) + ".gz")
REPORT = Path("docs/france-ozecar-direct-report-current.json")


def validate_output(out: Path) -> dict:
    plain = json.loads((out / PLAIN).read_text(encoding="utf-8"))
    with gzip.open(out / DATA, "rt", encoding="utf-8") as handle:
        compressed = json.load(handle)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    rows = plain.get("records")
    if (plain != compressed or plain.get("schemaVersion") != 1 or plain.get("country") != "FR"
            or plain.get("cpo") != "OZECAR" or not isinstance(rows, list)
            or report.get("schemaVersion") != 1 or report.get("country") != "FR"
            or report.get("cpo") != "OZECAR" or report.get("queriedEvses") != len(rows)
            or report.get("technicalErrorEvses")):
        raise ValueError("OZECAR technical collection or output invalid")
    ids = [row.get("evseKey") for row in rows]
    if (len(ids) != len(set(ids)) or any(not isinstance(key, str) or not key.startswith("FROZEE") for key in ids)
            or any(row.get("evseKey") != "".join(ch for ch in str((row.get("irve") or {}).get("id_pdc_itinerance", "")).upper() if ch.isalnum())
                   or row.get("rankableDirect") != (bool((row.get("live") or {}).get("resolved"))
                                                   and (row.get("live") or {}).get("status") != "private charger")
                   or not isinstance(row.get("directTariff"), list)
                   or row["directTariff"] != ((row.get("live") or {}).get("priceComponents") or [])
                   for row in rows)
            or report.get("rankableDirect") != sum(bool(row["rankableDirect"]) for row in rows)
            or report.get("private") != sum((row.get("live") or {}).get("status") == "private charger" for row in rows)
            or report.get("unresolved") != sum(not row["rankableDirect"] and (row.get("live") or {}).get("status") != "private charger" for row in rows)):
        raise ValueError("OZECAR exact EVSE identity or classification mismatch")
    return plain


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("OZECAR output must be off checkout")
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    result = runner([sys.executable, str(script), "--workers", "6", "--out", str(out / PLAIN),
                     "--report", str(out / REPORT)], cwd=out, capture_output=True,
                    text=True, timeout=3600, check=False)
    if result.returncode:
        raise RuntimeError("Historical OZECAR method failed")
    plain = out / PLAIN
    with gzip.open(out / DATA, "wt", encoding="utf-8") as handle:
        handle.write(plain.read_text(encoding="utf-8"))
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
