#!/usr/bin/env python3
"""Isolated IZIVIA official parser, preserving FAST, Express, Lyon and Pass scope."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/izivia_official.py")
TEMP = Path("out/izivia/izivia_official_france.json")
TEMP_REPORT = Path("out/izivia/SUMMARY.md")
TEMP_DIAGNOSTIC = Path("out/izivia/DIAGNOSTIC.json")
OUTPUT = Path("data/operator_direct/izivia_official_france.json")
REPORT = Path("reports/izivia/latest_summary.md")
DIAGNOSTIC = Path("reports/izivia/latest_diagnostic.json")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    archived = json.loads((ROOT / OUTPUT).read_text(encoding="utf-8"))
    diagnostic = json.loads((out / DIAGNOSTIC).read_text(encoding="utf-8"))
    evidence = payload.get("sourceEvidence") or {}
    sources = evidence.get("sources") or []
    direct = payload.get("operatorDirectNetworks") or []
    if (payload.get("schemaVersion") != "1.1.0" or payload.get("dataset") != "izivia-official-france"
            or payload.get("country") != "FR" or payload.get("operator") != "IZIVIA / EDF business services"
            or payload.get("publicationStatus") != "candidate_validated_source"
            or payload.get("classification") != archived.get("classification")
            or direct != archived.get("operatorDirectNetworks")
            or payload.get("mobilityProvider") != archived.get("mobilityProvider")
            or len(direct) != 3 or any(row.get("operatorDirect") is not True for row in direct)
            or payload.get("mobilityProvider", {}).get("operatorDirect") is not False
            or evidence.get("officialOnly") is not True
            or {row.get("key") for row in sources} != {"fast", "express", "grand_lyon", "grand_lyon_offers", "pass", "roaming_fee", "paynow"}
            or any(row.get("httpStatus") != 200 for row in sources)
            or diagnostic.get("success") is not True
            or {key for key in diagnostic.get("sources", {}) if not key.endswith("_rendered")}
               != {row.get("key") for row in sources}
            or not (out / REPORT).read_text(encoding="utf-8").strip()):
        raise ValueError("IZIVIA official tariff scope or technical contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("IZIVIA work must be off checkout")
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    completed = runner([sys.executable, str(script), "--out", str(out / "out/izivia")],
                       cwd=out, capture_output=True, text=True, timeout=1200, check=False)
    if completed.returncode:
        raise RuntimeError("Historical IZIVIA official method failed")
    for old, new in ((TEMP, OUTPUT), (TEMP_REPORT, REPORT), (TEMP_DIAGNOSTIC, DIAGNOSTIC)):
        dest = out / new
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out / old, dest)
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
