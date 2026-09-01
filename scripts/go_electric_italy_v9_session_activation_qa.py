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

OPERATOR = "Go Electric Stations SRLS"
EXPECTED_TOTAL_EVSE = 75025
EXPECTED_VALIDATED = 2214
EXPECTED_ENERGY_ONLY = 816
EXPECTED_SESSION_CANDIDATES = 127
EXPECTED_GO_ELECTRIC_RANKABLE = 943
EXPECTED_STAGED = 1271
EXPECTED_TOTAL_DIRECT = 26569
EXPECTED_CURRENT_PHYSICAL = 2453
EXPECTED_TIME = 1052
EXPECTED_PARKING = 700


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_gz(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def finite_nonnegative(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)) and float(v) >= 0


def component_map(tariff: dict[str, Any]) -> dict[str, dict[str, Any]]:
    comps = tariff.get("priceComponents")
    if not isinstance(comps, list) or not comps:
        raise SystemExit("missing priceComponents")
    out: dict[str, dict[str, Any]] = {}
    for comp in comps:
        if not isinstance(comp, dict):
            raise SystemExit("invalid price component")
        typ = str(comp.get("type") or "")
        if typ in out:
            raise SystemExit(f"duplicate component {typ}")
        out[typ] = comp
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--runtime-offers", required=True)
    ap.add_argument("--engine-report", required=True)
    ap.add_argument("--out", default="data/consolidation/italy_v9_candidate_go_electric_session_ready_qa.json.gz")
    ap.add_argument("--report", default="data/reports/go_electric_italy_v9_session_activation_qa.json")
    args = ap.parse_args()

    payload = load(Path(args.candidate))
    runtime = load(Path(args.runtime_offers))
    engine = load(Path(args.engine_report))

    if payload.get("publicationAllowed") is not False:
        raise SystemExit("cost-ready candidate must remain publicationAllowed=false")
    if runtime.get("publicationAllowed") is not False or runtime.get("builderActivationAllowed") is not False:
        raise SystemExit("runtime translation artifact must remain non-published and non-activated")
    if engine.get("publicationAllowed") is not False or engine.get("builderActivationAllowed") is not False:
        raise SystemExit("engine report must remain non-published and non-activated")
    if engine.get("testedOffers") != EXPECTED_SESSION_CANDIDATES or engine.get("passedOffers") != EXPECTED_SESSION_CANDIDATES or engine.get("failedOffers") != 0:
        raise SystemExit("session engine QA count mismatch")
    if not all((engine.get("gates") or {}).values()):
        raise SystemExit("session engine QA gates are not all green")

    evses = payload.get("evses")
    if not isinstance(evses, list) or len(evses) != EXPECTED_TOTAL_EVSE:
        raise SystemExit("Italy EVSE inventory drift")

    passed_offers = runtime.get("offers")
    if not isinstance(passed_offers, list) or len(passed_offers) != EXPECTED_SESSION_CANDIDATES:
        raise SystemExit("runtime offer count drift")

    runtime_by_evse: dict[str, dict[str, Any]] = {}
    for offer in passed_offers:
        ids = offer.get("evseIds")
        pricing = offer.get("pricing")
        if not isinstance(ids, list) or len(ids) != 1 or not isinstance(pricing, dict):
            raise SystemExit("invalid runtime offer")
        eid = str(ids[0]).upper()
        if eid in runtime_by_evse:
            raise SystemExit(f"duplicate runtime EVSE {eid}")
        if pricing.get("type") != "rules" or not isinstance(pricing.get("rules"), list) or len(pricing["rules"]) != 1:
            raise SystemExit(f"{eid}: invalid runtime rules pricing")
        rule = pricing["rules"][0]
        if not finite_nonnegative(rule.get("pricePerKwh")) or not finite_nonnegative(rule.get("sessionFeeEur")):
            raise SystemExit(f"{eid}: invalid translated energy/session amount")
        runtime_by_evse[eid] = offer

    evse_by_id = {str(e.get("evseId") or "").upper(): e for e in evses}
    promoted: list[str] = []

    for eid, offer in runtime_by_evse.items():
        evse = evse_by_id.get(eid)
        if not evse:
            raise SystemExit(f"{eid}: translated EVSE missing from candidate")
        tariff = evse.get("tccV9DirectTariff")
        if not isinstance(tariff, dict) or tariff.get("operator") != OPERATOR:
            raise SystemExit(f"{eid}: Go Electric exact direct tariff missing")
        if evse.get("tccV9RankableDirect") is True:
            raise SystemExit(f"{eid}: session candidate unexpectedly already rankable")

        comps = component_map(tariff)
        if set(comps) != {"energy", "session"}:
            raise SystemExit(f"{eid}: component set drift {sorted(comps)}")
        energy, session = comps["energy"], comps["session"]
        if energy.get("unit") != "per_kWh" or session.get("unit") != "per_session":
            raise SystemExit(f"{eid}: source units drift")
        rule = offer["pricing"]["rules"][0]
        if abs(float(energy["amount"]) - float(rule["pricePerKwh"])) > 1e-9:
            raise SystemExit(f"{eid}: translated energy mismatch")
        if abs(float(session["amount"]) - float(rule["sessionFeeEur"])) > 1e-9:
            raise SystemExit(f"{eid}: translated session fee mismatch")
        if not ((tariff.get("identityEvidence") or {}).get("exactPhysicalIdentity") is True):
            raise SystemExit(f"{eid}: exact physical identity evidence missing")

        tariff["runtimePricing"] = offer["pricing"]
        tariff["runtimeTranslation"] = {
            "energy": "pricePerKwh",
            "session": "sessionFeeEur",
            "qaRun": 33458731548,
            "stablePricingEngineBlobSha": runtime.get("stablePricingEngineBlobSha"),
            "exactEngineTestPassed": True,
        }
        tariff["fullCostRankable"] = True
        tariff["runtimeRankable"] = True
        tariff["rankable"] = True
        tariff["requiresRuntimeComponentSupport"] = False
        tariff["rankabilityReason"] = "energy_plus_session_exact_runtime_engine_qa_passed"
        evse["tccV9RankableDirect"] = True
        promoted.append(eid)

    if len(promoted) != EXPECTED_SESSION_CANDIDATES:
        raise SystemExit(f"promoted {len(promoted)} != {EXPECTED_SESSION_CANDIDATES}")

    validated = 0
    ge_rankable = 0
    staged = 0
    time_blocked = 0
    parking_blocked = 0
    unsafe_rankable: list[str] = []

    for evse in evses:
        tariff = evse.get("tccV9DirectTariff")
        if not isinstance(tariff, dict) or tariff.get("operator") != OPERATOR:
            continue
        validated += 1
        eid = str(evse.get("evseId") or "").upper()
        comps = component_map(tariff)
        types = set(comps)
        rankable = evse.get("tccV9RankableDirect") is True

        if "time" in types:
            time_blocked += 1
        if "parking" in types:
            parking_blocked += 1

        allowed = types == {"energy"} or types == {"energy", "session"}
        if rankable:
            ge_rankable += 1
            if not allowed:
                unsafe_rankable.append(eid)
            if types == {"energy", "session"}:
                rp = tariff.get("runtimePricing") or {}
                rules = rp.get("rules") if isinstance(rp, dict) else None
                if rp.get("type") != "rules" or not isinstance(rules, list) or len(rules) != 1:
                    raise SystemExit(f"{eid}: promoted tariff lost runtimePricing")
        else:
            staged += 1
            if types == {"energy", "session"}:
                raise SystemExit(f"{eid}: validated energy+session tariff remained staged")

    if validated != EXPECTED_VALIDATED:
        raise SystemExit(f"validated direct drift {validated}")
    if ge_rankable != EXPECTED_GO_ELECTRIC_RANKABLE:
        raise SystemExit(f"Go Electric rankable drift {ge_rankable}")
    if staged != EXPECTED_STAGED:
        raise SystemExit(f"Go Electric staged drift {staged}")
    if time_blocked != EXPECTED_TIME or parking_blocked != EXPECTED_PARKING:
        raise SystemExit(f"blocked component drift time={time_blocked} parking={parking_blocked}")
    if unsafe_rankable:
        raise SystemExit(f"unsafe multi-component rankable rows: {unsafe_rankable[:5]}")

    evse_by_station: dict[str, list[dict[str, Any]]] = {}
    for evse in evses:
        evse_by_station.setdefault(str(evse.get("stationId") or ""), []).append(evse)
    stations = payload.get("stations")
    if not isinstance(stations, list):
        raise SystemExit("stations missing")
    for station in stations:
        rows = evse_by_station.get(str(station.get("stationId") or ""), [])
        station["evses"] = rows
        station["rankableDirectEvseCount"] = sum(1 for row in rows if row.get("tccV9RankableDirect") is True)
        station["rankableDirect"] = station["rankableDirectEvseCount"] > 0

    direct_total = sum(1 for evse in evses if evse.get("tccV9RankableDirect") is True)
    direct_by_operator = Counter(
        (evse.get("tccV9DirectTariff") or {}).get("operator") or "UNKNOWN"
        for evse in evses if evse.get("tccV9RankableDirect") is True
    )
    if direct_total != EXPECTED_TOTAL_DIRECT:
        raise SystemExit(f"total direct rankable drift {direct_total}")
    if direct_by_operator.get(OPERATOR) != EXPECTED_GO_ELECTRIC_RANKABLE:
        raise SystemExit("Go Electric direct accounting mismatch")

    counts = payload.setdefault("counts", {})
    counts["rankableDirectEvseCount"] = direct_total
    counts["rankableDirectCoveragePct"] = round(100 * direct_total / len(evses), 2)
    counts["rankableDirectByOperator"] = dict(sorted(direct_by_operator.items()))

    rules = payload.setdefault("rules", {})
    rules["goElectricEnergyPlusSessionRuntimeTranslationQaPassed"] = True
    rules["goElectricEnergyPlusSessionRequiresBuilderRuntimePricingSupport"] = True
    rules["goElectricTimeAndParkingRemainFailClosed"] = True

    integration = payload.setdefault("goElectricIntegration", {})
    current_physical = int(integration.get("currentPhysicalEvse") or EXPECTED_CURRENT_PHYSICAL)
    if current_physical != EXPECTED_CURRENT_PHYSICAL:
        raise SystemExit("current physical Go Electric EVSE drift")
    integration.update({
        "status": "session_runtime_translation_pass_candidate",
        "acceptedExactEvseOffers": validated,
        "runtimeRankableEnergyOnlyEvse": EXPECTED_ENERGY_ONLY,
        "runtimeRankableEnergyPlusSessionEvse": EXPECTED_SESSION_CANDIDATES,
        "runtimeRankableTotalEvse": ge_rankable,
        "stagedMultiComponentEvse": staged,
        "currentPhysicalEvseWithoutRuntimeRankableDirect": current_physical - ge_rankable,
        "builderRuntimePricingSupportRequiredBeforePublication": True,
        "publicationAllowed": False,
    })

    payload["generatedAt"] = now_iso()
    payload["dataset"] = "italy-v9-consolidated-candidate-go-electric-session-ready-qa"
    payload["publicationAllowed"] = False
    payload["publicationReason"] = (
        "Go Electric energy+session activation candidate only; builder support is not yet merged "
        "and time/parking components remain fail-closed"
    )

    report = {
        "schemaVersion": 1,
        "generatedAt": payload["generatedAt"],
        "publicationAllowed": False,
        "builderActivationAllowed": False,
        "validatedGoElectricDirectEvse": validated,
        "promotedEnergyPlusSessionEvse": len(promoted),
        "goElectricRuntimeCandidateEvse": ge_rankable,
        "goElectricStagedEvse": staged,
        "remainingBlocked": {
            "timeComponentOffers": time_blocked,
            "parkingComponentOffers": parking_blocked,
        },
        "directAccounting": {
            "rankableDirectEvse": direct_total,
            "rankableDirectCoveragePct": counts["rankableDirectCoveragePct"],
            "rankableDirectByOperator": counts["rankableDirectByOperator"],
        },
        "goElectricPhysicalWithoutRuntimeCandidate": current_physical - ge_rankable,
        "engineEvidence": {
            "translationQaRun": 33458731548,
            "tested": engine["testedOffers"],
            "passed": engine["passedOffers"],
            "failed": engine["failedOffers"],
            "stablePricingEngineBlobSha": runtime.get("stablePricingEngineBlobSha"),
        },
        "gates": {
            "validated2214Preserved": validated == EXPECTED_VALIDATED,
            "energyPlusSession127Promoted": len(promoted) == EXPECTED_SESSION_CANDIDATES,
            "goElectric943RuntimeCandidate": ge_rankable == EXPECTED_GO_ELECTRIC_RANKABLE,
            "staged1271RemainFailClosed": staged == EXPECTED_STAGED,
            "time1052RemainBlocked": time_blocked == EXPECTED_TIME,
            "parking700RemainBlocked": parking_blocked == EXPECTED_PARKING,
            "noUnsafeMultiComponentRankable": not unsafe_rankable,
            "totalDirect26569": direct_total == EXPECTED_TOTAL_DIRECT,
            "publicationDisabled": payload.get("publicationAllowed") is False,
            "builderActivationDisabled": True,
        },
    }
    if not all(report["gates"].values()):
        raise SystemExit(f"session activation gates failed: {report['gates']}")

    write_gz(Path(args.out), payload)
    write_json(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
