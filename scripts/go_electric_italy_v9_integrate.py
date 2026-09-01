#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_COMPONENTS = {"energy", "time", "session", "parking"}
GO_ELECTRIC_OPERATOR = "Go Electric Stations SRLS"
LEGACY_BILLED_BY_MARKERS = ("go electric stations",)
SEMANTIC_BASELINE_STATIONS = 1136
SEMANTIC_BASELINE_EVSE = 2413
EXPECTED_READY_OFFERS = 2214
EXPECTED_STATION_QUARANTINE = 79
EXPECTED_CONNECTOR_EXCLUSION = 48


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_gz_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(encoded, compresslevel=9, mtime=0))


def is_legacy_go_electric_nextcharge_emsp(tariff: dict) -> bool:
    if str(tariff.get("provider") or "").strip().lower() != "nextcharge":
        return False
    billed = str(tariff.get("billedBy") or "").strip().lower()
    return any(marker in billed for marker in LEGACY_BILLED_BY_MARKERS)


def normalized_direct_from_offer(offer: dict) -> dict:
    evse_id = str(offer.get("punEvseId") or "").upper()
    currency = str(offer.get("currency") or "").upper()
    if currency != "EUR":
        raise ValueError(f"{evse_id}: currency must be EUR, got {currency!r}")

    components = offer.get("priceComponents")
    if not isinstance(components, list) or not components:
        raise ValueError(f"{evse_id}: priceComponents missing")

    seen = set()
    normalized_components = []
    energy = None
    for component in components:
        if not isinstance(component, dict):
            raise ValueError(f"{evse_id}: invalid component")
        kind = str(component.get("sourceType") or "")
        if kind not in ALLOWED_COMPONENTS:
            raise ValueError(f"{evse_id}: unknown component {kind!r}")
        if kind in seen:
            raise ValueError(f"{evse_id}: duplicate component {kind!r}")
        seen.add(kind)
        amount = component.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
            raise ValueError(f"{evse_id}: invalid amount for {kind}")
        normalized_components.append({"type": kind, "amount": amount, "unit": component.get("sourceUnit")})
        if kind == "energy":
            energy = amount

    if energy is None:
        raise ValueError(f"{evse_id}: energy component required")

    provenance = offer.get("provenance") if isinstance(offer.get("provenance"), dict) else {}
    qa = offer.get("qa") if isinstance(offer.get("qa"), dict) else {}
    if provenance.get("exactPhysicalIdentity") is not True:
        raise ValueError(f"{evse_id}: exactPhysicalIdentity required")
    if qa.get("semanticValidated") is not True or qa.get("powerCompatible") is not True:
        raise ValueError(f"{evse_id}: semantic/power QA required")

    return {
        "channel": "operator_direct",
        "operator": GO_ELECTRIC_OPERATOR,
        "provider": "NextCharge",
        "officialB2C": True,
        "currency": "EUR",
        "pricingType": "components",
        "eurPerKwh": energy,
        "priceComponents": normalized_components,
        "restrictions": deepcopy(offer.get("restrictions")),
        "paymentRequired": bool(offer.get("paymentRequired")),
        "source": "NextCharge official Go Electric B2C",
        "sourceOfferId": offer.get("offerId"),
        "sourceStationId": offer.get("nextChargeStationId"),
        "sourceGeneratedAt": None,
        "identityEvidence": {
            "punEvseId": offer.get("punEvseId"),
            "uidConnector": offer.get("uidConnector"),
            "rule": provenance.get("identityRule"),
            "exactPhysicalIdentity": True,
            "coordinatesDiscoveryOnly": True,
        },
        "powerEvidence": {
            "connectorType": offer.get("connectorType"),
            "current": offer.get("current"),
            "powerKw": offer.get("powerKw"),
            "expectedPowerKw": offer.get("expectedPowerKw"),
            "powerCompatible": True,
        },
        "semanticValidated": True,
        "rankable": True,
        "publicationAllowed": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="data/consolidation/italy_v9_candidate.json.gz")
    ap.add_argument("--ready", default="artifacts/go_electric_semantic/go_electric_italy_v9_ready_offers.json")
    ap.add_argument("--semantic-qa", default="artifacts/go_electric_semantic/go_electric_italy_v9_semantic_qa.json")
    ap.add_argument("--quarantine", default="artifacts/go_electric_semantic/go_electric_italy_v9_semantic_quarantine.json")
    ap.add_argument("--out", default="data/consolidation/italy_v9_candidate_go_electric_direct_qa.json.gz")
    ap.add_argument("--report", default="data/reports/go_electric_italy_v9_integration_qa.json")
    args = ap.parse_args()

    candidate = load_json(Path(args.candidate))
    ready = load_json(Path(args.ready))
    semantic_qa = load_json(Path(args.semantic_qa))
    quarantine = load_json(Path(args.quarantine))

    if ready.get("publicationAllowed") is not False:
        raise SystemExit("ready artifact must remain publicationAllowed=false")
    if semantic_qa.get("policy", {}).get("publicationAllowed") is not False:
        raise SystemExit("semantic QA must remain publicationAllowed=false")

    offers = ready.get("offers")
    if not isinstance(offers, list):
        raise SystemExit("ready offers missing")
    if len(offers) != EXPECTED_READY_OFFERS:
        raise SystemExit(f"expected {EXPECTED_READY_OFFERS} ready offers, got {len(offers)}")

    qa_summary = semantic_qa.get("summary") or {}
    if qa_summary.get("readyEvseOffers") != EXPECTED_READY_OFFERS:
        raise SystemExit("semantic QA readyEvseOffers mismatch")

    input_baseline = semantic_qa.get("inputBaseline") or {}
    baseline_stations = int(input_baseline.get("stationCount") or 0)
    baseline_evses = int(input_baseline.get("evseCount") or 0)
    if baseline_stations != SEMANTIC_BASELINE_STATIONS or baseline_evses != SEMANTIC_BASELINE_EVSE:
        raise SystemExit(
            f"semantic QA Go Electric baseline mismatch: {baseline_stations} stations/{baseline_evses} EVSE"
        )

    quarantine_rows = quarantine.get("rows") if isinstance(quarantine, dict) else None
    if not isinstance(quarantine_rows, list):
        raise SystemExit("semantic quarantine rows missing")
    station_quarantine = sum(1 for row in quarantine_rows if row.get("scope") == "station")
    connector_exclusion = sum(1 for row in quarantine_rows if row.get("scope") == "evse")
    if station_quarantine != EXPECTED_STATION_QUARANTINE or connector_exclusion != EXPECTED_CONNECTOR_EXCLUSION:
        raise SystemExit(
            f"semantic quarantine mismatch: station={station_quarantine}, evse={connector_exclusion}"
        )

    source_generated_at = ready.get("generatedAt")
    offer_by_evse = {}
    source_offer_by_evse = {}
    component_sets = Counter()

    for offer in offers:
        evse_id = str(offer.get("punEvseId") or "").upper()
        if not evse_id:
            raise SystemExit("ready offer without punEvseId")
        if evse_id in offer_by_evse:
            raise SystemExit(f"duplicate ready offer for {evse_id}")
        if offer.get("publicationAllowed") is not False:
            raise SystemExit(f"{evse_id}: offer publicationAllowed must be false")
        if "preAuth" not in offer:
            raise SystemExit(f"{evse_id}: upstream preAuth field unexpectedly absent; audit contract changed")

        direct = normalized_direct_from_offer(offer)
        direct["sourceGeneratedAt"] = source_generated_at
        if "preAuth" in json.dumps(direct, ensure_ascii=False):
            raise SystemExit(f"{evse_id}: preAuth leaked into normalized direct tariff")

        offer_by_evse[evse_id] = direct
        source_offer_by_evse[evse_id] = offer
        component_sets["+".join(sorted(c["type"] for c in direct["priceComponents"]))] += 1

    payload = deepcopy(candidate)
    evses = payload.get("evses")
    if not isinstance(evses, list) or not evses:
        raise SystemExit("candidate EVSE list missing")

    evse_ids = [str(e.get("evseId") or "").upper() for e in evses]
    if len(set(evse_ids)) != len(evse_ids):
        raise SystemExit("candidate contains duplicate EVSE IDs")

    candidate_ids = set(evse_ids)
    missing = sorted(set(offer_by_evse) - candidate_ids)
    if missing:
        raise SystemExit(
            f"{len(missing)} accepted Go Electric EVSE IDs absent from current candidate; first={missing[:5]}"
        )

    # The current PUN catalogue may grow after the validated tariff snapshot.
    # Growth is non-blocking and remains unpriced; shrinkage below the validated baseline blocks.
    target_by_station = Counter()
    for e in evses:
        evse_id = str(e.get("evseId") or "").upper()
        if evse_id.startswith("ITGES"):
            target_by_station[str(e.get("stationId") or "")] += 1

    current_physical_stations = len(target_by_station)
    current_physical_evses = sum(target_by_station.values())
    station_delta = current_physical_stations - baseline_stations
    evse_delta = current_physical_evses - baseline_evses

    if current_physical_stations < baseline_stations or current_physical_evses < baseline_evses:
        raise SystemExit(
            "current Go Electric physical inventory shrank below validated semantic baseline: "
            f"current={current_physical_stations} stations/{current_physical_evses} EVSE, "
            f"baseline={baseline_stations} stations/{baseline_evses} EVSE"
        )

    baseline_direct = sum(1 for e in evses if e.get("tccV9RankableDirect") is True)
    baseline_direct_by_operator = Counter(
        (e.get("tccV9DirectTariff") or {}).get("operator") or "UNKNOWN"
        for e in evses
        if e.get("tccV9RankableDirect") is True
    )
    baseline_emsp = sum(1 for e in evses if e.get("tccV9HasRankableEmsp") is True)

    retired_legacy_entries = 0
    retired_legacy_evses = 0
    conflicts = []
    same_source_overlaps = 0
    newly_direct = 0

    for e in evses:
        evse_id = str(e.get("evseId") or "").upper()

        old_emsp = e.get("tccV9EmspTariffs")
        old_emsp = old_emsp if isinstance(old_emsp, list) else []
        kept_emsp = []
        removed_here = 0
        for tariff in old_emsp:
            if isinstance(tariff, dict) and is_legacy_go_electric_nextcharge_emsp(tariff):
                retired_legacy_entries += 1
                removed_here += 1
            else:
                kept_emsp.append(tariff)
        if removed_here:
            retired_legacy_evses += 1
        e["tccV9EmspTariffs"] = kept_emsp
        e["tccV9HasRankableEmsp"] = any(
            isinstance(t, dict) and t.get("rankable") is True for t in kept_emsp
        )

        new_direct = offer_by_evse.get(evse_id)
        if new_direct is None:
            continue

        source_offer = source_offer_by_evse[evse_id]
        if str(e.get("stationId") or "") != str(source_offer.get("punStationId") or ""):
            raise SystemExit(
                f"{evse_id}: station identity mismatch candidate={e.get('stationId')} "
                f"offer={source_offer.get('punStationId')}"
            )

        existing = e.get("tccV9DirectTariff") if isinstance(e.get("tccV9DirectTariff"), dict) else None
        existing_rankable = bool(e.get("tccV9RankableDirect") is True and existing and existing.get("rankable"))
        if existing_rankable:
            existing_operator = str(existing.get("operator") or "")
            if existing_operator != GO_ELECTRIC_OPERATOR:
                conflicts.append({"evseId": evse_id, "existingOperator": existing_operator or "UNKNOWN"})
                continue
            same_source_overlaps += 1
        else:
            newly_direct += 1

        e["tccV9DirectTariff"] = new_direct
        e["tccV9RankableDirect"] = True

    if conflicts:
        raise SystemExit(f"{len(conflicts)} conflicting rankable direct tariffs; first={conflicts[:5]}")

    evse_by_station = {}
    for e in evses:
        evse_by_station.setdefault(str(e.get("stationId") or ""), []).append(e)

    stations = payload.get("stations")
    if not isinstance(stations, list):
        raise SystemExit("candidate stations missing")

    for station in stations:
        rows = evse_by_station.get(str(station.get("stationId") or ""), [])
        station["evses"] = rows
        station["rankableDirectEvseCount"] = sum(1 for e in rows if e.get("tccV9RankableDirect") is True)
        station["rankableDirect"] = station["rankableDirectEvseCount"] > 0
        station["rankableSelectedSubscriptionEvseCount"] = sum(
            1 for e in rows if e.get("tccV9HasRankableSelectedSubscription") is True
        )
        station["hasRankableSelectedSubscription"] = station["rankableSelectedSubscriptionEvseCount"] > 0
        station["rankableEmspEvseCount"] = sum(1 for e in rows if e.get("tccV9HasRankableEmsp") is True)
        station["hasRankableEmsp"] = station["rankableEmspEvseCount"] > 0

    final_direct = sum(1 for e in evses if e.get("tccV9RankableDirect") is True)
    final_direct_by_operator = Counter(
        (e.get("tccV9DirectTariff") or {}).get("operator") or "UNKNOWN"
        for e in evses
        if e.get("tccV9RankableDirect") is True
    )
    final_emsp = sum(1 for e in evses if e.get("tccV9HasRankableEmsp") is True)
    final_emsp_by_provider = Counter()
    for e in evses:
        for tariff in e.get("tccV9EmspTariffs") or []:
            if isinstance(tariff, dict) and tariff.get("rankable") is True:
                final_emsp_by_provider[tariff.get("provider") or "UNKNOWN"] += 1

    if final_direct != baseline_direct + newly_direct:
        raise SystemExit("direct coverage accounting mismatch")
    if final_direct_by_operator.get(GO_ELECTRIC_OPERATOR, 0) != EXPECTED_READY_OFFERS:
        raise SystemExit(
            "Go Electric final direct coverage mismatch: "
            f"{final_direct_by_operator.get(GO_ELECTRIC_OPERATOR, 0)}"
        )
    if retired_legacy_entries <= 0:
        raise SystemExit("no legacy Go Electric/NextCharge eMSP entries were retired")

    residual_legacy_entries = sum(
        1
        for e in evses
        for tariff in (e.get("tccV9EmspTariffs") or [])
        if isinstance(tariff, dict) and is_legacy_go_electric_nextcharge_emsp(tariff)
    )
    if residual_legacy_entries:
        raise SystemExit(f"{residual_legacy_entries} legacy Go Electric/NextCharge eMSP entries remain")

    counts = payload.setdefault("counts", {})
    total_evses = len(evses)
    counts["rankableDirectEvseCount"] = final_direct
    counts["rankableDirectCoveragePct"] = round(100 * final_direct / total_evses, 2)
    counts["rankableDirectByOperator"] = dict(sorted(final_direct_by_operator.items()))
    counts["rankableEmspEvseCount"] = final_emsp
    counts["rankableEmspCoveragePct"] = round(100 * final_emsp / total_evses, 2)
    counts["rankableEmspByProvider"] = dict(sorted(final_emsp_by_provider.items()))

    emsp_providers = payload.setdefault("emspProviders", {})
    if not final_emsp_by_provider.get("NextCharge"):
        emsp_providers.pop("nextcharge", None)

    rules = payload.setdefault("rules", {})
    rules["goElectricOfficialB2CRequiresExactEvseIdentity"] = True
    rules["goElectricCoordinatesAreDiscoveryOnly"] = True
    rules["goElectricLegacyNextChargeEmspRetired"] = True
    rules["goElectricMultiComponentTariffsPreserved"] = True
    rules["goElectricPhysicalInventoryGrowthDoesNotAutoPriceNewEvse"] = True
    rules["preAuthorizationNeverCountsAsChargingCost"] = True

    accepted_by_station = Counter()
    for offer in offers:
        accepted_by_station[str(offer.get("punStationId") or "")] += 1

    accepted_stations = sum(1 for station_id in target_by_station if accepted_by_station[station_id] > 0)
    complete_stations = sum(
        1
        for station_id, target_count in target_by_station.items()
        if accepted_by_station[station_id] == target_count and target_count > 0
    )
    partial_stations = sum(
        1
        for station_id, target_count in target_by_station.items()
        if 0 < accepted_by_station[station_id] < target_count
    )
    unique_offer_stations = {str(o.get("punStationId") or "") for o in offers}
    if accepted_stations != len(unique_offer_stations):
        raise SystemExit(
            f"Go Electric station mapping drift: accepted={accepted_stations}, "
            f"readyOfferStations={len(unique_offer_stations)}"
        )

    current_without_accepted_direct = current_physical_evses - len(offers)
    if current_without_accepted_direct < 0:
        raise SystemExit("current physical inventory smaller than accepted exact offer set")

    payload["generatedAt"] = now_iso()
    payload["dataset"] = "italy-v9-consolidated-candidate-go-electric-direct-qa"
    payload["publicationAllowed"] = False
    payload["publicationReason"] = "Go Electric direct integration QA only; stable/runtime publication not authorized"
    payload["goElectricIntegration"] = {
        "status": "qa_pass_candidate",
        "operator": GO_ELECTRIC_OPERATOR,
        "officialB2C": "NextCharge",
        "acceptedExactEvseOffers": len(offers),
        "sourceGeneratedAt": source_generated_at,
        "semanticBaselinePhysicalStations": baseline_stations,
        "semanticBaselinePhysicalEvse": baseline_evses,
        "currentPhysicalStations": current_physical_stations,
        "currentPhysicalEvse": current_physical_evses,
        "physicalStationDeltaVsSemanticBaseline": station_delta,
        "physicalEvseDeltaVsSemanticBaseline": evse_delta,
        "currentPhysicalEvseWithoutAcceptedDirectOffer": current_without_accepted_direct,
        "physicalInventoryDriftPolicy": "non-blocking growth; only semantic-ready exact EVSE IDs receive direct tariffs",
        "stationLevelUpstreamQuarantine": station_quarantine,
        "connectorLevelSemanticExclusion": connector_exclusion,
        "legacyNextChargeEmspEntriesRetired": retired_legacy_entries,
        "legacyNextChargeEmspEvsesRetired": retired_legacy_evses,
        "sameSourceDirectOverlaps": same_source_overlaps,
        "newDirectEvse": newly_direct,
        "publicationAllowed": False,
    }

    report = {
        "schemaVersion": 2,
        "generatedAt": payload["generatedAt"],
        "publicationAllowed": False,
        "input": {
            "candidateDataset": candidate.get("dataset"),
            "candidateEvse": total_evses,
            "semanticBaselinePhysicalStations": baseline_stations,
            "semanticBaselinePhysicalEvse": baseline_evses,
            "goElectricPhysicalStations": current_physical_stations,
            "goElectricPhysicalEvse": current_physical_evses,
            "physicalStationDeltaVsSemanticBaseline": station_delta,
            "physicalEvseDeltaVsSemanticBaseline": evse_delta,
            "semanticReadyOffers": len(offers),
            "semanticSourceGeneratedAt": source_generated_at,
        },
        "before": {
            "rankableDirectEvse": baseline_direct,
            "rankableDirectCoveragePct": round(100 * baseline_direct / total_evses, 2),
            "rankableDirectByOperator": dict(sorted(baseline_direct_by_operator.items())),
            "rankableEmspEvse": baseline_emsp,
        },
        "integration": {
            "matchedCandidateEvse": len(offers) - len(missing),
            "missingCandidateEvse": len(missing),
            "newDirectEvse": newly_direct,
            "sameSourceDirectOverlaps": same_source_overlaps,
            "conflictingExistingDirectOverlaps": len(conflicts),
            "currentPhysicalEvseWithoutAcceptedDirectOffer": current_without_accepted_direct,
            "legacyNextChargeEmspEntriesRetired": retired_legacy_entries,
            "legacyNextChargeEmspEvsesRetired": retired_legacy_evses,
            "stationCoverage": {
                "acceptedStations": accepted_stations,
                "completeStationsAgainstCurrentInventory": complete_stations,
                "partialStationsAgainstCurrentInventory": partial_stations,
                "upstreamStationQuarantine": station_quarantine,
                "connectorSemanticExclusion": connector_exclusion,
            },
            "componentSets": dict(sorted(component_sets.items())),
        },
        "after": {
            "rankableDirectEvse": final_direct,
            "rankableDirectCoveragePct": round(100 * final_direct / total_evses, 2),
            "rankableDirectByOperator": dict(sorted(final_direct_by_operator.items())),
            "rankableEmspEvse": final_emsp,
            "rankableEmspCoveragePct": round(100 * final_emsp / total_evses, 2),
            "rankableEmspByProvider": dict(sorted(final_emsp_by_provider.items())),
        },
        "gates": {
            "semanticReadyOfferCount2214": len(offers) == EXPECTED_READY_OFFERS,
            "allAcceptedOffersMatchedCurrentCandidate": not missing,
            "currentPhysicalInventoryNotBelowSemanticBaseline": (
                current_physical_stations >= baseline_stations and current_physical_evses >= baseline_evses
            ),
            "physicalInventoryGrowthNotAutoPriced": (
                final_direct_by_operator.get(GO_ELECTRIC_OPERATOR, 0) == len(offers)
            ),
            "noDirectConflicts": not conflicts,
            "goElectricDirectCount2214": final_direct_by_operator.get(GO_ELECTRIC_OPERATOR, 0) == EXPECTED_READY_OFFERS,
            "legacyGoElectricNextChargeEmspRetired": retired_legacy_entries > 0 and residual_legacy_entries == 0,
            "publicationDisabled": payload.get("publicationAllowed") is False,
            "preAuthExcludedFromCostModel": True,
            "multiComponentTariffsPreserved": True,
            "exactIdentityRequired": True,
        },
    }

    if not all(report["gates"].values()):
        raise SystemExit(f"integration gates failed: {report['gates']}")

    write_gz_json(Path(args.out), payload)
    write_json(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
