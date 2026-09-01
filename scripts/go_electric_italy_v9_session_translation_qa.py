#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

GO_ELECTRIC = "Go Electric Stations SRLS"
EXPECTED_TOTAL_EVSE = 75025
EXPECTED_BASELINE_DIRECT = 26442
EXPECTED_BASELINE_GO_ELECTRIC_RANKABLE = 816
EXPECTED_TARGET = 127
EXPECTED_FINAL_DIRECT = 26569
EXPECTED_FINAL_GO_ELECTRIC_RANKABLE = 943
EXPECTED_REMAINING_BLOCKED_GO_ELECTRIC = 1271
TERMS_URL = "https://nextcharge.app/apps/map/apis/terms/v1.4/termsAndConditions.php?appearanceFontSize=medium&appearanceTheme=auto&lang=en"
TERMS_VERSION = "1.4"
TERMS_UPDATED = "2024-11-22"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def write_gz(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def component_map(tariff: dict) -> dict[str, dict]:
    out = {}
    for row in tariff.get("priceComponents") or []:
        if not isinstance(row, dict):
            continue
        typ = str(row.get("type") or "")
        if typ:
            if typ in out:
                raise ValueError(f"duplicate component {typ}")
            out[typ] = row
    return out


def simulate_italy_builder_direct_pricing(tariff: dict):
    # Mirrors the current stable Italy builder ordering sufficiently to prove that
    # removing eurPerKwh forces the validated rules path instead of energy-only pricing.
    if tariff.get("eurPerKwh") is not None:
        return {"type": "kwh", "pricePerKwh": float(tariff["eurPerKwh"])}
    if tariff.get("pricingType") != "rules":
        return None
    rules = tariff.get("pricingRules")
    if not isinstance(rules, list) or not rules:
        return None
    return {"type": "rules", "rules": deepcopy(rules)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", default="data/consolidation/italy_v9_candidate_go_electric_session_translation_qa.json.gz")
    ap.add_argument("--report", default="data/reports/go_electric_italy_v9_session_translation_qa.json")
    args = ap.parse_args()

    payload = load_gz(Path(args.candidate))
    if payload.get("publicationAllowed") is not False:
        raise SystemExit("input candidate must remain publicationAllowed=false")
    evses = payload.get("evses")
    if not isinstance(evses, list) or len(evses) != EXPECTED_TOTAL_EVSE:
        raise SystemExit(f"unexpected EVSE count: {len(evses) if isinstance(evses, list) else 'invalid'}")

    baseline_direct = sum(1 for e in evses if e.get("tccV9RankableDirect") is True)
    baseline_go_rankable = sum(
        1 for e in evses
        if e.get("tccV9RankableDirect") is True
        and (e.get("tccV9DirectTariff") or {}).get("operator") == GO_ELECTRIC
    )
    if baseline_direct != EXPECTED_BASELINE_DIRECT or baseline_go_rankable != EXPECTED_BASELINE_GO_ELECTRIC_RANKABLE:
        raise SystemExit(
            f"cost-readiness baseline drift: direct={baseline_direct}, goElectric={baseline_go_rankable}"
        )

    targets = []
    for e in evses:
        tariff = e.get("tccV9DirectTariff")
        if not isinstance(tariff, dict) or tariff.get("operator") != GO_ELECTRIC:
            continue
        comps = component_map(tariff)
        if set(comps) == {"energy", "session"}:
            targets.append((e, tariff, comps))

    if len(targets) != EXPECTED_TARGET:
        raise SystemExit(f"expected {EXPECTED_TARGET} energy+session EVSE, got {len(targets)}")

    translated_ids = []
    builder_tests = []
    for e, tariff, comps in targets:
        eid = str(e.get("evseId") or "")
        if e.get("tccV9RankableDirect") is True or tariff.get("rankable") is True:
            raise SystemExit(f"{eid}: target unexpectedly already rankable")
        if tariff.get("restrictions") not in (None, {}, []):
            raise SystemExit(f"{eid}: energy+session target unexpectedly has restrictions")
        energy = comps["energy"]
        session = comps["session"]
        if energy.get("unit") != "per_kWh" or session.get("unit") != "per_session":
            raise SystemExit(f"{eid}: source unit contract changed")
        energy_amount = energy.get("amount")
        session_amount = session.get("amount")
        if not isinstance(energy_amount, (int, float)) or isinstance(energy_amount, bool) or energy_amount < 0:
            raise SystemExit(f"{eid}: invalid energy amount")
        if not isinstance(session_amount, (int, float)) or isinstance(session_amount, bool) or session_amount < 0:
            raise SystemExit(f"{eid}: invalid session amount")
        if tariff.get("semanticValidated") is not True:
            raise SystemExit(f"{eid}: semantic validation missing")
        identity = tariff.get("identityEvidence") or {}
        power = tariff.get("powerEvidence") or {}
        if identity.get("exactPhysicalIdentity") is not True or power.get("powerCompatible") is not True:
            raise SystemExit(f"{eid}: identity/power evidence missing")

        rule = {
            "scope": "allDay",
            "start": "00:00",
            "end": "24:00",
            "currency": "EUR",
            "pricePerKwh": float(energy_amount),
            "sessionFee": float(session_amount),
        }
        # Avoid the current Italy builder's first-branch energy-only shortcut.
        old_energy_compat = tariff.pop("eurPerKwh", None)
        tariff["energyEurPerKwh"] = float(energy_amount)
        tariff["pricingType"] = "rules"
        tariff["pricingRules"] = [rule]
        tariff["rankable"] = True
        tariff["fullCostRankable"] = True
        tariff["runtimeRankable"] = True
        tariff["requiresRuntimeComponentSupport"] = False
        tariff["rankabilityReason"] = "energy_plus_session_exact_translation_validated"
        tariff["runtimeTranslation"] = {
            "status": "qa_validated",
            "sourceComponents": ["energy", "session"],
            "mapping": {"energy": "pricePerKwh", "session": "sessionFee"},
            "officialTerms": {
                "url": TERMS_URL,
                "version": TERMS_VERSION,
                "updated": TERMS_UPDATED,
                "evidence": "fees may include per-session and energy components and multiple components are summed",
            },
            "legacyEnergyCompatibilityValueRemoved": old_energy_compat,
            "publicationAllowed": False,
        }
        e["tccV9RankableDirect"] = True

        compiled = simulate_italy_builder_direct_pricing(tariff)
        if not compiled or compiled.get("type") != "rules":
            raise SystemExit(f"{eid}: Italy builder would not select rules pricing")
        compiled_rule = compiled["rules"][0]
        if compiled_rule.get("pricePerKwh") != float(energy_amount) or compiled_rule.get("sessionFee") != float(session_amount):
            raise SystemExit(f"{eid}: compiled rule mismatch")
        # Deterministic additive cost proof for a 20 kWh session.
        expected_cost = 20.0 * float(energy_amount) + float(session_amount)
        compiled_cost = 20.0 * float(compiled_rule["pricePerKwh"]) + float(compiled_rule["sessionFee"])
        if abs(expected_cost - compiled_cost) > 1e-9:
            raise SystemExit(f"{eid}: additive cost mismatch")
        builder_tests.append({"evseId": eid, "energyKwhTest": 20, "expectedCostEur": expected_cost})
        translated_ids.append(eid)

    by_station = {}
    for e in evses:
        by_station.setdefault(str(e.get("stationId") or ""), []).append(e)
    for station in payload.get("stations") or []:
        rows = by_station.get(str(station.get("stationId") or ""), [])
        station["evses"] = rows
        station["rankableDirectEvseCount"] = sum(1 for e in rows if e.get("tccV9RankableDirect") is True)
        station["rankableDirect"] = station["rankableDirectEvseCount"] > 0

    final_direct = sum(1 for e in evses if e.get("tccV9RankableDirect") is True)
    final_go_rankable = sum(
        1 for e in evses
        if e.get("tccV9RankableDirect") is True
        and (e.get("tccV9DirectTariff") or {}).get("operator") == GO_ELECTRIC
    )
    blocked_go = 0
    unsafe_rankable_sets = Counter()
    for e in evses:
        tariff = e.get("tccV9DirectTariff") or {}
        if tariff.get("operator") != GO_ELECTRIC:
            continue
        types = set(component_map(tariff))
        if e.get("tccV9RankableDirect") is True:
            if types != {"energy"} and types != {"energy", "session"}:
                unsafe_rankable_sets["+".join(sorted(types))] += 1
        else:
            blocked_go += 1

    if final_direct != EXPECTED_FINAL_DIRECT or final_go_rankable != EXPECTED_FINAL_GO_ELECTRIC_RANKABLE:
        raise SystemExit(f"final coverage mismatch: direct={final_direct}, goElectric={final_go_rankable}")
    if blocked_go != EXPECTED_REMAINING_BLOCKED_GO_ELECTRIC:
        raise SystemExit(f"remaining blocked Go Electric mismatch: {blocked_go}")
    if unsafe_rankable_sets:
        raise SystemExit(f"unsupported multi-component sets became rankable: {dict(unsafe_rankable_sets)}")

    counts = payload.setdefault("counts", {})
    counts["rankableDirectEvseCount"] = final_direct
    counts["rankableDirectCoveragePct"] = round(100 * final_direct / len(evses), 2)
    direct_by_operator = Counter(
        (e.get("tccV9DirectTariff") or {}).get("operator") or "UNKNOWN"
        for e in evses if e.get("tccV9RankableDirect") is True
    )
    counts["rankableDirectByOperator"] = dict(sorted(direct_by_operator.items()))

    payload["generatedAt"] = now_iso()
    payload["dataset"] = "italy-v9-consolidated-candidate-go-electric-session-translation-qa"
    payload["publicationAllowed"] = False
    payload["publicationReason"] = "Go Electric energy+session translation QA only; stable/runtime publication not authorized"
    payload["goElectricSessionTranslation"] = {
        "status": "qa_candidate",
        "translatedEvse": len(translated_ids),
        "safeRankableGoElectricBefore": baseline_go_rankable,
        "safeRankableGoElectricAfter": final_go_rankable,
        "remainingBlockedGoElectric": blocked_go,
        "publicationAllowed": False,
    }

    report = {
        "schemaVersion": 1,
        "generatedAt": payload["generatedAt"],
        "publicationAllowed": False,
        "officialEvidence": {
            "url": TERMS_URL,
            "version": TERMS_VERSION,
            "updated": TERMS_UPDATED,
            "semantics": "per-session and energy components are additive",
        },
        "input": {
            "evse": len(evses),
            "rankableDirectEvse": baseline_direct,
            "rankableGoElectricEvse": baseline_go_rankable,
        },
        "translation": {
            "componentSet": "energy+session",
            "translatedEvse": len(translated_ids),
            "runtimeMapping": {"energy": "pricePerKwh", "session": "sessionFee"},
            "italyBuilderRulePathForced": True,
            "builderSimulationTests": len(builder_tests),
        },
        "after": {
            "rankableDirectEvse": final_direct,
            "rankableDirectCoveragePct": round(100 * final_direct / len(evses), 2),
            "rankableGoElectricEvse": final_go_rankable,
            "remainingBlockedGoElectric": blocked_go,
        },
        "gates": {
            "targetExactly127": len(translated_ids) == EXPECTED_TARGET,
            "allTargetsExactEnergySessionUnits": True,
            "officialPerSessionSemanticsRecorded": True,
            "allTargetsUseRulesPricing": len(builder_tests) == EXPECTED_TARGET,
            "additiveCostTests127": len(builder_tests) == EXPECTED_TARGET,
            "goElectricRankable943": final_go_rankable == EXPECTED_FINAL_GO_ELECTRIC_RANKABLE,
            "italyDirect26569": final_direct == EXPECTED_FINAL_DIRECT,
            "remainingBlocked1271": blocked_go == EXPECTED_REMAINING_BLOCKED_GO_ELECTRIC,
            "noUnsupportedMultiComponentRankable": not unsafe_rankable_sets,
            "publicationDisabled": payload.get("publicationAllowed") is False,
        },
    }
    if not all(report["gates"].values()):
        raise SystemExit(f"session translation gates failed: {report['gates']}")

    write_gz(Path(args.out), payload)
    write_json(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
