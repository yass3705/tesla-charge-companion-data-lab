#!/usr/bin/env python3
"""Read-only DOT-NL connector scope census, not a tariff calculation or public-access proof."""
import argparse
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NL_BOUNDS = (50.5, 53.8, 3.0, 7.6)  # Matches DOT-NL runtime geographical filter.
ACTIVE = {"AVAILABLE", "CHARGING"}
TYPE2 = {"IEC_62196_T2", "TYPE2", "TYPE_2", "T2", "MENNEKES"}
CCS = {"IEC_62196_T2_COMBO", "CCS", "CCS2", "COMBO", "CCS_COMBO_2"}


def plug(standard):
    value = str(standard or "").upper().strip().replace("-", "_").replace(" ", "_")
    if value in TYPE2:
        return "TYPE_2"
    if value in CCS:
        return "CCS"
    return None


def valid_nl(st):
    coord = st.get("coordinates") or {}
    try:
        lat = float(coord["latitude"])
        lon = float(coord["longitude"])
    except (KeyError, ValueError, TypeError):
        return False
    return math.isfinite(lat) and math.isfinite(lon) and NL_BOUNDS[0] <= lat <= NL_BOUNDS[1] and NL_BOUNDS[2] <= lon <= NL_BOUNDS[3]


def scan(data):
    counters = collections.defaultdict(lambda: collections.Counter())
    status_count = collections.Counter()
    standards_excluded = collections.Counter()
    excluded_stations = 0
    seen_evse = collections.defaultdict(set)
    for st in data.get("stations") or []:
        if not valid_nl(st) or not str(st.get("stationId") or ""):
            excluded_stations += 1
            continue
        cpo = str(st.get("partyId") or "UNKNOWN").upper()
        for evse in st.get("evses") or []:
            status = str(evse.get("status") or "UNKNOWN").upper()
            for conn in evse.get("connectors") or []:
                kind = plug(conn.get("standard"))
                if kind is None:
                    standards_excluded[str(conn.get("standard") or "UNSPECIFIED")] += 1
                    continue
                row = counters[cpo]
                row["type2CcsConnectorOccurrences"] += 1
                row["type2Connectors" if kind == "TYPE_2" else "ccsConnectors"] += 1
                status_count[status] += 1
                refs = conn.get("tariffKeys") or []
                if not isinstance(refs, list):
                    raise ValueError("Unexpected DOT-NL connector tariff-key schema")
                has_ref = bool(refs)
                row["withNationalTariffReference" if has_ref else "withoutNationalTariffReference"] += 1
                if status in ACTIVE:
                    row["activeAvailableOrCharging"] += 1
                    row["activeWithTariffReference" if has_ref else "activeWithoutTariffReference"] += 1
                    seen_evse[cpo].add((str(st.get("stationId")), str(evse.get("evseId") or evse.get("uid") or "")))
                else:
                    row["notActiveOrUnknownStatus"] += 1
    operator_rows = {code: {**dict(vals), "distinctActiveEvseKeys": len(seen_evse[code])}
                     for code, vals in sorted(counters.items())}
    totals = {key: sum(values.get(key, 0) for values in operator_rows.values())
              for key in ("type2CcsConnectorOccurrences", "type2Connectors", "ccsConnectors",
                          "withNationalTariffReference", "withoutNationalTariffReference",
                          "activeAvailableOrCharging", "activeWithTariffReference",
                          "activeWithoutTariffReference", "notActiveOrUnknownStatus")}
    if totals["type2CcsConnectorOccurrences"] == 0:
        raise ValueError("No Type 2 or CCS connectors; inspect DOT-NL standard schema")
    if totals["type2CcsConnectorOccurrences"] != totals["withNationalTariffReference"] + totals["withoutNationalTariffReference"]:
        raise ValueError("DOT-NL tariff reference census mismatch")
    if totals["activeAvailableOrCharging"] != totals["activeWithTariffReference"] + totals["activeWithoutTariffReference"]:
        raise ValueError("DOT-NL active tariff reference census mismatch")
    return {
        "schemaVersion": 1,
        "scope": "DOT_NL_TYPE2_CCS_AVAILABLE_OR_CHARGING_NOT_PUBLIC_ACCESS_VERIFIED",
        "datasetGeneratedAt": data.get("generatedAt"),
        "statusMeaning": "AVAILABLE or CHARGING is a candidate for access investigation, not physical public-access verification",
        "operatorRows": operator_rows,
        "totals": totals,
        "evseStatusCountsOnSelectedPlugs": dict(sorted(status_count.items())),
        "excludedConnectorStandards": dict(sorted(standards_excluded.items())),
        "excludedInvalidOrOutOfBoundsStations": excluded_stations,
        "limitations": [
            "Counts physical connector occurrences, not necessarily unique plugs if provider IDs duplicate",
            "Station and EVSE statuses are read as is; unknown/out-of-order are never assumed active",
            "No station public-access proof; no garage or restricted-access approval inferred",
            "A tariff reference is not proof that the tariff is calculable or directly payable",
            "Missing tariff references are price unavailable, not automatically tariff ambiguous",
            "Power and per-EVSE pricing calculations require a later independent contract audit",
        ],
        "publication": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    with gzip.open(args.input, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    report = scan(data)
    report["inputCompressedSha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    report["inputPath"] = args.input.as_posix()
    formatted = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted, encoding="utf-8")
    else:
        print(formatted)


if __name__ == "__main__":
    main()
