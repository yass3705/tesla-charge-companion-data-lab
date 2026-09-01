#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_READY = 2214
EXPECTED_ENERGY_ONLY = 816
EXPECTED_MULTI = 1398
EXPECTED_COMPONENT_COUNTS = {
    "energy": 2214,
    "time": 1052,
    "session": 275,
    "parking": 700,
}
EXPECTED_COMPONENT_SETS = {
    "energy": 816,
    "energy+time": 548,
    "energy+parking+time": 386,
    "energy+parking": 189,
    "energy+session": 127,
    "energy+parking+session+time": 95,
    "energy+parking+session": 30,
    "energy+session+time": 23,
}
EXPECTED_SOURCE_UNITS = {
    "energy": "per_kWh",
    "session": "per_session",
    "time": "source_time_rate",
    "parking": "source_parking_rate",
}
KNOWN_PARKING_TRIGGERS = {"onNoEnergyDelivery", "onAfterTime"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def component_key(types: set[str]) -> str:
    ordered = [x for x in ("energy", "parking", "session", "time") if x in types]
    return "+".join(ordered)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ready", required=True)
    ap.add_argument("--out", default="data/reports/go_electric_italy_v9_component_unit_audit.json")
    args = ap.parse_args()

    payload = load(Path(args.ready))
    if payload.get("publicationAllowed") is not False:
        raise SystemExit("semantic ready artifact must remain publicationAllowed=false")
    offers = payload.get("offers")
    if not isinstance(offers, list) or len(offers) != EXPECTED_READY:
        raise SystemExit(f"expected {EXPECTED_READY} ready offers, got {len(offers) if isinstance(offers, list) else 'invalid'}")

    component_counts = Counter()
    component_sets = Counter()
    source_units = {k: Counter() for k in EXPECTED_COMPONENT_COUNTS}
    parking_triggers = Counter()
    parking_shapes = Counter()
    unknown_component_types = Counter()
    duplicate_components = []
    malformed_components = []
    parking_without_rule = []
    unsupported_parking_triggers = []
    session_only_candidates = []

    for offer in offers:
        eid = str(offer.get("punEvseId") or "")
        comps = offer.get("priceComponents")
        if not isinstance(comps, list) or not comps:
            malformed_components.append(eid)
            continue
        types: set[str] = set()
        for comp in comps:
            if not isinstance(comp, dict):
                malformed_components.append(eid)
                continue
            typ = str(comp.get("sourceType") or "")
            if typ in types:
                duplicate_components.append(f"{eid}:{typ}")
            types.add(typ)
            if typ not in EXPECTED_COMPONENT_COUNTS:
                unknown_component_types[typ or "<missing>"] += 1
                continue
            component_counts[typ] += 1
            source_units[typ][str(comp.get("sourceUnit") or "<missing>")] += 1

        key = component_key(types)
        component_sets[key] += 1
        if types == {"energy", "session"}:
            session_only_candidates.append(eid)

        if "parking" in types:
            restrictions = offer.get("restrictions")
            parking = restrictions.get("parking") if isinstance(restrictions, dict) else None
            if not isinstance(parking, dict):
                parking_without_rule.append(eid)
                continue
            trigger = str(parking.get("trigger") or "<missing>")
            parking_triggers[trigger] += 1
            parking_shapes["+".join(sorted(parking.keys()))] += 1
            if trigger not in KNOWN_PARKING_TRIGGERS:
                unsupported_parking_triggers.append(f"{eid}:{trigger}")

    if dict(component_counts) != EXPECTED_COMPONENT_COUNTS:
        raise SystemExit(f"component count drift: {dict(component_counts)}")
    if dict(component_sets) != EXPECTED_COMPONENT_SETS:
        raise SystemExit(f"component set drift: {dict(component_sets)}")
    if unknown_component_types or duplicate_components or malformed_components:
        raise SystemExit(
            f"semantic component contract drift: unknown={dict(unknown_component_types)} "
            f"duplicates={len(duplicate_components)} malformed={len(malformed_components)}"
        )

    unit_contract_ok = True
    for typ, expected in EXPECTED_SOURCE_UNITS.items():
        observed = source_units[typ]
        if set(observed) != {expected}:
            unit_contract_ok = False

    energy_only = component_sets["energy"]
    multi = len(offers) - energy_only
    if energy_only != EXPECTED_ENERGY_ONLY or multi != EXPECTED_MULTI:
        raise SystemExit(f"rankability baseline drift: energyOnly={energy_only}, multi={multi}")

    # This audit intentionally does NOT unlock anything. It distinguishes engine
    # capability from source-unit proof. The V9 engine has the required primitives,
    # while the Italy builder and source-unit evidence remain the gating layer.
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "country": "IT",
        "operator": "Go Electric Stations SRLS",
        "source": "NextCharge official Go Electric B2C semantic-ready artifact",
        "publicationAllowed": False,
        "multiComponentUnlockAllowed": False,
        "semanticReadyOffers": len(offers),
        "currentSafeRankableGoElectric": energy_only,
        "blockedMultiComponent": multi,
        "componentCounts": dict(component_counts),
        "componentSets": dict(component_sets),
        "sourceUnitLabels": {k: dict(v) for k, v in source_units.items()},
        "parkingAudit": {
            "offersWithParking": component_counts["parking"],
            "withoutParkingRestriction": len(parking_without_rule),
            "triggers": dict(parking_triggers),
            "shapes": dict(parking_shapes),
            "unsupportedTriggers": unsupported_parking_triggers[:50],
        },
        "runtimeCapability": {
            "verifiedStableBranch": "refactor/unified-data-engine-v9",
            "pricingEnginePath": "assets/v9/pricing-engine.js",
            "sessionEnginePath": "assets/v9/session-engine.js",
            "italyBuilderPath": "scripts/v9_build_italy_catalog.py",
            "supports": {
                "energy": "pricePerKwh",
                "session": "sessionFee",
                "connectedTime": "connectedTimePerMinuteEur",
                "postCharge": "postChargeFee.eurPerMinute",
            },
            "currentItalyBuilderReadsGoElectricPriceComponents": False,
        },
        "evidenceMatrix": {
            "energy": {
                "sourceUnit": "per_kWh",
                "sourceSemanticsStatus": "proven",
                "enginePrimitive": "pricePerKwh",
                "translationStatus": "supported_now",
            },
            "session": {
                "sourceUnit": "per_session",
                "sourceSemanticsStatus": "semantic_label_and_terms_component_type_available",
                "enginePrimitive": "sessionFee",
                "translationStatus": "candidate_requires_translation_qa",
                "candidateEnergyPlusSessionEvse": len(session_only_candidates),
            },
            "time": {
                "sourceUnit": "source_time_rate",
                "sourceSemanticsStatus": "billing_unit_not_officially_proven",
                "enginePrimitive": "connectedTimePerMinuteEur",
                "translationStatus": "blocked",
            },
            "parking": {
                "sourceUnit": "source_parking_rate",
                "sourceSemanticsStatus": "billing_unit_and_trigger_mapping_not_officially_proven",
                "enginePrimitive": "postChargeFee",
                "translationStatus": "blocked",
            },
        },
        "blockers": {
            "unresolvedTimeUnitOffers": component_counts["time"],
            "unresolvedParkingUnitOrTriggerMappingOffers": component_counts["parking"],
            "italyBuilderPriceComponentsMappingMissing": True,
        },
        "nextTranslationCandidate": {
            "componentSet": "energy+session",
            "evseCount": len(session_only_candidates),
            "proposedRuntimeMapping": {"energy": "pricePerKwh", "session": "sessionFee"},
            "activationAllowedByThisAudit": False,
        },
        "gates": {
            "readyCount2214": len(offers) == EXPECTED_READY,
            "componentCountsStable": dict(component_counts) == EXPECTED_COMPONENT_COUNTS,
            "componentSetsStable": dict(component_sets) == EXPECTED_COMPONENT_SETS,
            "sourceUnitLabelsStable": unit_contract_ok,
            "energyOnly816": energy_only == EXPECTED_ENERGY_ONLY,
            "multiComponent1398": multi == EXPECTED_MULTI,
            "sessionOnlyCandidate127": len(session_only_candidates) == 127,
            "parkingRulesPresent": not parking_without_rule,
            "parkingTriggersKnown": not unsupported_parking_triggers,
            "noMultiComponentUnlock": True,
            "publicationDisabled": True,
        },
    }
    if not all(report["gates"].values()):
        raise SystemExit(f"component unit audit gates failed: {report['gates']}")

    write(Path(args.out), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
