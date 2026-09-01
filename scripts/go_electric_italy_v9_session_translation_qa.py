#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_READY = 2214
EXPECTED_SESSION_ONLY = 127
EXPECTED_ENGINE_BLOB_SHA = "8b58d24917322ab2526877d83d3ee3e7b1f99ce7"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def finite_nonnegative(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    n = float(value)
    return n if math.isfinite(n) and n >= 0 else None


def component_map(offer: dict) -> dict[str, dict]:
    out = {}
    for comp in offer.get("priceComponents") or []:
        if not isinstance(comp, dict):
            raise ValueError("invalid component row")
        typ = str(comp.get("sourceType") or "")
        if typ in out:
            raise ValueError(f"duplicate component {typ}")
        out[typ] = comp
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ready", required=True)
    ap.add_argument("--unit-audit", required=True)
    ap.add_argument("--out", default="data/qa/go_electric_italy_v9_session_runtime_offers.json")
    ap.add_argument("--vectors", default="data/qa/go_electric_italy_v9_session_runtime_vectors.json")
    ap.add_argument("--report", default="data/reports/go_electric_italy_v9_session_translation_qa.json")
    args = ap.parse_args()

    ready = load(Path(args.ready))
    audit = load(Path(args.unit_audit))
    if ready.get("publicationAllowed") is not False:
        raise SystemExit("semantic ready artifact must remain publicationAllowed=false")
    offers = ready.get("offers")
    if not isinstance(offers, list) or len(offers) != EXPECTED_READY:
        raise SystemExit("semantic ready offer count drift")
    if audit.get("publicationAllowed") is not False or audit.get("multiComponentUnlockAllowed") is not False:
        raise SystemExit("component unit audit must remain fail-closed")
    candidate = audit.get("nextTranslationCandidate") or {}
    if candidate.get("componentSet") != "energy+session" or candidate.get("evseCount") != EXPECTED_SESSION_ONLY:
        raise SystemExit("component audit session candidate drift")

    runtime_offers = []
    vectors = []
    rejected = []
    for offer in offers:
        try:
            comps = component_map(offer)
        except ValueError as exc:
            rejected.append({"evseId": offer.get("punEvseId"), "reason": str(exc)})
            continue
        if set(comps) != {"energy", "session"}:
            continue
        eid = str(offer.get("punEvseId") or "").upper()
        if not eid:
            rejected.append({"evseId": None, "reason": "missing_evse_id"})
            continue
        energy = comps["energy"]
        session = comps["session"]
        energy_rate = finite_nonnegative(energy.get("amount"))
        session_fee = finite_nonnegative(session.get("amount"))
        if energy.get("sourceUnit") != "per_kWh" or session.get("sourceUnit") != "per_session":
            rejected.append({"evseId": eid, "reason": "source_unit_mismatch"})
            continue
        if energy_rate is None or session_fee is None:
            rejected.append({"evseId": eid, "reason": "invalid_amount"})
            continue
        provenance = offer.get("provenance") or {}
        qa = offer.get("qa") or {}
        if provenance.get("exactPhysicalIdentity") is not True or qa.get("semanticValidated") is not True or qa.get("powerCompatible") is not True:
            rejected.append({"evseId": eid, "reason": "identity_or_semantic_gate"})
            continue
        pricing = {
            "type": "rules",
            "rules": [{
                "scope": "allDay",
                "start": "00:00",
                "end": "24:00",
                "currency": "EUR",
                "pricePerKwh": energy_rate,
                "sessionFeeEur": session_fee,
            }],
        }
        runtime_offer = {
            "id": f"it:direct:go-electric-session:{eid}",
            "provider": "Go Electric Stations SRLS",
            "evseIds": [eid],
            "verifiedScope": "exact_evse",
            "countries": ["IT"],
            "currency": "EUR",
            "priority": 130,
            "source": "NextCharge official Go Electric B2C",
            "sourceId": "go-electric-session-translation-qa",
            "directOperatorOnly": True,
            "pricing": pricing,
            "metadata": {
                "channel": "operator_direct",
                "officialB2C": True,
                "sourceUnits": {"energy": "per_kWh", "session": "per_session"},
                "sourceOfferId": offer.get("offerId"),
                "runtimeTranslation": "energy->pricePerKwh; session->sessionFeeEur",
                "publicationAllowed": False,
            },
        }
        runtime_offers.append(runtime_offer)
        test_energy = 17.25
        expected = round(test_energy * energy_rate + session_fee, 6)
        vectors.append({
            "offerId": runtime_offer["id"],
            "evseId": eid,
            "session": {
                "energyKwh": test_energy,
                "durationMinutes": 47,
                "startAt": "2026-09-01T12:00:00+02:00",
                "timeZone": "Europe/Rome",
            },
            "expectedTotalEur": expected,
            "expectedEnergyEur": round(test_energy * energy_rate, 6),
            "expectedSessionFeeEur": round(session_fee, 6),
        })

    ids = [o["evseIds"][0] for o in runtime_offers]
    if len(runtime_offers) != EXPECTED_SESSION_ONLY or len(set(ids)) != EXPECTED_SESSION_ONLY:
        raise SystemExit(f"expected {EXPECTED_SESSION_ONLY} session translation offers, got {len(runtime_offers)}")
    if rejected:
        raise SystemExit(f"session translation rejected rows: {rejected[:5]}")

    output = {
        "schemaVersion": 1,
        "country": "IT",
        "operator": "Go Electric Stations SRLS",
        "generatedAt": now_iso(),
        "publicationAllowed": False,
        "builderActivationAllowed": False,
        "stablePricingEngineBlobSha": EXPECTED_ENGINE_BLOB_SHA,
        "offers": runtime_offers,
    }
    vector_payload = {
        "schemaVersion": 1,
        "publicationAllowed": False,
        "stablePricingEngineBlobSha": EXPECTED_ENGINE_BLOB_SHA,
        "vectors": vectors,
    }
    report = {
        "schemaVersion": 1,
        "generatedAt": output["generatedAt"],
        "publicationAllowed": False,
        "builderActivationAllowed": False,
        "semanticReadyOffers": len(offers),
        "sessionTranslationCandidateEvse": len(runtime_offers),
        "translation": {
            "energy": {"sourceUnit": "per_kWh", "runtimeField": "pricePerKwh"},
            "session": {"sourceUnit": "per_session", "runtimeField": "sessionFeeEur"},
        },
        "stablePricingEngineBlobSha": EXPECTED_ENGINE_BLOB_SHA,
        "remainingBlocked": {
            "timeComponentOffers": int((audit.get("blockers") or {}).get("unresolvedTimeUnitOffers") or 0),
            "parkingComponentOffers": int((audit.get("blockers") or {}).get("unresolvedParkingUnitOrTriggerMappingOffers") or 0),
        },
        "gates": {
            "candidateCount127": len(runtime_offers) == EXPECTED_SESSION_ONLY,
            "uniqueExactEvse": len(set(ids)) == EXPECTED_SESSION_ONLY,
            "sourceUnitsExact": all(o["metadata"]["sourceUnits"] == {"energy": "per_kWh", "session": "per_session"} for o in runtime_offers),
            "runtimeSchemaUsesSessionFeeEur": all("sessionFeeEur" in o["pricing"]["rules"][0] for o in runtime_offers),
            "timeAndParkingRemainBlocked": (audit.get("blockers") or {}).get("unresolvedTimeUnitOffers") == 1052 and (audit.get("blockers") or {}).get("unresolvedParkingUnitOrTriggerMappingOffers") == 700,
            "builderActivationDisabled": True,
            "publicationDisabled": True,
        },
    }
    if not all(report["gates"].values()):
        raise SystemExit(f"session translation gates failed: {report['gates']}")
    write(Path(args.out), output)
    write(Path(args.vectors), vector_payload)
    write(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
