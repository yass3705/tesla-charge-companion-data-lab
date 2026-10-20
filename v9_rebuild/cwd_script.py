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
    "avia_picoty_inventory": ("scripts/avia_picoty_national.py", "data/national/avia_picoty_direct_stations_france.json.gz"),
    "waat_inventory": ("scripts/waat_national.py", "data/national/waat_direct_stations_france.json.gz"),
    "swiss_fastned": ("scripts/finalize_swiss_fastned_official.py", "data/switzerland/fastned-official-direct-tariffs.json"),
}


def validate_output(out: Path, method: str) -> dict:
    if method not in METHODS:
        raise ValueError("Unsupported relative-output method")
    if method == "swiss_fastned":
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        report = json.loads((out / "docs/switzerland-fastned-finalization-2026-09-28.json").read_text(encoding="utf-8"))
        rows = payload.get("evses")
        ids = [row.get("evseId") for row in rows] if isinstance(rows, list) else []
        if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
                or payload.get("cpo") != "Fastned" or payload.get("operatorId") != "CH*FASTNED"
                or not isinstance(rows, list) or any(not value for value in ids)
                or len(ids) != len(set(ids))
                or any(row.get("currency") != "CHF" for row in rows)
                or any(row.get("source") != payload.get("sources", {}).get("officialPricing") for row in rows)
                or payload.get("counts", {}).get("nationalEvseCount") != len(rows)
                or payload.get("counts", {}).get("pricedEvseCount") != len(rows)
                or report.get("productionSource") != str(METHODS[method][1])
                or report.get("nationalEvseCount") != len(rows)
                or report.get("status") != ("complete" if rows else "partial")):
            raise ValueError("Swiss Fastned exact owner and output contract invalid")
        return payload
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
    if method == "avia_picoty_inventory":
        with gzip.open(out / METHODS[method][1], "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        report = json.loads((out / "data/reports/avia_picoty_station_inventory_report.json").read_text(encoding="utf-8"))
        stations = payload.get("stations")
        counts = payload.get("counts") or {}
        if (payload.get("schemaVersion") != "1.0.0"
                or payload.get("dataset") != "avia-volt-picoty-direct-stations-france"
                or payload.get("country") != "FR" or payload.get("operator") != "Picoty"
                or payload.get("scope", {}).get("operatorPrefix") != "FR*PY2"
                or payload.get("scope", {}).get("operatorDirectOnly") is not True
                or payload.get("scope", {}).get("roamingIncluded") is not False
                or not isinstance(stations, list) or counts.get("franceStationCount") != len(stations)
                or counts.get("franceEvseCount") != sum(len(row.get("evseIds") or []) for row in stations)
                or report.get("generatedAt") != payload.get("generatedAt")
                or report.get("counts") != counts
                or report.get("stationIds") != [row.get("stationIdNormalized") for row in stations]):
            raise ValueError("AVIA Picoty inventory technical contract invalid")
        ids = set()
        for station in stations:
            sid = station.get("stationIdNormalized")
            if (not sid or not sid.startswith("FRPY2") or sid in ids
                    or not isinstance(station.get("evseIds"), list)
                    or len(station["evseIds"]) != len(set(station["evseIds"]))
                    or station.get("directEurPerKwh") is not None
                    or station.get("rankableDirect") is not False):
                raise ValueError("AVIA Picoty exact scope or unpriced policy invalid")
            ids.add(sid)
        return payload
    if method == "waat_inventory":
        with gzip.open(out / METHODS[method][1], "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        report = json.loads((out / "data/reports/waat_station_inventory_report.json").read_text(encoding="utf-8"))
        stations = payload.get("stations")
        counts = payload.get("counts") or {}
        if (payload.get("schemaVersion") != "1.0.0"
                or payload.get("dataset") != "waat-direct-stations-france"
                or payload.get("country") != "FR"
                or payload.get("scope", {}).get("operatorPrefix") != "FR*WA2"
                or payload.get("scope", {}).get("operatorDirectOnly") is not True
                or payload.get("scope", {}).get("roamingIncluded") is not False
                or not isinstance(stations, list)
                or counts.get("franceStationCount") != len(stations)
                or counts.get("franceEvseCount") != sum(len(row.get("evses") or []) for row in stations)
                or report.get("counts") != counts):
            raise ValueError("WAAT inventory technical contract invalid")
        ids = set()
        evses = set()
        for station in stations:
            sid = station.get("stationIdNormalized")
            if (not sid or not sid.startswith("FRWA2") or sid in ids
                    or station.get("rankableDirect") is not False
                    or station.get("directEurPerKwh") is not None):
                raise ValueError("WAAT station scope or unpriced policy invalid")
            ids.add(sid)
            for point in station.get("evses") or []:
                eid = point.get("evseIdNormalized")
                if not eid or eid in evses:
                    raise ValueError("WAAT EVSE identity invalid")
                evses.add(eid)
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
