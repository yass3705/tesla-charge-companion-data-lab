#!/usr/bin/env python3
"""Read-only DOT-NL direct-CPO tariff compiler census by active Type 2/CCS connector.

This is a COMPILABILITY audit, never evidence of a fully priced charging
scenario, physical public access, or a tariff ready for TCC publication.
"""
import argparse
import collections
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from dotnl_netherlands_runtime import choose_tariff, date_of
from v9_nl_type2_ccs_scope_audit_20261012 import valid_nl, plug, ACTIVE

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/national/netherlands_dotnl/normalized.json.gz"
CATEGORIES = (
    "noNationalReference",
    "compiledNotSimulated",
    "ambiguousTariff",
    "sourceReferenceUnresolved",
    "notCurrentOrInactiveTariff",
    "thirdPartyOrNonDirectOnly",
    "unsupportedOrIncompleteContract",
)


def reason_category(keys, catalog, explanations):
    available = [catalog[k] for k in keys if k in catalog and isinstance(catalog[k], dict)]
    if not available:
        return "sourceReferenceUnresolved"
    reasons = set(explanations or {})
    if reasons and all(reason == "not_current" or reason == "no_current_element" for reason in reasons):
        return "notCurrentOrInactiveTariff"
    if reasons and all(reason.startswith("non_direct_tariff_type:") for reason in reasons):
        return "thirdPartyOrNonDirectOnly"
    return "unsupportedOrIncompleteContract"


def evaluate(data, *, example_limit=5):
    at = str(data.get("generatedAt") or "")
    day = date_of(at)
    if day is None:
        raise ValueError("DOT-NL generatedAt absent/invalid: cannot select tariff validity date")
    tariffs = data.get("tariffs")
    if not isinstance(tariffs, dict):
        raise ValueError("DOT-NL tariff index absent or not a keyed catalog")
    per_cpo = collections.defaultdict(collections.Counter)
    reasons = collections.Counter()
    examples = collections.defaultdict(list)
    stats = {
        "ambiguousTariffConnectors": 0,
        "unsupportedReasons": collections.Counter(),
    }
    compile_cache = {}
    selection_cache = {}
    examined = 0
    nonactive = 0
    excluded_plugs = 0
    ignored_stations = 0
    for station in data.get("stations") or []:
        if not valid_nl(station) or not str(station.get("stationId") or ""):
            ignored_stations += 1
            continue
        cpo = str(station.get("partyId") or "UNKNOWN").upper()
        for evse in station.get("evses") or []:
            status = str(evse.get("status") or "UNKNOWN").upper()
            for conn in evse.get("connectors") or []:
                kind = plug(conn.get("standard"))
                if kind is None:
                    excluded_plugs += 1
                    continue
                if status not in ACTIVE:
                    nonactive += 1
                    continue
                examined += 1
                keys = conn.get("tariffKeys") or []
                if not isinstance(keys, list):
                    raise ValueError("Unexpected tariffKeys schema")
                keys = [str(k) for k in keys]
                if not keys:
                    category = "noNationalReference"
                    details = []
                else:
                    before = dict(stats["unsupportedReasons"])
                    chosen, rules, err = choose_tariff(
                        keys, tariffs, day, stats, compile_cache, selection_cache
                    )
                    details = sorted(
                        k for k, n in stats["unsupportedReasons"].items()
                        if n > before.get(k, 0)
                    )
                    if chosen and rules:
                        category = "compiledNotSimulated"
                    elif err == "ambiguous":
                        category = "ambiguousTariff"
                    else:
                        category = reason_category(keys, tariffs, details)
                    if category != "compiledNotSimulated":
                        for reason in details:
                            reasons[reason] += 1
                per_cpo[cpo][category] += 1
                if category != "compiledNotSimulated" and len(examples[category]) < example_limit:
                    examples[category].append({
                        "partyId": cpo,
                        "stationId": station.get("stationId"),
                        "evseId": evse.get("evseId") or evse.get("uid"),
                        "connectorId": conn.get("id"),
                        "standard": conn.get("standard"),
                        "powerKw": conn.get("powerKw"),
                        "status": status,
                        "tariffKeys": keys[:10],
                        "compilerReasons": details[:10],
                    })
    totals = {key: sum(row[key] for row in per_cpo.values()) for key in CATEGORIES}
    if examined != sum(totals.values()):
        raise ValueError("Connector classes do not reconcile")
    if not examined:
        raise ValueError("No active Type 2/CCS connector to audit")
    summary = {
        "schemaVersion": 1,
        "status": "DIRECT_CPO_COMPILER_ACCEPTANCE_NOT_COMPLETE_PRICE_SIMULATION",
        "dataObservedAt": at,
        "tariffEffectiveDate": day.isoformat(),
        "scope": "Netherlands bounds, EVSE AVAILABLE/CHARGING, plugs Type 2/CCS, national direct CPO tariff refs only",
        "totalActiveType2CcsConnectorOccurrences": examined,
        "counts": totals,
        "cpoBreakdown": {
            name: {"activeType2Ccs": sum(row.values()), **{
                k: row[k] for k in CATEGORIES if row[k]
            }} for name, row in sorted(per_cpo.items())
        },
        "compilerRejectionReasons": dict(reasons.most_common()),
        "examplesByClass": dict(examples),
        "diagnostics": {
            "nonActiveType2Ccs": nonactive,
            "excludedNonType2Ccs": excluded_plugs,
            "excludedStations": ignored_stations,
            "distinctTariffKeysCompiled": len(compile_cache),
            "distinctReferenceSelections": len(selection_cache),
        },
        "limitations": [
            "Compiled means only that DOT-NL OCPI rules were converted; never that an actual session total is correct",
            "Tariff selectors can contain several offers; alternatives are not flattened to a station price",
            "Current validity is tested at the dataset date, not the reader's current local time",
            "No evidence of physical public access; garages and restricted facilities may still be included",
            "No eMSP or subscription substitution for direct CPO prices",
            "Time spent CONNECTED versus CHARGING, energy, SoC and tariff restrictions must still be simulated",
            "Do not promote this report or candidate tariffs as production V9 pricing",
        ],
        "publishedToTcc": False,
    }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--example-limit", type=int, default=5)
    args = parser.parse_args()
    if args.example_limit < 0 or args.example_limit > 20:
        raise ValueError("Example limit must be between 0 and 20")
    with gzip.open(args.input, "rt", encoding="utf-8") as f:
        data = json.load(f)
    report = evaluate(data, example_limit=args.example_limit)
    report["inputCompressedSha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    print(json.dumps({
        "source": report["inputCompressedSha256"],
        "at": report["dataObservedAt"],
        "activeConnectors": report["totalActiveType2CcsConnectorOccurrences"],
        "counts": report["counts"],
        "reasons": report["compilerRejectionReasons"],
        "blockedExamples": {k: v for k, v in report["examplesByClass"].items()
                            if k not in {"noNationalReference", "compiledNotSimulated"}},
        "topCpoMissing": sorted(
            ({"partyId": code, "missing": row.get("noNationalReference", 0)}
             for code, row in report["cpoBreakdown"].items()),
            key=lambda x: (-x["missing"], x["partyId"]),
        )[:15],
        "diagnostics": report["diagnostics"],
    }, ensure_ascii=False))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
