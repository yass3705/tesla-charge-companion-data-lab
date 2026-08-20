#!/usr/bin/env python3
"""Validate current Plenitude On The Road France public-charging rules.

Operator-rule validator only: no national station database is built. Consumer
Pay Per Use prices for Plenitude-owned charging points are kept separate from
third-party roaming prices and from B2B/wholesale interoperability tariffs.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

SOURCES = {
    "pricing": "https://eniplenitude.eu/e-mobility/pricing",
    "network": "https://eniplenitude.eu/e-mobility/charging-network",
    "travelPromo": "https://eniplenitude.eu/e-mobility/travel-on-the-road",
    "bilateral": "https://eniplenitude.eu/e-mobility/bilateral-agreement-pricing",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9,fr;q=0.7",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=40) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return int(getattr(resp, "status", 200)), raw.decode(charset, errors="replace")


def text_from_html(raw: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def require_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    n = norm(text)
    missing = [t for t in tokens if norm(t) not in n]
    if missing:
        raise RuntimeError(f"{label}: missing markers: {', '.join(missing)}")


def require_amount(text: str, amount: float, label: str) -> None:
    n = norm(text)
    forms = {f"{amount:.2f}", f"{amount:.2f}".replace(".", ",")}
    if not any(re.search(rf"(?<!\d){re.escape(v)}(?!\d)", n) for v in forms):
        raise RuntimeError(f"{label}: amount {amount:.2f} not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/plenitude")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pages = {}
    statuses = {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        pages[key] = norm(text_from_html(raw))

    pricing = pages["pricing"]
    require_tokens(pricing, ("pay per use", "charging cost in france", "quick", "fast", "ultra fast"), "Plenitude France consumer pricing")
    for amount in (0.45, 0.55):
        require_amount(pricing, amount, "Plenitude France consumer pricing")
    require_tokens(pricing, ("60 minutes free parking", "0.12", "0.20", "0.30", "23:00", "07:00"), "Plenitude blocking fees")
    require_tokens(pricing, ("other operators", "may be different", "app"), "Plenitude third-party pricing separation")

    network = pages["network"]
    require_tokens(network, ("plenitude charging points", "other operators", "interoperability", "600.000"), "Plenitude network separation")

    promo = pages["travelPromo"]
    require_tokens(promo, ("august26", "40%", "3 charging sessions", "france", "31st august 2026"), "Plenitude August 2026 promo")

    bilateral = pages["bilateral"]
    require_tokens(bilateral, ("bilateral agreement pricing scheme", "mobility service providers", "france", "vat"), "Plenitude B2B tariff separation")

    facts = {
        "classification": {
            "consumerDirectTariffPublishedForFranceByPowerClass": True,
            "singleFlatAllPowerNationalTariff": False,
            "stationLevelLookupRequiredForThirdPartyRoaming": True,
            "reason": "Plenitude publishes France Pay Per Use prices for its owned charging points by power class; third-party operator prices in the app may differ.",
        },
        "operatorDirect": {
            "payPerUseFranceOwnedNetwork": {
                "billingUnit": "kWh",
                "quickAcUpTo22KwEurPerKwh": 0.45,
                "fastDcUpTo75KwEurPerKwh": 0.55,
                "fastPlusUltraFastDcFrom75KwEurPerKwh": 0.55,
                "paymentMethods": ["Plenitude On The Road app", "RFID card"],
                "priceSource": "current consumer pricing page",
                "note": "The published class wording overlaps at exactly 75 kW (Fast up to 75; Fast+/UltraFast from 75); use the station/app class at that boundary.",
            },
        },
        "roaming": {
            "classification": "third_party_operator_points_available_in_plenitude_app",
            "operatorDirect": False,
            "exactPartnerTariffLookupRequired": True,
            "priceSetByPlenitudeForItsAppMayDifferFromOtherOperatorsOwnPayPerUse": True,
            "consumerPriceAuthority": "Plenitude On The Road app for selected third-party station",
        },
        "fees": {
            "blockingFee": {
                "graceMinutesAfterEndOfCharge": 60,
                "quickAcUpTo22Kw": {
                    "eurPerMin": 0.12,
                    "appliesBetween": "07:00-23:00",
                    "nightExemption": "23:00-07:00",
                },
                "fastDcUpTo75Kw": {
                    "eurPerMin": 0.20,
                    "applies": "24h",
                },
                "fastPlusUltraFastDcOver75Kw": {
                    "eurPerMin": 0.30,
                    "applies": "24h",
                },
                "boundary75Kw": "use station/app classification because published class wording overlaps at 75 kW",
            },
            "parkingOutsideChargingOperatorFee": {
                "status": "site_or_landowner_specific_check_required",
            },
        },
        "temporaryPromotions": {
            "AUGUST26": {
                "activeAsOfGeneratedDate": True,
                "discountPercent": 40.0,
                "maxChargingSessions": 3,
                "countries": ["FR", "AT", "CH"],
                "validThrough": "2026-08-31T23:59:00",
                "payPerUseOnly": True,
                "personal": True,
                "combinable": False,
                "defaultTariff": False,
            },
        },
        "b2bInteroperability": {
            "publishedBilateralPricingExists": True,
            "consumerTariff": False,
            "pricesExcludeVat": True,
            "note": "Bilateral OCPI/operator prices are MSP/CPO settlement terms and must not be used as the end-user Charge Companion tariff.",
        },
        "network": {
            "ownedAndManagedPointsSeparateFromOtherOperators": True,
            "appAccessiblePointsClaimedApprox": 600000,
            "nationalStationDatabaseBuiltByThisValidator": False,
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "plenitude-on-the-road-official-france",
        "generatedAt": now_iso(),
        "operator": "Plenitude On The Road",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "This validator intentionally does not build a national station database.",
            "Keep Plenitude-owned consumer Pay Per Use prices separate from third-party roaming prices shown in the app.",
            "Do not use bilateral wholesale prices as consumer tariffs.",
            "AUGUST26 is a temporary promotion and must not replace the normal tariff baseline.",
        ],
    }

    (out / "plenitude_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Plenitude On The Road France official check\n\n"
        "- Validation model: **operator rules only**, no national station extract.\n"
        "- Plenitude-owned Pay Per Use France: **0.45 EUR/kWh AC <=22 kW**, **0.55 EUR/kWh DC** (published Fast/Fast+/UltraFast classes).\n"
        "- Third-party stations in the app: **separate roaming layer**, exact price must be read in the app.\n"
        "- Blocking fee after **60 min grace**: AC **0.12 EUR/min** (except 23:00-07:00), Fast DC **0.20 EUR/min**, Fast+/UltraFast **0.30 EUR/min**.\n"
        "- Current temporary promo **AUGUST26**: **40% off up to 3 Pay Per Use sessions** in France/Austria/Switzerland through 31 Aug 2026; not a baseline tariff.\n"
        "- Bilateral OCPI/operator pricing is **B2B wholesale, not consumer pricing**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
