#!/usr/bin/env python3
"""Execute the preserved Allego official method in isolated staging."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

OUTPUT = Path("data/operator_direct/allego_official_france.json")
REPORT = Path("reports/allego/latest_summary.md")
TEMP = Path("out/allego")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    evidence = payload.get("sourceEvidence") or {}
    sources = evidence.get("sources") or []
    direct = (payload.get("operatorDirect") or {}).get("allegoDirectCountryDefault") or {}
    if (payload.get("schemaVersion") != "1.0.0"
            or payload.get("dataset") != "allego-official-france"
            or payload.get("operator") != "Allego" or payload.get("country") != "FR"
            or payload.get("publicationStatus") != "candidate_validated_source"
            or payload.get("classification", {}).get("stationLevelPriceLookupRequiredForExactSimulation") is not True
            or direct.get("stationLevelPriceLookupRequired") is not True
            or direct.get("currency") != "EUR" or direct.get("billingUnit") != "kWh"
            or evidence.get("officialOnly") is not True
            or {row.get("key") for row in sources} != {"pricing", "overstay", "faq", "app", "station:fenouillet", "station:vauxbuin", "station:saran"}
            or any(row.get("httpStatus") != 200 for row in sources if row.get("key") != "app")):
        raise ValueError("Allego official technical contract invalid")
    if not isinstance(payload.get("stationValidationSamples"), list) or len(payload["stationValidationSamples"]) != 3:
        raise ValueError("Allego station sample evidence incomplete")
    fingerprint = evidence.get("relevantTariffFingerprintSha256")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
        raise ValueError("Allego tariff fact fingerprint invalid")
    if not (out / REPORT).is_file() or not (out / REPORT).read_text(encoding="utf-8").strip():
        raise ValueError("Allego summary missing")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Allego output must be outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    result = runner([sys.executable, str(ROOT / "scripts/allego_static_wrapper.py"), "--out", str(out / TEMP)],
                    cwd=out, capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError("Historical Allego official method failed")
    (out / OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    (out / REPORT).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out / TEMP / "allego_official_france.json", out / OUTPUT)
    shutil.copy2(out / TEMP / "SUMMARY.md", out / REPORT)
    shutil.rmtree(out / "out")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
