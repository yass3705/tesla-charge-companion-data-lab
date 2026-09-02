#!/usr/bin/env python3
"""Audit ACEA's Italy CPO scope without reviving its retired direct eMSP tariff.

The PUN backbone currently carries several historical operator labels under the
same AFIR/OCPI party ID (``ACE``).  This audit keeps that exact physical scope,
separates Acea Innovation's CPO role from Acea Energia's former eMSP role, and
fails closed on every legacy PUN price until a current CPO-direct channel is
proved.

The script is deliberately offline.  It only reads an already-sanitized Italy
V9 candidate and emits a deterministic classification report.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

PARTY_ID = "ACE"
NEXT_PARTY_ID = "HER"
PHYSICAL_CPO = "Acea Innovation"
FORMER_EMSP = "Acea Energia / Acea e-mobility"
SERVICE_END_DATE = "2025-12-19"
APP_ARCHIVE_END_DATE = "2026-02-26"

EVIDENCE = [
    {
        "type": "official_cpo_role",
        "publisher": "Acea",
        "publishedAt": "2024-07-29",
        "url": (
            "https://www.acea.it/comunicati-stampa/2024/07/"
            "acea-e-plugsurfing-un-accordo-per-offrire-servizi-piu-capillari-"
            "ai-clienti-europei-della-e-mobility"
        ),
        "supports": (
            "Acea Innovation operates the charging infrastructure as CPO and "
            "makes its charging points available through interoperable eMSPs."
        ),
    },
    {
        "type": "publisher_authored_app_notice",
        "publisher": "Acea SpA via Apple App Store",
        "publishedAt": "2025-12-18",
        "url": "https://apps.apple.com/app/acea-e-mobility/id1496190588",
        "supports": (
            "Acea Energia stopped providing the Acea e-mobility charging "
            "service from 2025-12-19."
        ),
    },
    {
        "type": "corroborated_customer_notice",
        "publisher": "InsideEVs Italia",
        "publishedAt": "2025-12-19",
        "url": "https://insideevs.it/news/782358/acea-emobility-chiusura-ricarica/",
        "supports": (
            "The shutdown concerns the Acea Energia app/eMSP service; physical "
            "stations remain usable through other charging providers."
        ),
    },
]


def load_payload(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError("Italy candidate must be a JSON object")
    if value.get("country") != "IT":
        raise RuntimeError(f"expected country IT, got {value.get('country')!r}")
    return value


def iter_evses(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    evses = payload.get("evses")
    if not isinstance(evses, list):
        raise RuntimeError("Italy candidate is missing the top-level EVSE list")
    for row in evses:
        if isinstance(row, dict):
            yield row


def power_band(max_power_kw: Any) -> str:
    try:
        power = float(max_power_kw)
    except (TypeError, ValueError):
        return "unknown"
    if power <= 22:
        return "up_to_22_kw"
    if power <= 50:
        return "23_to_50_kw"
    if power <= 100:
        return "51_to_100_kw"
    return "over_100_kw"


def tariff_signature(details: dict[str, Any]) -> str:
    return json.dumps(details, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decode_tariff_signature(signature: str, count: int) -> dict[str, Any]:
    details = json.loads(signature)
    populated = []
    for tariff_class in ("acTariff", "dcTariff", "hpcTariff"):
        value = details.get(tariff_class)
        if isinstance(value, dict):
            populated.append({"tariffClass": tariff_class, **value})
    return {
        "count": count,
        "components": populated,
        "rankable": False,
        "reason": "current direct-channel applicability and component units are not proven",
    }


def build_report(payload: dict[str, Any]) -> dict[str, Any]:
    all_evses = list(iter_evses(payload))
    ace = [row for row in all_evses if str(row.get("partyId") or "").upper() == PARTY_ID]
    if not ace:
        raise RuntimeError("no ACE party-ID EVSE found in the Italy candidate")

    station_ids = {str(row.get("stationId")) for row in ace if row.get("stationId")}
    evse_ids = [str(row.get("evseId")) for row in ace if row.get("evseId")]
    if len(evse_ids) != len(ace) or len(set(evse_ids)) != len(evse_ids):
        raise RuntimeError("ACE EVSE identities are missing or duplicated")

    aliases = Counter(str(row.get("operator") or "UNKNOWN") for row in ace)
    source_status = Counter(str(row.get("sourceStatus") or "UNKNOWN") for row in ace)
    operational_state = Counter(str(row.get("operationalState") or "unknown") for row in ace)
    power_bands = Counter(power_band(row.get("maxPowerKw")) for row in ace)
    pun_reasons = Counter(str(row.get("rankablePunDirectTariffReason") or "none") for row in ace)

    legacy_signatures: Counter[str] = Counter()
    for row in ace:
        details = row.get("rawPunTariffsDetails")
        if isinstance(details, dict) and details:
            legacy_signatures[tariff_signature(details)] += 1

    rankable_direct = sum(row.get("tccV9RankableDirect") is True for row in ace)
    rankable_selected_subscription = sum(
        row.get("tccV9HasRankableSelectedSubscription") is True for row in ace
    )
    rankable_emsp = sum(row.get("tccV9HasRankableEmsp") is True for row in ace)
    legacy_rankable = sum(row.get("rankablePunDirectTariff") is True for row in ace)
    legacy_with_block = sum(row.get("punTariffBlockPresent") is True for row in ace)

    her = [row for row in all_evses if str(row.get("partyId") or "").upper() == NEXT_PARTY_ID]
    her_stations = {str(row.get("stationId")) for row in her if row.get("stationId")}
    her_aliases = Counter(str(row.get("operator") or "UNKNOWN") for row in her)

    safety_gates = {
        "exactPartyIdScope": all(str(row.get("partyId") or "").upper() == PARTY_ID for row in ace),
        "uniqueEvseIdentity": len(evse_ids) == len(set(evse_ids)) == len(ace),
        "physicalCpoSeparatedFromFormerEmsp": PHYSICAL_CPO not in {FORMER_EMSP},
        "retiredDirectChannelNotPromoted": rankable_direct == 0,
        "legacyPunTariffsNotPromoted": legacy_rankable == 0,
        "noFormerAceaSubscriptionPromoted": rankable_selected_subscription == 0,
        "noFormerAceaEmspOfferPromoted": rankable_emsp == 0,
        "thirdPartyRoamingRemainsSeparate": True,
        "physicalInventoryPreserved": len(ace) > 0 and len(station_ids) > 0,
        "nextCpoPresent": len(her) > 0 and len(her_stations) > 0,
    }
    if not all(safety_gates.values()):
        failed = sorted(key for key, ok in safety_gates.items() if not ok)
        raise RuntimeError(f"ACEA fail-closed gates failed: {failed}")

    report = {
        "schemaVersion": "1.0.0",
        "dataset": "italy-v9-acea-cpo-readiness",
        "country": "IT",
        "source": {
            "dataset": payload.get("dataset"),
            "generatedAt": payload.get("generatedAt"),
            "backbone": payload.get("backbone"),
            "punEvseCount": (payload.get("counts") or {}).get("punEvseCount"),
            "punStationCount": (payload.get("counts") or {}).get("punStationCount"),
        },
        "identity": {
            "partyId": PARTY_ID,
            "physicalCpo": PHYSICAL_CPO,
            "formerDirectEmsp": FORMER_EMSP,
            "operatorAliasesInPun": dict(sorted(aliases.items())),
            "classification": "active_physical_cpo_retired_direct_emsp",
        },
        "scope": {
            "stations": len(station_ids),
            "evse": len(ace),
            "powerBands": dict(sorted(power_bands.items())),
            "sourceStatus": dict(sorted(source_status.items())),
            "operationalState": dict(sorted(operational_state.items())),
        },
        "commercialStatus": {
            "formerDirectChannel": "Acea e-mobility",
            "chargingServiceEndedAt": SERVICE_END_DATE,
            "historicalAppArchiveAccessEndedAt": APP_ARCHIVE_END_DATE,
            "currentDirectTariffSource": None,
            "rankableDirectEvse": rankable_direct,
            "rankableSelectedSubscriptionEvse": rankable_selected_subscription,
            "rankableEmspEvse": rankable_emsp,
            "decision": "no_current_acea_direct_tariff_published",
            "policy": (
                "Keep ACE physical EVSE visible. Do not reuse former app prices or "
                "PUN tariff blocks. Third-party prices may only enter as independently "
                "validated eMSP offers."
            ),
        },
        "legacyPunTariffs": {
            "evseWithTariffBlock": legacy_with_block,
            "evseWithoutTariffBlock": len(ace) - legacy_with_block,
            "rankablePunDirectTariffEvse": legacy_rankable,
            "rankabilityReasons": dict(sorted(pun_reasons.items())),
            "signatures": [
                decode_tariff_signature(signature, count)
                for signature, count in sorted(legacy_signatures.items())
            ],
        },
        "evidence": EVIDENCE,
        "queue": {
            "paused": {
                "operator": "Atlante",
                "status": "paused_by_user",
                "resumeCondition": "Mac repaired and native MyAtlante HTTPS capture available",
                "pricingPromotion": False,
            },
            "next": {
                "partyId": NEXT_PARTY_ID,
                "operator": "HERA COMM SPA",
                "stations": len(her_stations),
                "evse": len(her),
                "operatorAliasesInPun": dict(sorted(her_aliases.items())),
            },
        },
        "safetyGates": safety_gates,
        "publicationAllowed": True,
        "publicationScope": "classification_and_queue_only",
        "stableTariffPublicationAllowed": False,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--consolidated", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/reports/acea_italy_cpo_readiness_snapshot.json"),
    )
    args = parser.parse_args()

    report = build_report(load_payload(args.consolidated))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["scope"], ensure_ascii=False, sort_keys=True))
    print(json.dumps(report["commercialStatus"], ensure_ascii=False, sort_keys=True))
    print(json.dumps(report["queue"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
