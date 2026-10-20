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
    "swiss_lidl": ("scripts/finalize_swiss_lidl_official.py", "data/switzerland/lidl-official-direct-tariffs.json"),
    "swiss_ionity": ("scripts/finalize_swiss_ionity_national.py", "data/switzerland/ionity-official-national-direct-tariffs.json"),
    "swiss_plenitude": ("scripts/finalize_swiss_plenitude_official.py", "data/switzerland/plenitude-official-direct-tariffs.json"),
    "swiss_ail": ("scripts/finalize_swiss_ail_emoti.py", "data/switzerland/ail-emoti-official-direct-tariffs.json"),
    "swiss_ebs": ("scripts/finalize_swiss_ebs_ecarup.py", "data/switzerland/ebs-ecarup-direct-tariffs.json"),
    "swiss_ewd": ("scripts/finalize_swiss_ewd_official.py", "data/switzerland/ewd-official-direct-tariffs.json"),
    "swiss_migrol": ("scripts/finalize_swiss_migrol_official.py", "data/switzerland/migrol-official-direct-tariffs.json"),
    "swiss_autosense": ("scripts/finalize_swiss_autosense_amag.py", "data/switzerland/autosense-amag-direct-tariffs.json"),
    "swiss_chevp": ("scripts/finalize_swiss_chevp_evpass.py", "data/switzerland/chevp-evpass-official-direct-tariffs.json"),
    "swiss_shell_evpass": ("scripts/finalize_swiss_shell_evpass_official.py", "data/switzerland/shell-evpass-official-direct-tariffs.json"),
}


