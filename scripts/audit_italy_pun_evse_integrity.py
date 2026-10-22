#!/usr/bin/env python3
"""Validate an Italy PUN national snapshot before V9 tile generation.

Read-only validation: never derives rankable rates from raw PUN tariff fields.
"""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path


def audit(payload):
    stations = payload.get("stations") or []
    evses = payload.get("evses") or []
    station_keys = [s.get("stationKey") for s in stations]
    evse_ids = [e.get("evseId") for e in evses]
    station_evse_ids = [e.get("evseId") for s in stations for e in s.get("evses", [])]
    errors = []
    if payload.get("country") != "IT" or payload.get("dataset") != "pun-national-italy":
        errors.append("incorrect PUN dataset/country")
    if len(stations) < 29696:
        errors.append("national station count below pinned Stable reference")
    if len(evses) < 75025:
        errors.append("national EVSE count below previous PUN reference")
    if len(set(station_keys)) != len(station_keys) or None in station_keys:
        errors.append("missing/duplicate station keys")
    if len(set(evse_ids)) != len(evse_ids) or None in evse_ids:
        errors.append("missing/duplicate EVSE IDs")
    if Counter(station_evse_ids) != Counter(evse_ids):
        errors.append("station EVSE membership not a bijection")
    if payload.get("scope", {}).get("punTariffsRankable") is not False:
        errors.append("raw PUN tariffs must be non-rankable")
    if any(s.get("evseCount") != len(s.get("evses", [])) for s in stations):
        errors.append("station-level EVSE count mismatch")
    return {
        "country": "IT", "stationCount": len(stations), "uniqueEvseCount": len(evses),
        "linkedEvseOccurrences": len(station_evse_ids),
        "nonRankablePunTariffs": payload.get("scope", {}).get("punTariffsRankable") is False,
        "readyToGenerateTiles": not errors,
        "readyForProductionCutover": False,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    payload = json.loads(gzip.decompress(raw) if args.input.name.endswith(".gz") else raw)
    report = audit(payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
