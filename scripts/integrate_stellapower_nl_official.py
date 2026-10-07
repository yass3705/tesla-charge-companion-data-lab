#!/usr/bin/env python3
"""Integrate StellaPower's official Dutch direct-pay tariff.

StellaPower states on its own public site that Dutch public chargers use a
fixed national energy tariff, paid by QR/card, with a post-session parking
charge.  The national DOT-NL records are accepted only when partyId is SPA.
No roaming, eMSP, card-contract, or station-level inference is used.
"""

from __future__ import annotations

import argparse
import gzip
import errno
import hashlib
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path


PARTY = "SPA"
SOURCE = "https://www.stellapower.nl/gratis-openbare-laadpaal-aanvragen"
FAQ = "https://www.stellapower.nl/veelgestelde-vragen"
ENERGY_GROSS = 0.57
PARKING_GROSS = 0.44
PARKING_STEP_SECONDS = 900
PARKING_MIN_SECONDS = 4 * 60 * 60


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_normalized(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_normalized(path: Path, payload: dict) -> None:
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def fetch_official_markers() -> dict:
    checks = {}
    for name, url, markers in (
        ("tariff", SOURCE, ("0,57", "0.57", "0,44", "0.44", "QR")),
        ("faq", FAQ, ("kwH", "kWh", "laadpaal")),
    ):
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,*/*"})
        with urllib.request.urlopen(request, timeout=60) as response:
            text = response.read().decode("utf-8", "replace")
        folded = re.sub(r"\s+", " ", text).lower()
        present = [marker for marker in markers if marker.lower() in folded]
        if name == "tariff" and not {"0,57", "0.57"} & set(present):
            raise RuntimeError("StellaPower official tariff page no longer exposes the national energy price")
        if name == "tariff" and not {"0,44", "0.44"} & set(present):
            raise RuntimeError("StellaPower official tariff page no longer exposes the parking price")
        checks[name] = {"url": url, "markers": present}
    return checks


def tariff() -> tuple[str, dict]:
    token = f"{ENERGY_GROSS:.6f}:{PARKING_GROSS:.6f}:{PARKING_STEP_SECONDS}:{PARKING_MIN_SECONDS}"
    key = "NL:SPA:STELLAPOWER-PAYG:" + hashlib.sha256(token.encode()).hexdigest()[:16]
    return key, {
        "tariffKey": key,
        "countryCode": "NL",
        "partyId": PARTY,
        "tariffId": key.rsplit(":", 1)[-1],
        "type": "AD_HOC_PAYMENT",
        "currency": "EUR",
        "elements": [
            {"priceComponents": [{"type": "ENERGY", "priceInclVat": ENERGY_GROSS, "stepSize": 1}], "restrictions": {}},
            {
                "priceComponents": [{"type": "PARKING_TIME", "priceInclVat": PARKING_GROSS, "stepSize": PARKING_STEP_SECONDS}],
                "restrictions": {
                    "min_duration": PARKING_MIN_SECONDS,
                    "day_of_week": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"],
                    "start_time": "09:00",
                    "end_time": "21:00",
                },
            },
        ],
        "source": SOURCE,
        "sourceKind": "official_cpo_direct_payg_qr",
        "sourceMetadata": {
            "provider": "StellaPower",
            "cpoOnly": True,
            "emspExcluded": True,
            "roamingExcluded": True,
            "contractExcluded": True,
            "paymentModes": ["qr", "credit_card", "debit_card"],
            "uniformNetworkTariffDeclaredByCpo": True,
            "energyGrossEurPerKwh": ENERGY_GROSS,
            "parkingGrossEurPer15Minutes": PARKING_GROSS,
            "parkingStartsAfterSeconds": PARKING_MIN_SECONDS,
            "parkingWindow": "MON-SAT 09:00-21:00",
            "exactNationalPartyMatch": PARTY,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized", type=Path, default=Path("data/national/netherlands_dotnl/normalized.json.gz"))
    parser.add_argument("--overlay", type=Path, default=Path("data/operator_direct/stellapower_nl_official_exact_overlay.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/netherlands/stellapower-direct-payg-integration-latest.json"))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--skip-live-check", action="store_true", help="local test only; use previously verified official source")
    args = parser.parse_args()

    generated = now()
    try:
        checks = {"sourceStatus": "previously_verified_official_source"} if args.skip_live_check else fetch_official_markers()
    except urllib.error.URLError as exc:
        if getattr(exc.reason, "errno", None) != errno.ENETUNREACH:
            raise
        report = {
            "schemaVersion": 1, "generatedAt": generated,
            "status": "official_source_network_unreachable",
            "partyId": PARTY, "source": SOURCE, "exactPricedConnectorCount": 0,
            "policy": "No StellaPower tariff promoted without current official source verification",
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
        return
    data = read_normalized(args.normalized)
    key, obj = tariff()
    matches = []
    for station in data.get("stations") or []:
        if station.get("partyId") != PARTY:
            continue
        for evse in station.get("evses") or []:
            for connector in evse.get("connectors") or []:
                if not args.no_write:
                    connector["tariffKeys"] = [key]
                    connector["tariffIds"] = []
                    connector["unresolvedTariffIds"] = []
                matches.append({
                    "stationId": station.get("stationId"),
                    "evseId": evse.get("uid") or evse.get("evseId"),
                    "connectorId": connector.get("id"),
                    "tariffKey": key,
                    "match": "exact_national_connector_with_cpo_declared_uniform_tariff",
                })

    if not matches:
        raise RuntimeError("No in-scope SPA connectors found")
    if not args.no_write:
        data.setdefault("tariffs", {})[key] = obj
        overlays = data.setdefault("source", {}).setdefault("directTariffOverlays", [])
        data["source"]["directTariffOverlays"] = [x for x in overlays if x.get("provider") != "StellaPower" or x.get("countryCode") != "NL"] + [{
            "provider": "StellaPower", "countryCode": "NL", "source": SOURCE,
            "sourceKind": "official_cpo_direct_payg_qr", "generatedAt": generated,
            "exactConnectorCount": len(matches), "uniformNetworkTariffDeclaredByCpo": True,
            "emspExcluded": True, "roamingExcluded": True,
        }]
        data["generatedAt"] = generated
        write_normalized(args.normalized, data)

    overlay = {
        "schemaVersion": 1, "dataset": "nl-stellapower-official-payg-exact-overlay",
        "generatedAt": generated, "country": "NL", "partyId": PARTY,
        "source": SOURCE, "officialChecks": checks, "tariffs": {key: obj},
        "matches": matches,
        "policy": {"officialCpoSource": True, "directPaygOnly": True, "uniformNetworkTariff": True,
                   "exactPartyId": PARTY, "exactNationalConnectorMatch": True,
                   "emspExcluded": True, "roamingExcluded": True, "contractExcluded": True},
    }
    args.overlay.parent.mkdir(parents=True, exist_ok=True)
    args.overlay.write_text(json.dumps(overlay, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    report = {
        "schemaVersion": 1, "generatedAt": generated, "status": "integrated" if not args.no_write else "candidate_only",
        "partyId": PARTY, "officialSources": checks, "exactPricedConnectorCount": len(matches),
        "tariffKey": key, "energyGrossEurPerKwh": ENERGY_GROSS,
        "parkingGrossEurPer15Minutes": PARKING_GROSS, "parkingStartsAfterSeconds": PARKING_MIN_SECONDS,
        "parkingWindow": "MON-SAT 09:00-21:00", "overlaySha256": hashlib.sha256(args.overlay.read_bytes()).hexdigest(),
        "guardrails": ["CPO-owned official source", "Direct QR/card PAYG only", "Exact national party/connector scope", "No eMSP or roaming", "Uniform tariff explicitly declared by CPO"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "partyId", "exactPricedConnectorCount", "energyGrossEurPerKwh", "parkingGrossEurPer15Minutes")}, indent=2))


if __name__ == "__main__":
    main()
