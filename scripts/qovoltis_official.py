#!/usr/bin/env python3
"""Validate current Qovoltis France public-charging tariff rules.

Model intentionally follows the operator-rule validators used for Powerdot/IZIVIA/Fastned:
- no national station database is built;
- exact CPO-direct price remains station/location specific when official terms say so;
- ad-hoc bank-card access is kept separate from account offers;
- partner roaming is kept separate from Qovoltis-direct pricing;
- historical tariff sheets are not promoted as current nationwide prices.
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
    "nomadTerms": "https://cdn.qovoltis.com/CGV_CP_VF.html",
    "adHoc": "https://chargenow.qovoltis.com/",
    "dataGouvOrg": "https://www.data.gouv.fr/organizations/qovoltis/datasets",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
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
    s = s.lower().replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def require_any(text: str, phrases: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(p) in n for p in phrases):
        raise RuntimeError(f"{label}: expected evidence not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/qovoltis")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    texts: dict[str, str] = {}
    statuses: dict[str, int] = {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        texts[key] = text_from_html(raw)

    terms = norm(texts["nomadTerms"])
    adhoc = norm(texts["adHoc"])
    datagouv = norm(texts["dataGouvOrg"])

    # Current published Nomad terms explicitly point exact Qovoltis and partner prices
    # to the application's Location page rather than defining one national tariff.
    require_any(
        terms,
        (
            "les tarifs au kwh des bornes de recharge qovoltis ouvertes au public sont disponibles sur la page « localisation » de l'application",
            "les tarifs au kwh des bornes de recharge qovoltis ouvertes au public sont disponibles sur la page \"localisation\" de l'application",
            "tarifs au kwh des bornes de recharge qovoltis ouvertes au public",
        ),
        "Qovoltis direct station pricing",
    )
    require_any(
        terms,
        (
            "conditions tarifaires d'utilisation des bornes de recharge partenaire",
            "bornes de recharge partenaire",
            "operateurs partenaires",
        ),
        "Qovoltis partner roaming",
    )
    require_any(terms, ("nomad open", "offre nomad open"), "Nomad Open")
    require_any(terms, ("nomad gold", "offre nomad gold"), "Nomad Gold")
    require_any(
        terms,
        ("sans frais d'acces", "sans frais d’accès"),
        "Nomad Gold no-access-fee rule",
    )

    # Public no-account card flow.
    require_any(
        adhoc,
        ("je recharge par carte bancaire sans compte qovoltis", "carte bancaire sans compte qovoltis"),
        "Qovoltis ad-hoc card access",
    )

    # Official organisation publishes IRVE static datasets. These are inventory evidence only.
    require_any(datagouv, ("irve qovoltis", "irve statique"), "Qovoltis data.gouv inventory")
    if "qovoltis" not in datagouv:
        raise RuntimeError("Qovoltis data.gouv organisation marker missing")

    facts = {
        "classification": {
            "singleGuaranteedNationalCpoDirectTariff": False,
            "stationLevelPriceLookupRequiredForExactCpoDirect": True,
            "reason": "Current Qovoltis Nomad terms direct users to the application's Location page for the applicable Qovoltis-station kWh tariff.",
        },
        "operatorDirect": {
            "nomadOpen": {
                "available": True,
                "priceModel": "station_specific",
                "exactPriceLookupRequired": True,
                "nationalEurPerKwh": None,
                "currentAccessFeeEur": None,
                "currentAccessFeeStatus": "not_asserted_from_current_terms_without_current_tariff_grid",
            },
            "nomadGold": {
                "available": True,
                "subscriptionTier": True,
                "monthlyFeeEur": None,
                "monthlyFeeStatus": "not_asserted_from_current_terms_without_current_tariff_grid",
                "accessFeeOnQovoltisNetworkEur": 0.0,
                "priceModel": "station_specific_kwh_tariff",
                "exactPriceLookupRequired": True,
            },
            "adHocBankCard": {
                "available": True,
                "accountRequired": False,
                "priceModel": "station_specific",
                "exactPriceLookupRequired": True,
            },
        },
        "roaming": {
            "classification": "partner_network_eMSP_layer",
            "operatorDirect": False,
            "partnerStationsSupported": True,
            "exactPartnerTariffLookupRequired": True,
            "priceDisplayLocation": "Qovoltis application Location page",
        },
        "fees": {
            "networkWideIdleOrDurationFee": None,
            "networkWideIdleFeeStatus": "not_asserted_from_current_general_terms",
            "durationMayAppearAsInvoiceComponent": True,
            "parking": {
                "status": "site_or_landowner_specific_check_required",
            },
        },
        "inventory": {
            "officialDataGouvOrganisation": True,
            "staticInventoryOnly": True,
            "liveAvailability": False,
            "note": "Qovoltis publishes official IRVE static datasets on data.gouv.fr; these are not used as a national station database in this validator.",
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "qovoltis-official-france",
        "generatedAt": now_iso(),
        "operator": "Qovoltis",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [
                {"key": key, "url": url, "httpStatus": statuses[key]}
                for key, url in SOURCES.items()
            ],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "This validator intentionally does not build a national station database.",
            "Do not promote historical Nomad tariff-grid amounts as current nationwide prices without a current official tariff grid.",
            "Exact Qovoltis-direct and partner-network prices must be resolved at station/location level in the Qovoltis app.",
            "Ad-hoc bank-card charging without a Qovoltis account is currently exposed by the official ChargeNow flow.",
        ],
    }

    (out / "qovoltis_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Qovoltis France official check\n\n"
        "- Validation model: **operator rules only** (Powerdot/IZIVIA/Fastned style), no national station extract.\n"
        "- One guaranteed France-wide CPO-direct tariff: **no**; exact Qovoltis price is station/location specific in the app.\n"
        "- Nomad Open: **station-specific price**, current access fee not asserted without a current tariff grid.\n"
        "- Nomad Gold: **subscription tier exists**, **no access fee on Qovoltis network**, exact kWh price remains station specific.\n"
        "- Ad-hoc: **bank card without Qovoltis account supported**.\n"
        "- Partner roaming: **separate eMSP/partner layer**, exact tariff shown in the Qovoltis app.\n"
        "- Network-wide idle fee: **not asserted** from current general terms; parking remains site/landowner specific.\n"
        "- Official data.gouv IRVE datasets: **inventory evidence only**, not live availability and not promoted to a national station base.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
