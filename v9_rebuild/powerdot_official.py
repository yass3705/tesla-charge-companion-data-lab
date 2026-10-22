#!/usr/bin/env python3
"""Run preserved Powerdot official rules while separating CPO and eMSP channels."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

SCRIPT = Path("scripts/powerdot_official.py")
TEMP = Path("out/powerdot/powerdot_official_france.json")
TEMP_REPORT = Path("out/powerdot/SUMMARY.md")
OUTPUT = Path("data/operator_direct/powerdot_official_france.json")
REPORT = Path("reports/powerdot/latest_summary.md")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    archived = json.loads((ROOT / OUTPUT).read_text(encoding="utf-8"))
    evidence = payload.get("sourceEvidence") or {}
    sources = evidence.get("sources") or []
    direct = (payload.get("operatorDirect") or {}).get("adHocQr") or {}
    subscription = (payload.get("mobilityProviders") or {}).get("electroversePowerdotSubscription") or {}
    inventory = payload.get("inventory") or {}
    if (payload.get("schemaVersion") != "1.1.0" or payload.get("dataset") != "powerdot-official-france"
            or payload.get("country") != "FR" or payload.get("operator") != "Powerdot"
            or payload.get("publicationStatus") != "candidate_validated_source"
            or payload.get("classification") != archived.get("classification")
            or payload.get("operatorDirect") != archived.get("operatorDirect")
            or payload.get("mobilityProviders") != archived.get("mobilityProviders")
            or payload.get("specialPrograms") != archived.get("specialPrograms")
            or payload.get("fees") != archived.get("fees")
            or direct.get("nationalEurPerKwh") is not None
            or subscription.get("operatorDirect") is not False
            or subscription.get("exactResultingEurPerKwh") is not None
            or evidence.get("cpoFactsFromPowerdotOfficial") is not True
            or evidence.get("emspFactsFromElectroverseOfficial") is not True
            or {row.get("key") for row in sources} != {"faq", "driver", "electroverseSubscription", "powerdotInventoryDataset", "powerdotInventoryCsv"}
            or any(row.get("httpStatus") != 200 for row in sources if row.get("key") != "powerdotInventoryDataset")
            or not isinstance(inventory.get("rowCount"), int)
            or not isinstance(inventory.get("samples"), list)
            or not (out / REPORT).read_text(encoding="utf-8").strip()):
        raise ValueError("Powerdot official channel, price or technical contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Powerdot official work must be off checkout")
    script = out / SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / SCRIPT, script)
    completed = runner([sys.executable, str(script), "--out", str(out / "out/powerdot")],
                       cwd=out, capture_output=True, text=True, timeout=1200, check=False)
    if completed.returncode:
        raise RuntimeError("Historical Powerdot official method failed")
    for old, new in ((TEMP, OUTPUT), (TEMP_REPORT, REPORT)):
        destination = out / new
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out / old, destination)
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()
