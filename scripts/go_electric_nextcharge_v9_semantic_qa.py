#!/usr/bin/env python3
"""Semantic QA and fail-closed V9 staging for Go Electric / NextCharge Italy.

Input is the fully aggregated national extraction. This stage performs no
network access and never publishes runtime data. It emits an EVSE-scoped staging
set only when exact physical identity, tariff semantics and power consistency
are all validated. Everything else is quarantined with explicit reasons.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INPUT = Path("artifacts/go_electric_italy_v9_full_extraction.json")
REPORT_OUT = Path("artifacts/go_electric_italy_v9_semantic_qa.json")
READY_OUT = Path("artifacts/go_electric_italy_v9_ready_offers.json")
QUARANTINE_OUT = Path("artifacts/go_electric_italy_v9_semantic_quarantine.json")

EXPECTED_STATIONS = 1136
EXPECTED_EVSES = 2413
OPERATOR = "Go Electric Stations SRLS"
SOURCE = "NextCharge"
ALLOWED_PRICE_COMPONENTS = {"energy", "time", "session", "parking"}
ALLOWED_PARKING_TRIGGERS = {"onNoEnergyDelivery", "onAfterTime"}
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

# These thresholds are anomaly flags only, not tariff reinterpretation rules.
ANOMALY_THRESHOLDS = {
    "energy": 3.0,
    "time": 2.0,
    "session": 50.0,
    "parking": 5.0,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def evse_suffix(evse_id: str) -> str | None:
    if not isinstance(evse_id, str) or not evse_id.startswith("ITGESE"):
        return None
    suffix = evse_id[len("ITGESE"):]
    return suffix if suffix.isdigit() else None


def validate_restrictions(restrictions: Any, prices: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if restrictions is None:
        return errors
    if not isinstance(restrictions, dict):
        return ["restrictions_not_object"]
    unknown_top = set(restrictions) - {"parking"}
    if unknown_top:
        errors.append("unknown_restriction_component:" + ",".join(sorted(unknown_top)))
    parking = restrictions.get("parking")
    if parking is None:
        return errors
    if "parking" not in prices:
        errors.append("parking_restriction_without_parking_price")
    if not isinstance(parking, dict):
        errors.append("parking_restriction_not_object")
        return errors
    allowed_keys = {"trigger", "afterTime", "startTime", "endTime"}
    unknown = set(parking) - allowed_keys
    if unknown:
        errors.append("unknown_parking_restriction_key:" + ",".join(sorted(unknown)))
    trigger = parking.get("trigger")
    if trigger not in ALLOWED_PARKING_TRIGGERS:
        errors.append("unsupported_parking_trigger")
    if trigger == "onAfterTime":
        after = parking.get("afterTime")
        if not is_number(after) or float(after) < 0:
            errors.append("invalid_parking_after_time")
    elif "afterTime" in parking:
        errors.append("unexpected_parking_after_time")
    for key in ("startTime", "endTime"):
        if key in parking and (not isinstance(parking[key], str) or not TIME_RE.match(parking[key])):
            errors.append(f"invalid_{key}")
    if ("startTime" in parking) ^ ("endTime" in parking):
        errors.append("incomplete_parking_time_window")
    return errors


def validate_connector(station: dict[str, Any], connector: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    anomalies: list[dict[str, Any]] = []
    pun_evse_id = connector.get("punEvseId")
    uid = str(connector.get("uidConnector") or "")
    suffix = evse_suffix(pun_evse_id)
    if suffix is None:
        errors.append("invalid_pun_evse_id")
    elif uid != suffix:
        errors.append("exact_identity_mismatch")
    if connector.get("powerCompatible") is not True:
        errors.append("power_not_compatible")

    tariff = connector.get("tariff")
    if not isinstance(tariff, dict):
        return errors + ["tariff_missing"], anomalies
    if tariff.get("currency") != "EUR":
        errors.append("unsupported_currency")
    prices = tariff.get("prices")
    if not isinstance(prices, dict) or not prices:
        errors.append("prices_missing")
        prices = {}
    unknown_components = set(prices) - ALLOWED_PRICE_COMPONENTS
    if unknown_components:
        errors.append("unknown_price_component:" + ",".join(sorted(unknown_components)))
    if "energy" not in prices:
        errors.append("energy_component_missing")
    for component, amount in prices.items():
        if not is_number(amount) or float(amount) < 0:
            errors.append(f"invalid_price:{component}")
            continue
        threshold = ANOMALY_THRESHOLDS.get(component)
        if threshold is not None and float(amount) > threshold:
            anomalies.append({"type": "high_price_component", "component": component, "amount": float(amount), "threshold": threshold})

    errors.extend(validate_restrictions(tariff.get("restrictions"), prices))
    preauth = tariff.get("preAuth")
    if preauth is not None and (not is_number(preauth) or float(preauth) < 0):
        errors.append("invalid_preauth")
    payment_required = tariff.get("paymentRequired")
    if payment_required is not None and not isinstance(payment_required, bool):
        errors.append("invalid_payment_required")
    return sorted(set(errors)), anomalies


def price_components(tariff: dict[str, Any]) -> list[dict[str, Any]]:
    units = {
        "energy": "per_kWh",
        "time": "source_time_rate",
        "session": "per_session",
        "parking": "source_parking_rate",
    }
    return [
        {"sourceType": key, "amount": float(value), "sourceUnit": units[key]}
        for key, value in (tariff.get("prices") or {}).items()
        if key in units
    ]


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    summary = data.get("summary") or {}
    policy = data.get("policy") or {}
    if summary.get("processedStations") != EXPECTED_STATIONS:
        raise SystemExit(f"national station coverage incomplete: {summary.get('processedStations')}")
    if summary.get("targetPunEvses") != EXPECTED_EVSES:
        raise SystemExit(f"national EVSE baseline incomplete: {summary.get('targetPunEvses')}")
    if policy.get("exactPunEvseSuffixRequiredForAttribution") is not True:
        raise SystemExit("upstream exact-identity policy missing")
    if policy.get("coordinateOnlyAttributionAllowed") is not False:
        raise SystemExit("coordinate-only attribution unexpectedly allowed")
    if policy.get("directCpoPublicationAllowed") is not False:
        raise SystemExit("upstream extraction unexpectedly publishable")

    ready: list[dict[str, Any]] = []
    semantic_quarantine: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()

    # Preserve the upstream station-level quarantine as-is. It is never promoted
    # by this semantic stage.
    upstream_quarantine = data.get("quarantine") or []
    for row in upstream_quarantine:
        reason = "upstream_station_not_exactly_attributed"
        semantic_quarantine.append({"scope": "station", "reason": reason, "source": row})
        reason_counts[reason] += 1

    seen_evse: set[str] = set()
    for station in data.get("acceptedExactTariffs") or []:
        for connector in station.get("connectors") or []:
            evse_id = connector.get("punEvseId")
            if evse_id in seen_evse:
                errors = ["duplicate_pun_evse_id"]
                connector_anomalies: list[dict[str, Any]] = []
            else:
                seen_evse.add(evse_id)
                errors, connector_anomalies = validate_connector(station, connector)
            if errors:
                semantic_quarantine.append({
                    "scope": "evse",
                    "punStationId": station.get("punStationId"),
                    "punEvseId": evse_id,
                    "reasons": errors,
                    "connector": connector,
                })
                for reason in errors:
                    reason_counts[reason] += 1
                continue

            tariff = connector["tariff"]
            record = {
                "offerId": f"go-electric-nextcharge-{evse_id}",
                "country": "IT",
                "operator": OPERATOR,
                "source": SOURCE,
                "scope": "evse",
                "punStationId": station.get("punStationId"),
                "punEvseId": evse_id,
                "nextChargeStationId": station.get("nextChargeStationId"),
                "uidConnector": str(connector.get("uidConnector")),
                "connectorType": connector.get("standard"),
                "current": connector.get("current"),
                "powerKw": connector.get("powerMax"),
                "expectedPowerKw": connector.get("expectedPowerKw"),
                "currency": "EUR",
                "priceComponents": price_components(tariff),
                "restrictions": tariff.get("restrictions"),
                "preAuth": tariff.get("preAuth"),
                "paymentRequired": tariff.get("paymentRequired"),
                "rawTariff": tariff,
                "provenance": {
                    "channel": SOURCE,
                    "operatorCpo": OPERATOR,
                    "identityRule": "ITGESE numeric suffix == uidConnector",
                    "exactPhysicalIdentity": True,
                    "distanceM": station.get("distanceM"),
                },
                "qa": {
                    "semanticValidated": True,
                    "powerCompatible": True,
                    "knownPriceComponentsOnly": True,
                    "knownRestrictionSemanticsOnly": True,
                    "anomalyFlags": connector_anomalies,
                },
                "publicationAllowed": False,
            }
            ready.append(record)
            for anomaly in connector_anomalies:
                anomalies.append({"punEvseId": evse_id, **anomaly})

    ready.sort(key=lambda x: x["punEvseId"])
    semantic_quarantine.sort(key=lambda x: (x.get("scope", ""), str(x.get("punEvseId") or x.get("source", {}).get("punStationId") or "")))
    component_counts: Counter[str] = Counter()
    component_sets: Counter[str] = Counter()
    for row in ready:
        components = sorted(c["sourceType"] for c in row["priceComponents"])
        component_sets["+".join(components)] += 1
        component_counts.update(components)

    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "inputBaseline": {"stationCount": EXPECTED_STATIONS, "evseCount": EXPECTED_EVSES},
        "policy": {
            "readOnlyTransform": True,
            "networkAccess": False,
            "exactPhysicalIdentityRequired": True,
            "coordinateFallbackAllowed": False,
            "unknownTariffSemanticsAllowed": False,
            "publicationAllowed": False,
            "publicationReason": "semantic_qa_staging_only_requires_consolidation_integration_gate",
        },
        "summary": {
            "upstreamExactStations": summary.get("exactMatchedStations"),
            "upstreamQuarantinedStations": summary.get("quarantinedStations"),
            "upstreamExactConnectors": summary.get("exactConnectorMatches"),
            "readyEvseOffers": len(ready),
            "semanticQuarantineRows": len(semantic_quarantine),
            "semanticQuarantineReasons": dict(reason_counts),
            "anomalyFlags": len(anomalies),
            "componentCounts": dict(component_counts),
            "componentSets": dict(component_sets),
        },
        "anomalies": anomalies,
    }

    REPORT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    READY_OUT.write_text(json.dumps({"schemaVersion": 1, "generatedAt": report["generatedAt"], "publicationAllowed": False, "offers": ready}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    QUARANTINE_OUT.write_text(json.dumps({"schemaVersion": 1, "generatedAt": report["generatedAt"], "rows": semantic_quarantine}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if len(ready) != len({row["punEvseId"] for row in ready}):
        raise SystemExit("ready offers contain duplicate EVSE IDs")
    if any(row.get("publicationAllowed") is not False for row in ready):
        raise SystemExit("ready staging accidentally enables publication")


if __name__ == "__main__":
    main()
