#!/usr/bin/env python3
"""Run preserved scripts that write relative paths in an isolated directory."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

METHODS = {
    "etotem_inventory": ("scripts/etotem_direct_station_inventory.py", "data/national/etotem_direct_stations_france.json.gz"),
    "qwello_saone_et_loire": ("scripts/qwello_saone_et_loire_official.py", "data/operator_direct/qwello_saone_et_loire_official.json"),
    "reveo_official": ("scripts/reveo_official.py", "data/operator_direct/reveo_official_france.json"),
}


def validate_output(out: Path, method: str) -> dict:
    if method not in METHODS:
        raise ValueError("Unsupported relative-output method")
    if method == "qwello_saone_et_loire":
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        evidence = payload.get("sourceEvidence") or {}
        sources = evidence.get("sources") or []
        fingerprint = evidence.get("relevantTariffFingerprintSha256")
        summary = out / "reports/qwello_saone_et_loire/latest_summary.md"
        if (payload.get("schemaVersion") != "1.0.0" or payload.get("dataset") != "qwello-saone-et-loire-official-france"
                or payload.get("operator") != "Qwello" or payload.get("country") != "FR"
                or payload.get("classification", {}).get("sydeslIsCurrentCpo") is not False
                or payload.get("classification", {}).get("exactCurrentStationTariffLookupRequired") is not True
                or payload.get("operatorDirect", {}).get("currentTariffModel", {}).get("exactCurrentPriceMachineVerified") is not False
                or payload.get("roaming", {}).get("mustRemainSeparateFromDirectTariff") is not True
                or evidence.get("officialOnly") is not True or len(sources) != 2
                or any(row.get("httpStatus") != 200 or len(row.get("rawSha256", "")) != 64 for row in sources)
                or not isinstance(fingerprint, str) or len(fingerprint) != 64
                or not summary.is_file() or not summary.read_text(encoding="utf-8").strip()):
            raise ValueError("Qwello official relative-output contract invalid")
        return payload
    if method == "reveo_official":
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        evidence = payload.get("sourceEvidence") or {}
        technical = payload.get("technicalTariffEvidence") or {}
        sources = evidence.get("sources") or []
        fingerprint = evidence.get("relevantTariffFingerprintSha256")
        report = out / "reports/reveo/latest_summary.md"
        if (payload.get("schemaVersion") != "1.0.0" or payload.get("dataset") != "reveo-official-france"
                or payload.get("operator") != "Révéo" or payload.get("country") != "FR"
                or payload.get("directTariffModel", {}).get("exactStationTariffLookupRequired") is not True
                or payload.get("roaming", {}).get("separateFromDirectRetail") is not True
                or not isinstance(technical.get("activeTariffs"), list)
                or any(row.get("classification") != "cpo_ocpi_tariff_transmitted_to_roaming_via_gireve" for row in technical["activeTariffs"])
                or len(technical.get("feedSha256", "")) != 64
                or evidence.get("officialOnly") is not True or len(sources) != 4
                or any(row.get("httpStatus") != 200 or len(row.get("rawSha256", "")) != 64 for row in sources)
                or not isinstance(fingerprint, str) or len(fingerprint) != 64
                or not report.is_file() or not report.read_text(encoding="utf-8").strip()):
            raise ValueError("Révéo official relative-output contract invalid")
        return payload
    with gzip.open(out / METHODS[method][1], "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    stations = payload.get("stations") or []
    ids = [row.get("stationId") for row in stations]
    if (payload.get("schemaVersion") != "1.0.0" or payload.get("operator") != "e-Totem"
            or payload.get("country") != "FR"
            or payload.get("scope", {}).get("physicalCpoDirectOnly") is not True
            or payload.get("scope", {}).get("roamingIncluded") is not False
            or not isinstance(payload.get("sourceDatasets"), list)
            or payload.get("counts", {}).get("stationCount") != len(stations)
            or any(not x for x in ids) or len(ids) != len(set(ids))
            or payload.get("counts", {}).get("pdcCount") != sum(len(row.get("pdcs") or []) for row in stations)
            or any(row.get("pdcCount") != len(row.get("pdcs") or []) for row in stations)):
        raise ValueError("e-Totem technical contract invalid")
    return payload


def run(out: Path, method: str, *, runner=subprocess.run) -> None:
    if method not in METHODS:
        raise ValueError("Unsupported relative-output method")
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Relative-output method must run outside checkout")
    out.mkdir(parents=True, exist_ok=True)
    result = runner([sys.executable, str(ROOT / METHODS[method][0])],
                    cwd=out, capture_output=True, text=True, timeout=1200, check=False)
    if result.returncode:
        raise RuntimeError(f"Historical {method} method failed")
    if method == "qwello_saone_et_loire":
        generated = out / "out/qwello_saone_et_loire"
        output = out / METHODS[method][1]
        summary = out / "reports/qwello_saone_et_loire/latest_summary.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        summary.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(generated / "qwello_saone_et_loire_official.json", output)
        shutil.copy2(generated / "SUMMARY.md", summary)
        shutil.rmtree(out / "out")
    elif method == "reveo_official":
        generated = out / "out/reveo"
        output = out / METHODS[method][1]
        summary = out / "reports/reveo/latest_summary.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        summary.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(generated / "reveo_official_france.json", output)
        shutil.copy2(generated / "SUMMARY.md", summary)
        shutil.rmtree(out / "out")
    validate_output(out, method)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=sorted(METHODS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.method)


if __name__ == "__main__":
    main()
