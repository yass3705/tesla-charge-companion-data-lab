#!/usr/bin/env python3
"""Read-only, dated TCC V9 nine-country tariff-gap evidence baseline.

This is deliberately NOT a live EVSE-level tariff audit and never publishes prices.
Its purpose is to make evidence dates, scopes and unresolved filtering explicit.
"""
import argparse
import json
from pathlib import Path

COUNTRIES = ("FR", "IT", "CH", "DE", "ES", "NL", "UK", "MA", "BE")
ROOT = Path(__file__).resolve().parents[1]
GLOBAL = "reports/tariff-scenarios/review-latest.json"
NL = "reports/netherlands/nl-cpo-unpriced-evse-inventory-2026-10-11.json"
AFTER = "reports/tariff-scenarios/after-minutes-production-verification-2026-10-11.json"
ACTIVE_STATUSES = ("AVAILABLE", "CHARGING")


def read(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def baseline(root=ROOT):
    global_review = read(root, GLOBAL)
    nl = read(root, NL)
    after = read(root, AFTER)
    if set(global_review["countries"]) != set(COUNTRIES):
        raise ValueError("Nine-country source census missing a TCC country")
    if global_review["sourceFilesScanned"] > global_review["sourceFilesEnumerated"]:
        raise ValueError("Scanned source count exceeds enumerated files")
    per_country = {}
    tesla = global_review["externalTeslaCatalogue"]
    for code in COUNTRIES:
        census = global_review["countrySourceCensus"][code]
        config = tesla["countries"][code]
        per_country[code] = {
            "datedSourceFilesScanned": census["files_scanned"],
            "datedTeslaStations": config["stations"],
            "scopeWarning": "Files and Tesla stations are NOT priced/public active EVSE counts.",
        }
    if nl["country"] != "NL" or len(nl["operatorStats"]) != 4:
        raise ValueError("Unexpected NL evidence scope")
    nl_operators = {}
    missing = active_missing = 0
    for code, stat in sorted(nl["operatorStats"].items()):
        all_connectors = stat["totalConnectors"]
        priced = stat["exactPricedConnectors"]
        unpriced = stat["unpricedConnectors"]
        if priced + unpriced != all_connectors:
            raise ValueError("NL priced/unpriced connector totals inconsistent")
        if sum(stat["statusUnpriced"].values()) != unpriced:
            raise ValueError("NL status inventory incomplete or duplicated")
        if sum(x["count"] for x in stat["unpricedByPower"]) != unpriced:
            raise ValueError("NL unpriced power breakdown inconsistent")
        active = sum(stat["statusUnpriced"].get(k, 0) for k in ACTIVE_STATUSES)
        missing += unpriced
        active_missing += active
        nl_operators[code] = {
            "name": stat["operator"], "allConnectors": all_connectors,
            "priced": priced, "missingDirectTariff": unpriced,
            "statusAvailableOrCharging": active,
            "connectorTypesType2CcsVerified": False,
            "publicAccessVerified": False,
        }
    if missing != nl["globalMissingConnectorCountAmongFourOperators"]:
        raise ValueError("NL four-operator summary mismatch")
    if after["affectedRealOffers"] != 84 or not after["pass"]:
        raise ValueError("After-minutes evidence no longer matches reviewed scope")
    verified = len(after["officialDirectOrMembershipRulesVerified"])
    unverified = after["providerCounts"].get("Electra eMSP")
    if verified + unverified != after["affectedRealOffers"]:
        raise ValueError("After-minutes cohort mismatch")
    return {
        "schemaVersion": 1,
        "status": "DATED_BASELINE_NOT_LIVE_EVSE_AUDIT",
        "sourceRefs": {"global": GLOBAL, "nl": NL, "afterMinutes": AFTER},
        "sourceDates": {
            "globalReviewedAt": global_review["reviewedAt"],
            "nlSnapshotAt": nl["snapshotGeneratedAt"],
            "nlReportAt": nl["generatedAt"],
            "afterMinutesReportAt": after["generatedAt"],
        },
        "countries": per_country,
        "globalSourceCensus": {
            "filesEnumerated": global_review["sourceFilesEnumerated"],
            "filesScanned": global_review["sourceFilesScanned"],
            "unscanned": global_review["unscannedSourceFiles"],
            "teslaStationsReported": tesla["stationCount"],
            "notes": "File counts are schema/source census only; some country classifications can overlap.",
        },
        "netherlandsFourCpos": {
            "operators": nl_operators,
            "allMissingDirectTariff": missing,
            "availableOrChargingWithMissingDirectTariff": active_missing,
            "unresolvedFilters": ["Type 2 / CCS connector identity", "public access",
                                  "newer DOT-NL snapshot", "actual pricing-component simulation"],
            "notEquivalentTo": "Earlier 5,246 national incalculable cases (different population and causes).",
        },
        "franceAfterMinutes": {
            "offerSample": after["affectedRealOffers"],
            "directOrSubscriptionRulesProved": verified,
            "electraEmspUnprovedTimeComponent": unverified,
            "statusForUnproved": "tarif incalculable, not an estimated amount",
            "sourceScope": "Dated 2026-10-11 report; not a fresh country-wide EVSE census.",
        },
        "nextActions": [
            "Recompute nine-country source/EVSE/connector population on an exact new Data Lab SHA and Production candidate.",
            "Filter NL missing references to public available/occupied Type 2 or CCS EVSE before tariff analysis.",
            "Use DOT-NL as canonical direct CPO source unless absent, contradictory, or uncomputable.",
            "Separate no tariff, ambiguous tariff, and missing computation input per EVSE and offer channel.",
            "Resolve Electra 78 eMSP fee components only with evidence for each specific offer.",
            "Exercise all tariff families on current engine; retain source-native currency, power, time zone and contract.",
        ],
        "publication": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    doc = baseline(args.root)
    if args.check:
        print("V9 dated tariff-gap baseline integrity OK: nine countries, NL subpopulation and France fees")
    else:
        print(json.dumps(doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
