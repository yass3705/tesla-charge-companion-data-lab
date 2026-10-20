#!/usr/bin/env python3
"""Execute the preserved TE63 exact PAN join outside the Git checkout."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

OUTPUT = Path("data/operator_direct/chargezy_te63_official_france.json")
REPORT = Path("reports/france/spie-citynetworks/chargezy-te63-summary.json")
RUNTIME = Path("v9-production-runtime/data/v9/france-chargezy-te63-offers.json")


def validate_output(out: Path) -> dict:
    payload = json.loads((out / OUTPUT).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    runtime = json.loads((out / RUNTIME).read_text(encoding="utf-8"))
    exact, special, gaps = (payload.get(key) for key in ("exact", "specialPaymentMode", "gaps"))
    if not all(isinstance(rows, list) for rows in (exact, special, gaps)):
        raise ValueError("TE63 output classification lists missing")
    coverage = payload.get("coverage") or {}
    ids = [row.get("id_pdc_itinerance") for row in exact + special + gaps]
    exact_ids = {row["id_pdc_itinerance"] for row in exact}
    offer_ids = [eid for offer in runtime.get("directOffers", []) for eid in offer.get("evseIds", [])]
    groups = {row["rule"] for row in exact}
    policy = runtime.get("policy") or {}
    if (payload.get("schemaVersion") != "1.0.0"
            or payload.get("dataset") != "chargezy-te63-official-direct-france"
            or payload.get("country") != "FR"
            or payload.get("operator") != "SPIE CityNetworks"
            or payload.get("network") != "CHARGEZY - TE63"
            or payload.get("classification", {}).get("directCpoOnly") is not True
            or payload.get("classification", {}).get("roamingIncluded") is not False
            or any(not value for value in ids) or len(ids) != len(set(ids))
            or coverage.get("panRows") != len(ids)
            or coverage.get("exactRows") != len(exact)
            or coverage.get("specialPaymentModeRows") != len(special)
            or coverage.get("gaps") != len(gaps)
            or report.get("coverage") != coverage
            or report.get("specialPaymentMode") != special
            or report.get("gaps") != gaps
            or runtime.get("mode") != "operator-direct-exact-evse"
            or policy.get("failClosed") is not True or policy.get("roamingIncluded") is not False
            or runtime.get("sourceEvidence", {}).get("exactRows") != len(exact)
            or sorted(offer_ids) != sorted(exact_ids)
            or len(offer_ids) != len(set(offer_ids))
            or len(runtime.get("directOffers", [])) != len(groups)
            or any(row.get("sourceUrl") != payload.get("source", {}).get("url") for row in exact)
            or any(offer.get("verifiedScope") != "exact_evse" or offer.get("directOperatorOnly") is not True
                   or offer.get("currency") != "EUR" for offer in runtime["directOffers"])):
        raise ValueError("TE63 exact EVSE and output contract invalid")
    return payload


def run(out: Path, *, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("TE63 script must run outside checkout")
    script = out / "scripts/chargezy_te63_official_direct.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts/chargezy_te63_official_direct.py", script)
    result = runner([sys.executable, str(script)], cwd=out, capture_output=True,
                    text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError("Historical TE63 exact PAN method failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
