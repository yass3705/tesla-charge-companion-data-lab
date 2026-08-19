#!/usr/bin/env python3
"""Extract Plug Inn fast charge France rules from current official Renault sources."""
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
    "fastCharge": "https://www.renault.fr/solutions-de-recharge/plug-inn-fast-charge.html",
    "chargePass": "https://www.renault.fr/solutions-de-recharge/charge-pass.html",
    "rename": "https://media.renaultgroup.com/?p=256599",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return int(getattr(resp, "status", 200)), raw.decode(charset, errors="replace")


def text_from_html(raw: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def price_present(text: str, value: float) -> bool:
    whole, frac = f"{value:.2f}".split(".")
    return bool(re.search(rf"(?<!\d){whole}[,.]{frac}(?!\d)\s*€?\s*/?\s*kwh", norm(text)))


def money_per_month_present(text: str, value: float) -> bool:
    whole, frac = f"{value:.2f}".split(".")
    return bool(re.search(rf"(?<!\d){whole}[,.]{frac}(?!\d)\s*€?\s*/\s*mois", norm(text)))


def require(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: official evidence missing")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/pluginn")
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

    fast = norm(texts["fastCharge"])
    cp = norm(texts["chargePass"])
    rename = norm(texts["rename"])

    for value, label in ((0.59, "bank-card direct"), (0.46, "Charge Pass Basic"), (0.39, "Charge Pass Intense")):
        if not price_present(fast, value):
            raise RuntimeError(f"Plug Inn {label} {value:.2f} EUR/kWh evidence missing")

    require(fast, ("via carte bancaire", "carte bancaire"), "bank-card direct payment")
    require(fast, ("charge pass - basic", "charge pass basic"), "Charge Pass Basic")
    require(fast, ("charge pass - intense", "charge pass intense"), "Charge Pass Intense")
    require(fast, ("jusqu'a 320 kw", "320 kw"), "published maximum power")
    require(fast, ("ouvert 24/7", "24/7"), "24/7 network access")
    require(fast, ("tous les vehicules electriques", "tous les usagers de vehicules electriques"), "all-brand access")
    require(fast, ("0,30€/min", "0,30 €/min", "0.30€/min", "0.30 €/min"), "overstay fee amount")
    require(fast, ("au-dela d'1 heure", "au dela d'1 heure", "au-delà d’1 heure"), "overstay threshold")

    if not money_per_month_present(cp, 5.99):
        raise RuntimeError("Charge Pass Intense 5.99 EUR/month evidence missing")
    require(cp, ("formule basic",), "Charge Pass Basic product")
    require(cp, ("gratuit",), "Charge Pass Basic free subscription")
    require(cp, ("sans engagement",), "Charge Pass Intense no commitment")
    promo_199 = money_per_month_present(cp, 1.99) and bool(re.search(r"6\s+mois", cp))
    require(rename, ("mobilize fast charge devient plug inn fast charge", "reseau mobilize fast charge devient plug inn fast charge"), "2026 network rename")
    require(rename, ("avril",), "rename effective month")

    facts = {
        "classification": {
            "cpoNetwork": "Plug Inn fast charge",
            "formerName": "Mobilize Fast Charge",
            "renamedInFrance": "2026-04",
            "singleNationalBankCardDirectTariff": True,
            "chargePassIsMobilityServiceLayer": True,
            "thirdPartyPassTariffCanDiffer": True,
        },
        "operatorDirect": {
            "bankCard": {
                "eurPerKwh": 0.59,
                "subscriptionRequired": False,
                "geography": "France",
            },
            "network": {
                "maxPowerKwPublished": 320,
                "open247": True,
                "allVehicleBrands": True,
                "highPowerConnector": "CCS2",
            },
        },
        "mobilityService": {
            "product": "Charge Pass",
            "classification": "same_group_eMSP_member_pricing",
            "mustRemainSeparateFromPublicBankCardCpoTariff": True,
            "basic": {
                "monthlyFeeEur": 0.0,
                "plugInnEurPerKwh": 0.46,
            },
            "intense": {
                "monthlyFeeEur": 5.99,
                "commitment": "none",
                "plugInnEurPerKwh": 0.39,
                "temporaryPromo": {
                    "eurPerMonth": 1.99 if promo_199 else None,
                    "durationMonths": 6 if promo_199 else None,
                    "observedOnCurrentOfficialPage": promo_199,
                    "mustNotReplaceRecurringFee": True,
                },
            },
        },
        "roaming": {
            "classification": "third_party_eMSP",
            "operatorDirect": False,
            "exactTariffSource": "third-party mobility app/pass",
            "examplesPublishedByOperator": [
                "Chargemap Pass", "Fulli", "Ulys", "Freshmile", "IZIVIA", "Plugsurfing", "Total Charge"
            ],
        },
        "fees": {
            "overstayOrParkingDuration": {
                "thresholdMinutes": 60,
                "eurPerMinuteAfterThreshold": 0.30,
                "wording": "stationnement beyond one hour",
                "appliesToPublishedPlugInnTariffs": True,
                "doNotModelAsChargeEndedOnly": True,
            },
            "bankCardPreauthorization": {
                "status": "amount_not_stated_on_current_fast_charge_page",
                "amountEur": None,
            },
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "pluginn-fastcharge-official-france",
        "generatedAt": now_iso(),
        "operator": "Plug Inn fast charge",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "The public CPO bank-card tariff is kept separate from Charge Pass mobility-service/member prices.",
            "The 0.30 EUR/min fee is described as applying beyond one hour of parking/stationnement; it is not modeled as charge-ended-only.",
            "Third-party passes remain eMSP roaming and their prices must be resolved in the relevant app.",
            "Mobilize Fast Charge is retained only as the former network name for matching legacy station records.",
        ],
    }

    (out / "pluginn_fastcharge_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Plug Inn fast charge France official check\n\n"
        "- Former name: **Mobilize Fast Charge**; renamed **Plug Inn fast charge** in April 2026.\n"
        "- Public direct bank-card tariff: **0.59 EUR/kWh**.\n"
        "- Charge Pass BASIC: **0.46 EUR/kWh**, no monthly fee.\n"
        "- Charge Pass INTENSE: **0.39 EUR/kWh + 5.99 EUR/month**, no commitment.\n"
        f"- Current 1.99 EUR/month x 6 months promo observed: **{promo_199}**.\n"
        "- Parking/overstay: **0.30 EUR/min after 60 min**.\n"
        "- Published power: **up to 320 kW**, network open 24/7 and all brands.\n"
        "- Third-party passes: **eMSP pricing kept separate**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