def validate_output(out: Path, method: str) -> dict:
    if method not in METHODS:
        raise ValueError("Unsupported relative-output method")
    if method in {"swiss_autosense", "swiss_chevp", "swiss_shell_evpass"}:
        operator, label = {
            "swiss_autosense": ("CH*AUTOSENSE", "autosense"),
            "swiss_chevp": ("CHEVP", "chevp"),
            "swiss_shell_evpass": ("CH*SHE", "shell"),
        }[method]
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        report = json.loads((out / f"docs/switzerland-{label}-finalization-2026-09-28.json").read_text(encoding="utf-8"))
        rows = payload.get("evses")
        unresolved = payload.get("unresolved")
        if not isinstance(rows, list) or not isinstance(unresolved, list):
            raise ValueError(f"Swiss {label} output lists missing")
        ids = [row.get("evseId") for row in rows]
        unresolved_ids = [row.get("evseId") for row in unresolved]
        all_ids = ids if method == "swiss_shell_evpass" else ids + unresolved_ids
        counts = payload.get("counts") or {}
        if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
                or payload.get("operatorId") != operator
                or any(not value or not value.startswith(operator + ("*E" if operator != "CHEVP" else "E")) for value in all_ids)
                or len(all_ids) != len(set(all_ids))
                or any(row.get("currency") != "CHF" for row in rows)
                or counts.get("nationalEvseCount") != len(all_ids)
                or counts.get("pricedEvseCount") != len(all_ids) - len(unresolved_ids)
                or counts.get("unresolvedEvseCount") != len(unresolved_ids)
                or report.get("productionSource") != str(METHODS[method][1])
                or report.get("status") != ("complete" if all_ids and not unresolved else "partial")
                or any(report.get(key) != counts.get(key) for key in ("nationalEvseCount", "pricedEvseCount", "unresolvedEvseCount"))):
            raise ValueError(f"Swiss {label} exact EVSE contract invalid")
        if method == "swiss_shell_evpass":
            if (not set(unresolved_ids).issubset(set(ids))
                    or any((row.get("pricePerKwh") is None) != (row["evseId"] in unresolved_ids) for row in rows)):
                raise ValueError("Swiss Shell/evpass missing-price policy invalid")
        elif method == "swiss_autosense":
            if any(not row.get("stationName", "").startswith("AMAG Charging Station")
                   or row.get("conditionalEligibleBrandPricePerKwh") is None for row in rows):
                raise ValueError("Swiss autoSense AMAG scope or conditional tariff invalid")
        elif any(row.get("maxPowerKw") is None or row.get("parkingPenalty") != "excluded; station-specific if applicable" for row in rows):
            raise ValueError("Swiss CHEVP exact power or parking scope invalid")
        return payload
    if method in {"swiss_ewd", "swiss_migrol"}:
        operator = "CH*EWD" if method == "swiss_ewd" else "CH*MIG"
        label = "ewd" if method == "swiss_ewd" else "migrol"
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        report = json.loads((out / f"docs/switzerland-{label}-finalization-2026-09-28.json").read_text(encoding="utf-8"))
        rows = payload.get("evses")
        if not isinstance(rows, list):
            raise ValueError(f"Swiss {label.upper()} EVSE list missing")
        ids = [row.get("evseId") for row in rows]
        unresolved = payload.get("unresolved", [])
        if not isinstance(unresolved, list):
            raise ValueError(f"Swiss {label.upper()} unresolved list invalid")
        unresolved_ids = {row.get("evseId") for row in unresolved}
        counts = payload.get("counts") or {}
        if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
                or payload.get("operatorId") != operator
                or any(not value or not value.startswith(operator + "*E") for value in ids)
                or len(ids) != len(set(ids)) or not unresolved_ids.issubset(set(ids))
                or any(row.get("currency") != "CHF" for row in rows)
                or any((row.get("pricePerKwh") is None) != (row["evseId"] in unresolved_ids) for row in rows)
                or counts.get("nationalEvseCount") != len(rows)
                or counts.get("pricedEvseCount") != len(rows) - len(unresolved_ids)
                or counts.get("unresolvedEvseCount") != len(unresolved_ids)
                or report.get("productionSource") != str(METHODS[method][1])
                or report.get("status") != ("complete" if rows and not unresolved else "partial")
                or report.get("nationalEvseCount") != len(rows)
                or report.get("pricedEvseCount") != len(rows) - len(unresolved_ids)
                or report.get("unresolvedEvseCount") != ((0 if rows else 1) if method == "swiss_ewd" else len(unresolved_ids))):
            raise ValueError(f"Swiss {label.upper()} exact EVSE contract invalid")
        return payload
    if method in {"swiss_ail", "swiss_ebs"}:
        operator = "CH*AIL" if method == "swiss_ail" else "CH*EBS"
        prefix = "ail" if method == "swiss_ail" else "ebs"
        archive = ("docs/switzerland-small-cpo-national-context-2026-09-28.json" if method == "swiss_ail" else
                   "docs/switzerland-ecarup-targeted-national-queries-2026-09-28.json")
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        report = json.loads((out / f"docs/switzerland-{prefix}-finalization-2026-09-28.json").read_text(encoding="utf-8"))
        source = json.loads((out / archive).read_text(encoding="utf-8"))
        input_rows = source.get("operators", {}).get(operator)
        rows = payload.get("evses")
        unresolved = payload.get("unresolved")
        if not all(isinstance(value, list) for value in (input_rows, rows, unresolved)):
            raise ValueError(f"Swiss {prefix.upper()} source or output lists missing")
        input_ids = [row.get("evseId") for row in input_rows]
        output_ids = [row.get("evseId") for row in rows + unresolved]
        counts = payload.get("counts") or {}
        if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
                or payload.get("operatorId") != operator
                or any(not value or not value.startswith(operator + "*E") for value in input_ids)
                or len(input_ids) != len(set(input_ids))
                or sorted(input_ids) != sorted(output_ids)
                or len(output_ids) != len(set(output_ids))
                or counts.get("nationalEvseCount") != len(input_rows)
                or counts.get("pricedEvseCount") != len(rows)
                or counts.get("unresolvedEvseCount") != len(unresolved)
                or report.get("productionSource") != str(METHODS[method][1])
                or report.get("status") != ("complete" if input_rows and not unresolved else "partial")
                or any(report.get(key) != counts.get(key) for key in ("nationalEvseCount", "pricedEvseCount", "unresolvedEvseCount"))):
            raise ValueError(f"Swiss {prefix.upper()} exact EVSE contract invalid")
        if method == "swiss_ail" and any(row.get("currency") != "CHF" or row.get("powerKw", 1000) > 22 for row in rows):
            raise ValueError("Swiss AIL <=22 kW tariff scope invalid")
        if method == "swiss_ebs" and any(row.get("tariff", {}).get("currency") != "CHF" or
                                         not row.get("matchedPublicConnectors") or
                                         any(point.get("distanceMeters", 1000) > 50 for point in row["matchedPublicConnectors"])
                                         for row in rows):
            raise ValueError("Swiss EBS exact public connector scope invalid")
        return payload
    if method == "swiss_plenitude":
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        report = json.loads((out / "docs/switzerland-plenitude-finalization-2026-09-28.json").read_text(encoding="utf-8"))
        atlas = json.loads((out / "data/switzerland/pln-direct-tariffs.json").read_text(encoding="utf-8"))
        rows = payload.get("evses")
        unresolved = payload.get("unresolved")
        if not isinstance(rows, list) or not isinstance(unresolved, list):
            raise ValueError("Swiss Plenitude output lists missing")
        ids = [row.get("evseId") for row in rows + unresolved]
        counts = payload.get("counts") or {}
        if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
                or payload.get("cpo") != "Plenitude On The Road" or payload.get("operatorId") != "CH*PLN"
                or atlas.get("country") != "CH" or atlas.get("operatorId") != "CH*PLN"
                or not isinstance(atlas.get("stations"), list)
                or any(not value or not value.startswith("CH*PLN*E") for value in ids)
                or len(ids) != len(set(ids))
                or any(row.get("currency") != "CHF" or not isinstance(row.get("pricePerKwh"), (int, float)) for row in rows)
                or any(row.get("category") not in {"Quick", "Fast", "Fast+/Ultra Fast"} for row in rows)
                or counts.get("nationalEvseCount") != len(ids)
                or counts.get("pricedEvseCount") != len(rows)
                or counts.get("unresolvedEvseCount") != len(unresolved)
                or report.get("productionSource") != str(METHODS[method][1])
                or report.get("status") != ("complete" if ids and not unresolved else "partial")
                or any(report.get(key) != counts.get(key) for key in ("nationalEvseCount", "pricedEvseCount", "unresolvedEvseCount"))):
            raise ValueError("Swiss Plenitude exact connector and output contract invalid")
        return payload
    if method == "swiss_ionity":
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        report = json.loads((out / "docs/switzerland-ionity-national-finalization-2026-09-28.json").read_text(encoding="utf-8"))
        official = json.loads((out / "data/switzerland/ionity-official-direct-tariffs.json").read_text(encoding="utf-8"))
        rows = payload.get("evses")
        unresolved = payload.get("unresolved")
        if not isinstance(rows, list) or not isinstance(unresolved, list):
            raise ValueError("Swiss IONITY output lists missing")
        ids = [row.get("evseId") for row in rows + unresolved]
        counts = payload.get("counts") or {}
        if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
                or payload.get("cpo") != "IONITY" or payload.get("operatorId") != "CH*IOY"
                or official.get("country") != "CH" or official.get("operatorId") != "CH*IOY"
                or not isinstance(official.get("locations"), list)
                or any(not value or not value.startswith("CH*IOY*E") for value in ids)
                or len(ids) != len(set(ids))
                or any(row.get("currency") != "CHF" or not isinstance(row.get("pricePerKwh"), (int, float)) for row in rows)
                or any(not any(loc.get("uuid") == row.get("officialLocationUuid") for loc in official["locations"]) for row in rows)
                or counts.get("nationalEvseCount") != len(ids)
                or counts.get("pricedEvseCount") != len(rows)
                or counts.get("unresolvedEvseCount") != len(unresolved)
                or report.get("productionSource") != str(METHODS[method][1])
                or report.get("status") != ("complete" if ids and not unresolved else "partial")
                or any(report.get(key) != counts.get(key) for key in ("nationalEvseCount", "pricedEvseCount", "unresolvedEvseCount"))):
            raise ValueError("Swiss IONITY exact connector and output contract invalid")
        return payload
    if method == "swiss_lidl":
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        report = json.loads((out / "docs/switzerland-lidl-finalization-2026-09-28.json").read_text(encoding="utf-8"))
        rows = payload.get("evses")
        unresolved = payload.get("unresolved")
        ids = [row.get("evseId") for row in rows] if isinstance(rows, list) else []
        unresolved_ids = {row.get("evseId") for row in unresolved} if isinstance(unresolved, list) else set()
        counts = payload.get("counts") or {}
        if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
                or payload.get("cpo") != "Lidl" or payload.get("operatorId") != "CH*LDL"
                or not isinstance(rows, list) or not isinstance(unresolved, list)
                or any(not value or not value.startswith("CH*LDL*E") for value in ids)
                or len(ids) != len(set(ids)) or not unresolved_ids.issubset(set(ids))
                or any(row.get("currency") != "CHF" for row in rows)
                or any((row.get("directWebPricePerKwh") is None) != (row["evseId"] in unresolved_ids) for row in rows)
                or counts.get("nationalEvseCount") != len(rows)
                or counts.get("pricedEvseCount") != len(rows) - len(unresolved_ids)
                or counts.get("unresolvedEvseCount") != len(unresolved_ids)
                or report.get("productionSource") != str(METHODS[method][1])
                or report.get("nationalEvseCount") != len(rows)
                or report.get("status") != ("complete" if rows and not unresolved else "partial")):
            raise ValueError("Swiss Lidl exact EVSE and output contract invalid")
        return payload
    if method == "swiss_fastned":
        payload = json.loads((out / METHODS[method][1]).read_text(encoding="utf-8"))
        report = json.loads((out / "docs/switzerland-fastned-finalization-2026-09-28.json").read_text(encoding="utf-8"))
        rows = payload.get("evses")
        ids = [row.get("evseId") for row in rows] if isinstance(rows, list) else []
        if (payload.get("schemaVersion") != 1 or payload.get("country") != "CH"
                or payload.get("cpo") != "Fastned" or payload.get("operatorId") != "CH*FASTNED"
                or not isinstance(rows, list) or any(not value or not value.startswith("CH*FASTNED*E") for value in ids)
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
    archive_name = ("ionity-official-direct-tariffs.json" if method == "swiss_ionity" else
                    "pln-direct-tariffs.json" if method == "swiss_plenitude" else None)
    if archive_name:
        archive = ROOT / "data/switzerland" / archive_name
        destination = out / "data/switzerland" / archive_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive, destination)
    if method in {"swiss_ail", "swiss_ebs"}:
        archive_name = ("switzerland-small-cpo-national-context-2026-09-28.json" if method == "swiss_ail" else
                        "switzerland-ecarup-targeted-national-queries-2026-09-28.json")
        destination = out / "docs" / archive_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "docs" / archive_name, destination)
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
