#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GO_ELECTRIC_OPERATOR = "Go Electric Stations SRLS"
EXPECTED_VALIDATED_DIRECT = 2214
EXPECTED_ENERGY_ONLY_RUNTIME_RANKABLE = 816
EXPECTED_MULTI_COMPONENT_STAGED = 1398
EXPECTED_TOTAL_EVSE = 75025
EXPECTED_CURRENT_PHYSICAL_EVSE = 2453
EXPECTED_LEGACY_EMSP_RETIRED = 2281
EXPECTED_COMPONENT_SETS = {
    "energy": 816,
    "energy+parking": 189,
    "energy+parking+session": 30,
    "energy+parking+session+time": 95,
    "energy+parking+time": 386,
    "energy+session": 127,
    "energy+session+time": 23,
    "energy+time": 548,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_gz_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def finite_nonnegative(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value)) and float(value) >= 0


def is_legacy_go_electric_nextcharge_emsp(tariff: dict[str, Any]) -> bool:
    if str(tariff.get("provider") or "").strip().lower() != "nextcharge":
        return False
    return "go electric stations" in str(tariff.get("billedBy") or "").strip().lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--integration-report", required=True)
    ap.add_argument(
        "--out",
        default="data/consolidation/italy_v9_candidate_go_electric_cost_ready_qa.json.gz",
    )
    ap.add_argument(
        "--report",
        default="data/reports/go_electric_italy_v9_cost_readiness.json",
    )
    args = ap.parse_args()

    payload = load_json(Path(args.input))
    integration_report = load_json(Path(args.integration_report))

    if payload.get("publicationAllowed") is not False:
        raise SystemExit("input candidate must remain publicationAllowed=false")
    if integration_report.get("publicationAllowed") is not False:
        raise SystemExit("integration report must remain publicationAllowed=false")
    if integration_report.get("integration", {}).get("matchedCandidateEvse") != EXPECTED_VALIDATED_DIRECT:
        raise SystemExit("unexpected validated Go Electric direct count in integration report")
    if integration_report.get("integration", {}).get("legacyNextChargeEmspEntriesRetired") != EXPECTED_LEGACY_EMSP_RETIRED:
        raise SystemExit("legacy Go Electric NextCharge eMSP retirement count drift")

    evses = payload.get("evses")
    if not isinstance(evses, list) or len(evses) != EXPECTED_TOTAL_EVSE:
        raise SystemExit(f"unexpected Italy EVSE inventory: {len(evses) if isinstance(evses, list) else 'invalid'}")

    validated = 0
    runtime_rankable = 0
    staged_multi_component = 0
    component_sets: Counter[str] = Counter()
    unsafe_marked_rankable: list[str] = []

    for evse in evses:
        tariff = evse.get("tccV9DirectTariff")
        if not isinstance(tariff, dict) or tariff.get("operator") != GO_ELECTRIC_OPERATOR:
            continue

        validated += 1
        evse_id = str(evse.get("evseId") or "").upper()
        components = tariff.get("priceComponents")
        if not isinstance(components, list) or not components:
            raise SystemExit(f"{evse_id}: validated direct tariff lost priceComponents")

        types: list[str] = []
        for component in components:
            if not isinstance(component, dict):
                raise SystemExit(f"{evse_id}: invalid component row")
            kind = str(component.get("type") or "")
            if kind not in {"energy", "time", "session", "parking"}:
                raise SystemExit(f"{evse_id}: unsupported component type {kind!r}")
            if kind in types:
                raise SystemExit(f"{evse_id}: duplicate component type {kind!r}")
            if not finite_nonnegative(component.get("amount")):
                raise SystemExit(f"{evse_id}: invalid amount for {kind}")
            types.append(kind)

        component_key = "+".join(sorted(types))
        component_sets[component_key] += 1

        energy_rows = [c for c in components if c.get("type") == "energy"]
        energy_only_runtime_safe = (
            len(components) == 1
            and len(energy_rows) == 1
            and energy_rows[0].get("unit") == "per_kWh"
            and finite_nonnegative(energy_rows[0].get("amount"))
        )

        tariff["fullCostRankable"] = energy_only_runtime_safe
        tariff["runtimeRankable"] = energy_only_runtime_safe
        tariff["rankable"] = energy_only_runtime_safe
        tariff["requiresRuntimeComponentSupport"] = not energy_only_runtime_safe
        tariff["rankabilityReason"] = (
            "energy_only_exact_direct_runtime_safe"
            if energy_only_runtime_safe
            else "multi_component_runtime_unit_mapping_pending"
        )
        evse["tccV9RankableDirect"] = energy_only_runtime_safe

        if energy_only_runtime_safe:
            runtime_rankable += 1
        else:
            staged_multi_component += 1
            if evse.get("tccV9RankableDirect") is True or tariff.get("rankable") is True:
                unsafe_marked_rankable.append(evse_id)

    if validated != EXPECTED_VALIDATED_DIRECT:
        raise SystemExit(f"validated Go Electric direct count drift: {validated}")
    if runtime_rankable != EXPECTED_ENERGY_ONLY_RUNTIME_RANKABLE:
        raise SystemExit(f"energy-only runtime-rankable count drift: {runtime_rankable}")
    if staged_multi_component != EXPECTED_MULTI_COMPONENT_STAGED:
        raise SystemExit(f"multi-component staged count drift: {staged_multi_component}")
    if dict(sorted(component_sets.items())) != EXPECTED_COMPONENT_SETS:
        raise SystemExit(f"component-set distribution drift: {dict(sorted(component_sets.items()))}")
    if unsafe_marked_rankable:
        raise SystemExit(f"multi-component offers incorrectly rankable: {unsafe_marked_rankable[:5]}")

    evse_by_station: dict[str, list[dict[str, Any]]] = {}
    for evse in evses:
        evse_by_station.setdefault(str(evse.get("stationId") or ""), []).append(evse)

    stations = payload.get("stations")
    if not isinstance(stations, list):
        raise SystemExit("candidate stations missing")
    for station in stations:
        rows = evse_by_station.get(str(station.get("stationId") or ""), [])
        station["evses"] = rows
        station["rankableDirectEvseCount"] = sum(1 for row in rows if row.get("tccV9RankableDirect") is True)
        station["rankableDirect"] = station["rankableDirectEvseCount"] > 0

    final_direct = sum(1 for evse in evses if evse.get("tccV9RankableDirect") is True)
    final_direct_by_operator = Counter(
        (evse.get("tccV9DirectTariff") or {}).get("operator") or "UNKNOWN"
        for evse in evses
        if evse.get("tccV9RankableDirect") is True
    )
    expected_baseline_direct = int(integration_report.get("before", {}).get("rankableDirectEvse") or 0)
    expected_final_direct = expected_baseline_direct + EXPECTED_ENERGY_ONLY_RUNTIME_RANKABLE
    if final_direct != expected_final_direct:
        raise SystemExit(f"rankable direct accounting mismatch: {final_direct} != {expected_final_direct}")
    if final_direct_by_operator.get(GO_ELECTRIC_OPERATOR, 0) != EXPECTED_ENERGY_ONLY_RUNTIME_RANKABLE:
        raise SystemExit("Go Electric runtime-rankable direct count mismatch")

    residual_legacy_emsp = sum(
        1
        for evse in evses
        for tariff in (evse.get("tccV9EmspTariffs") or [])
        if isinstance(tariff, dict) and is_legacy_go_electric_nextcharge_emsp(tariff)
    )
    if residual_legacy_emsp:
        raise SystemExit(f"{residual_legacy_emsp} legacy Go Electric NextCharge eMSP entries remain")

    counts = payload.setdefault("counts", {})
    counts["rankableDirectEvseCount"] = final_direct
    counts["rankableDirectCoveragePct"] = round(100 * final_direct / len(evses), 2)
    counts["rankableDirectByOperator"] = dict(sorted(final_direct_by_operator.items()))

    rules = payload.setdefault("rules", {})
    rules["goElectricValidatedDirectTariffsPreserved"] = True
    rules["goElectricEnergyOnlyDirectTariffsRuntimeRankable"] = True
    rules["goElectricMultiComponentTariffsFailClosedUntilRuntimeUnitMapping"] = True
    rules["goElectricRuntimeMustNotFlattenMultiComponentTariffsToEnergyOnly"] = True

    integration = payload.setdefault("goElectricIntegration", {})
    current_physical = int(integration.get("currentPhysicalEvse") or EXPECTED_CURRENT_PHYSICAL_EVSE)
    if current_physical != EXPECTED_CURRENT_PHYSICAL_EVSE:
        raise SystemExit(f"current Go Electric physical EVSE drift since integration QA: {current_physical}")
    integration.update(
        {
            "status": "cost_readiness_pass_candidate",
            "acceptedExactEvseOffers": validated,
            "runtimeRankableEnergyOnlyEvse": runtime_rankable,
            "stagedMultiComponentEvse": staged_multi_component,
            "currentPhysicalEvseWithoutRuntimeRankableDirect": current_physical - runtime_rankable,
            "runtimeRankabilityPolicy": (
                "energy-only per_kWh offers rankable; multi-component offers preserved but fail-closed "
                "until exact time/session/parking unit semantics are supported"
            ),
            "publicationAllowed": False,
        }
    )

    payload["generatedAt"] = now_iso()
    payload["dataset"] = "italy-v9-consolidated-candidate-go-electric-cost-ready-qa"
    payload["publicationAllowed"] = False
    payload["publicationReason"] = (
        "Go Electric cost-readiness QA only; multi-component tariffs fail closed and stable/runtime publication is not authorized"
    )

    report = {
        "schemaVersion": 1,
        "generatedAt": payload["generatedAt"],
        "publicationAllowed": False,
        "input": {
            "validatedExactDirectEvse": validated,
            "currentPhysicalGoElectricEvse": current_physical,
            "integrationQaRun": 33456319476,
            "integrationArtifactId": 9781579505,
        },
        "runtimeCompatibility": {
            "currentItalyBuilderSupportsEnergyOnlyKwhDirect": True,
            "currentItalyBuilderSupportsGoElectricPriceComponents": False,
            "runtimeRankableEnergyOnlyEvse": runtime_rankable,
            "stagedMultiComponentEvse": staged_multi_component,
            "currentPhysicalEvseWithoutAcceptedDirectOffer": current_physical - validated,
            "currentPhysicalEvseWithoutRuntimeRankableDirect": current_physical - runtime_rankable,
            "componentSets": dict(sorted(component_sets.items())),
        },
        "before": {
            "rankableDirectEvse": expected_baseline_direct,
            "rankableDirectCoveragePct": round(100 * expected_baseline_direct / len(evses), 2),
        },
        "after": {
            "rankableDirectEvse": final_direct,
            "rankableDirectCoveragePct": round(100 * final_direct / len(evses), 2),
            "rankableDirectByOperator": dict(sorted(final_direct_by_operator.items())),
            "goElectricValidatedDirectEvse": validated,
            "goElectricRuntimeRankableDirectEvse": runtime_rankable,
            "goElectricStagedNonRankableDirectEvse": staged_multi_component,
        },
        "gates": {
            "validatedDirectTariffsPreserved2214": validated == EXPECTED_VALIDATED_DIRECT,
            "energyOnlyRuntimeRankable816": runtime_rankable == EXPECTED_ENERGY_ONLY_RUNTIME_RANKABLE,
            "multiComponentFailClosed1398": staged_multi_component == EXPECTED_MULTI_COMPONENT_STAGED,
            "noMultiComponentMarkedRankable": not unsafe_marked_rankable,
            "componentDistributionUnchanged": dict(sorted(component_sets.items())) == EXPECTED_COMPONENT_SETS,
            "legacyGoElectricNextChargeEmspStillRetired": residual_legacy_emsp == 0,
            "rankableDirectAccountingSafe": final_direct == expected_final_direct,
            "publicationDisabled": payload.get("publicationAllowed") is False,
        },
    }
    if not all(report["gates"].values()):
        raise SystemExit(f"cost-readiness gates failed: {report['gates']}")

    write_gz_json(Path(args.out), payload)
    write_json(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
