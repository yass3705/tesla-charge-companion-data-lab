#!/usr/bin/env python3
"""Promote exact official Ubitricity NL PAYG matches into DOT-NL.

The source candidate is generated from Ubitricity's own public PAYG portal and
reconciled against exact national EVSE and connector IDs. No Shell Recharge,
eMSP, roaming, regular/member tariff, or station-level inheritance is used.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SOURCE = "https://charge.ubitricity.com/<EVSE-ID>"
PARTY = "UB2"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_gz(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def read_candidate(path: Path) -> dict:
    if path.suffix == ".b64":
        packed = base64.b64decode(path.read_bytes())
        return json.loads(gzip.decompress(packed))
    return json.loads(path.read_text(encoding="utf-8"))


def write_gz(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized", type=Path, default=Path("data/national/netherlands_dotnl/normalized.json.gz"))
    parser.add_argument("--candidate", type=Path, default=Path("data/operator_direct/ubitricity_nl_payg_exact_overlay_candidate.json.gz.b64"))
    parser.add_argument("--overlay", type=Path, default=Path("data/operator_direct/ubitricity_nl_payg_exact_overlay.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/netherlands/ubitricity-direct-payg-integration-latest.json"))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    data = read_gz(args.normalized)
    candidate = read_candidate(args.candidate)
    if candidate.get("partyId") != PARTY or candidate.get("policy", {}).get("officialPortalOnly") is not True:
        raise SystemExit("Candidate source/policy is not the approved official Ubitricity PAYG dataset")

    index: dict[tuple[str, str], tuple[dict, dict]] = {}
    duplicates: Counter[tuple[str, str]] = Counter()
    for station in data.get("stations") or []:
        if station.get("partyId") != PARTY:
            continue
        for evse in station.get("evses") or []:
            for connector in evse.get("connectors") or []:
                key = (str(evse.get("evseId") or ""), str(connector.get("id") or ""))
                if key in index:
                    duplicates[key] += 1
                else:
                    index[key] = (station, connector)

    promoted: list[dict] = []
    rejected: list[dict] = []
    tariffs: dict[str, dict] = {}
    conflicts: list[dict] = []
    for row in candidate.get("matches") or []:
        key = (str(row.get("evseId") or ""), str(row.get("connectorId") or ""))
        pair = index.get(key)
        if not pair or pair[0].get("stationId") != row.get("stationId") or duplicates[key]:
            rejected.append({"evseId": key[0], "connectorId": key[1], "reason": "national_identity_missing_or_duplicated"})
            continue
        station, connector = pair
        source_tariff = candidate.get("tariffs", {}).get(row.get("tariffKey"))
        if not source_tariff or source_tariff.get("type") != "AD_HOC_PAYMENT":
            rejected.append({"evseId": key[0], "connectorId": key[1], "reason": "not_explicit_ad_hoc"})
            continue
        token = json.dumps(source_tariff.get("elements") or [], sort_keys=True, separators=(",", ":"))
        tariff_key = "NL:UB2:UBITRICITY-PAYG:" + hashlib.sha256(token.encode()).hexdigest()[:16]
        tariff = {
            "tariffKey": tariff_key,
            "countryCode": "NL",
            "partyId": PARTY,
            "tariffId": tariff_key.rsplit(":", 1)[-1],
            "type": "AD_HOC_PAYMENT",
            "currency": source_tariff.get("currency", "EUR"),
            "elements": source_tariff.get("elements") or [],
            "source": SOURCE,
            "sourceKind": "official_cpo_direct_payg_portal",
            "sourceMetadata": {
                "provider": "ubitricity",
                "cpoOnly": True,
                "emspExcluded": True,
                "roamingExcluded": True,
                "shellRechargeExcluded": True,
                "matchPolicy": "exact DOT-NL station, EVSE and connector identity",
                "preAuthorizationIsNotTariff": True,
            },
        }
        if tariff_key in data.get("tariffs", {}) and data["tariffs"][tariff_key] != tariff:
            conflicts.append({"tariffKey": tariff_key, "reason": "normalized_tariff_key_conflict"})
            continue
        old_keys = list(connector.get("tariffKeys") or [])
        old_ids = list(connector.get("tariffIds") or [])
        if old_keys == [tariff_key] and not old_ids:
            tariffs[tariff_key] = tariff
            promoted.append({
                "stationId": row["stationId"], "evseId": key[0], "connectorId": key[1],
                "tariffKey": tariff_key, "sourceTariffKey": row["tariffKey"],
                "sourceUrl": row.get("sourceUrl"), "preAuthEur": row.get("preAuthEur"),
                "prices": row.get("prices"), "match": "exact_evse_and_connector",
            })
            continue
        resolvable_old_ids = [
            old_id for old_id in old_ids
            if old_id in (data.get("tariffs") or {})
            or any(t.get("tariffId") == old_id for t in (data.get("tariffs") or {}).values())
        ]
        if old_keys or resolvable_old_ids:
            # Existing DOT-NL tariff ownership stays authoritative. The PAYG
            # overlay is promoted only to connectors with no national tariff.
            rejected.append({"evseId": key[0], "connectorId": key[1], "reason": "existing_dotnl_tariff_preserved"})
            continue
        tariffs[tariff_key] = tariff
        promoted.append({
            "stationId": row["stationId"],
            "evseId": key[0],
            "connectorId": key[1],
            "tariffKey": tariff_key,
            "sourceTariffKey": row["tariffKey"],
            "sourceUrl": row.get("sourceUrl"),
            "preAuthEur": row.get("preAuthEur"),
            "supersededUnresolvedDotnlTariffIds": old_ids,
            "prices": row.get("prices"),
            "match": "exact_evse_and_connector",
        })
        if not args.no_write:
            connector["tariffKeys"] = [tariff_key]
            connector["tariffIds"] = []
            connector["unresolvedTariffIds"] = []

    if conflicts:
        raise SystemExit(f"Refusing to write: tariff key conflicts: {len(conflicts)}")

    data_tariffs = data.get("tariffs") or {}
    data_tariffs.update(tariffs)
    data["tariffs"] = data_tariffs
    overlay = {
        "schemaVersion": 1,
        "dataset": "nl-ubitricity-direct-payg-exact-overlay",
        "generatedAt": now(),
        "country": "NL",
        "partyId": PARTY,
        "source": SOURCE,
        "tariffs": tariffs,
        "matches": promoted,
        "excludedSourceRows": candidate.get("excluded") or [],
        "policy": {
            "directCpoOnly": True,
            "officialPortalOnly": True,
            "shellProviderApiExcluded": True,
            "exactEvseAndConnectorMatchOnly": True,
            "duplicateEvseIdsFailClosed": True,
            "preAuthIsNotAChargingPrice": True,
                "existingDotnlTariffsPreserved": True,
                "unresolvedDotnlReferencesReplacedOnlyWithExactOfficialPayg": True,
        },
    }
    report = {
        "schemaVersion": 1,
        "generatedAt": overlay["generatedAt"],
        "dataset": "netherlands-ubitricity-direct-payg-integration",
        "candidateMatchedConnectors": len(candidate.get("matches") or []),
        "promotedExactConnectors": len(promoted),
        "excludedSourceAmbiguities": len(candidate.get("excluded") or []),
        "rejected": len(rejected),
        "rejectedReasons": dict(Counter(row["reason"] for row in rejected)),
        "scheduleCount": len(tariffs),
        "status": "integrated" if not args.no_write else "validated_no_write",
        "source": SOURCE,
        "sourceCandidate": str(args.candidate),
        "overlaySha256": hashlib.sha256(json.dumps(overlay, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "policy": overlay["policy"],
    }
    if not args.no_write:
        write_gz(args.normalized, data)
        args.overlay.parent.mkdir(parents=True, exist_ok=True)
        args.overlay.write_text(json.dumps(overlay, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
