#!/usr/bin/env python3
"""Extract Zunder France tariff rules from current official public sources."""
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
    "drivers": "https://www.zunder.com/fr/utilisateur-ve/",
    "subscriptions": "https://www.zunder.com/fr/suscripciones/",
    "leasingSocial": "https://www.zunder.com/fr/leasing-social",
    "leasingTerms": "https://www.zunder.com/_landings/leasing-social/Conditions_Legales_Club_Social_Leasing_13042026.html",
    "payment": "https://www.zunder.com/fr/faqs/comment-puis-je-payer-pour-un-chargement-sur-zunder/",
    "activation": "https://www.zunder.com/fr/faqs/comment-activer-une-charge-sur-zunder/",
    "dynamic": "https://www.zunder.com/fr/zunder-deploie-de-nouveaux-tarifs-dynamiques-dans-laube-et-les-vosges/",
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


def has_price(text: str, value: float) -> bool:
    whole, frac = f"{value:.3f}".split(".")
    frac = frac.rstrip("0")
    return bool(re.search(rf"(?<!\d){whole}[,.]{frac}(?!\d)\s*€?\s*/?\s*kwh", norm(text), flags=re.I))


def require(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: expected official evidence not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/zunder")
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

    drivers = norm(texts["drivers"])
    subs = norm(texts["subscriptions"])
    leasing = norm(texts["leasingSocial"])
    leasing_terms = norm(texts["leasingTerms"])
    payment = norm(texts["payment"])
    activation = norm(texts["activation"])
    dynamic = norm(texts["dynamic"])

    # Current France public/reference grid.
    for value in (0.42, 0.59, 0.33, 0.578, 0.595, 0.44, 0.40, 0.564, 0.32, 0.57):
        if not has_price(drivers, value):
            raise RuntimeError(f"Zunder France current public/reference price {value} EUR/kWh missing")
    require(drivers, ("troyes",), "Zunder Troyes dynamic tariff")
    require(drivers, ("charmes",), "Zunder Charmes dynamic tariff")
    require(drivers, ("prix exact de chaque point s'affiche toujours dans l'app",), "Zunder exact station price source")

    # Subscription layer.
    for value in (0.51, 0.39):
        if not has_price(subs, value):
            raise RuntimeError(f"Zunder subscription price {value} EUR/kWh missing")
    require(subs, ("1,99 €/mois", "1,99€/mois"), "Zunder Easy monthly fee")
    require(subs, ("11,99 €/mois", "11,99€/mois"), "Zunder Pro monthly fee")
    require(subs, ("1%",), "Zunder no-plan credit")
    require(subs, ("3%",), "Zunder Easy credit")
    require(subs, ("5%",), "Zunder Pro credit")
    require(subs, ("sans engagement",), "Zunder no commitment")

    # Roaming layer: Zunder as eMSP on third-party CPOs.
    require(drivers, ("0,99 €/session", "0,99€/session"), "Zunder roaming service fee")
    require(drivers, ("prix fixe par l'operateur du point", "prix fixé par l’opérateur du point", "prix fixe par l'operateur"), "Zunder roaming CPO component")

    # Social leasing special eligibility-limited offer.
    if not has_price(leasing_terms, 0.39) or not has_price(leasing_terms, 0.45):
        raise RuntimeError("Zunder Social Leasing power-band prices missing")
    require(leasing_terms, ("31 decembre 2026", "31/12/2026"), "Zunder Social Leasing deadline")
    require(leasing, ("leasing social",), "Zunder Social Leasing program")

    # Payment methods and card prepayment model.
    require(activation, ("tpe", "terminal"), "Zunder payment terminal")
    require(activation, ("pass rfid",), "Zunder RFID")
    require(activation, ("plug & charge", "plug&charge", "autocharge"), "Zunder Plug&Charge")
    require(payment, ("montant que vous indiquez",), "Zunder card prepayment user-chosen amount")

    # Dynamic tariff proof for current France exceptions.
    if not has_price(dynamic, 0.49) or not has_price(dynamic, 0.40):
        raise RuntimeError("Zunder Troyes current dynamic tariff evidence missing")
    require(dynamic, ("8h et 18h",), "Zunder Troyes daytime window")
    require(dynamic, ("18h et 8h",), "Zunder Troyes off-peak window")

    facts = {
        "classification": {
            "singleFlatNationalPublicTariff": False,
            "stationLevelPriceLookupRequiredForExactPublicPrice": True,
            "subscriptionPricesApplyAcrossZunderFrance": True,
            "specialConcessionAndDynamicTariffsExist": True,
        },
        "operatorDirect": {
            "franceReferencePublic": {
                "upTo50KwEurPerKwh": 0.42,
                "above50KwEurPerKwh": 0.59,
                "exactPriceSource": "Zunder app selected charging point",
            },
            "specialFranceGrids": {
                "alicorne": {"acEurPerKwh": 0.33, "upTo150KwEurPerKwh": 0.578, "above150KwEurPerKwh": 0.595},
                "vinci": {"acEurPerKwh": 0.44, "upTo150KwEurPerKwh": 0.44, "above150KwEurPerKwh": 0.59},
                "a63": {"acEurPerKwh": 0.40, "upTo150KwEurPerKwh": 0.40, "above150KwEurPerKwh": 0.564},
                "risle": {"upTo50KwEurPerKwh": 0.32, "above50KwEurPerKwh": 0.57},
                "troyes": {"dynamicRangeEurPerKwh": [0.40, 0.49], "day0800To1800EurPerKwh": 0.49, "night1800To0800EurPerKwh": 0.40},
                "charmes": {"dynamicRangeEurPerKwh": [0.35, 0.49]},
            },
            "subscriptions": {
                "none": {"monthlyFeeEur": 0.0, "creditPercent": 1},
                "easy": {"monthlyFeeEur": 1.99, "eurPerKwh": 0.51, "creditPercent": 3, "commitment": "none"},
                "pro": {"monthlyFeeEur": 11.99, "eurPerKwh": 0.39, "creditPercent": 5, "commitment": "none"},
            },
            "paymentMethods": ["Zunder app", "TPE bank card", "Zunder RFID/eZCard", "Plug&Charge/Autocharge"],
            "bankCardPrepayment": {"fixedNetworkWideAmountEur": None, "model": "user_selects_prepaid_amount_then_unused_balance_refunded"},
        },
        "specialPrograms": {
            "socialLeasing2026": {
                "generalPublicTariff": False,
                "eligibilityLimited": True,
                "upTo50KwEurPerKwh": 0.39,
                "above50KwEurPerKwh": 0.45,
                "validUntil": "2026-12-31",
                "mustNotReplaceGeneralPublicTariff": True,
            }
        },
        "loyalty": {
            "classification": "future_charge_credit",
            "mustRemainSeparateFromBaseEnergyTariff": True,
            "noPlanPercent": 1,
            "easyPercent": 3,
            "proPercent": 5,
        },
        "roaming": {
            "classification": "Zunder_eMSP_on_third_party_CPO",
            "operatorDirect": False,
            "zunderServiceFeeEurPerSession": 0.99,
            "plusCpoPrice": True,
            "mustNotOverwriteThirdPartyCpoDirectTariff": True,
        },
        "fees": {
            "idleOrOccupation": {
                "status": "not_stated_network_wide_on_current_checked_official_pricing_pages",
                "networkWideAmount": None,
            },
            "parking": {"status": "site_specific_not_asserted_network_wide"},
        },
    }

    fingerprint = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "zunder-official-france",
        "generatedAt": now_iso(),
        "operator": "Zunder",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Zunder public France pricing is not represented as one national flat price because power, concession and location-specific tariffs exist.",
            "Easy/Pro subscription pricing and loyalty credit are kept separate from the public station grid.",
            "Social Leasing is eligibility-limited and must never be shown as a general-public default.",
            "When Zunder is used on another CPO through roaming, the 0.99 EUR/session eMSP fee is added to that CPO's price.",
            "No network-wide idle/occupation fee is asserted without current official evidence.",
        ],
    }

    (out / "zunder_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# Zunder France official check\n\n"
        "- Public reference: **<=50 kW 0.42 EUR/kWh; >50 kW 0.59 EUR/kWh**, with location/concession exceptions.\n"
        "- Easy: **0.51 EUR/kWh + 1.99 EUR/month + 3% credit**.\n"
        "- Pro: **0.39 EUR/kWh + 11.99 EUR/month + 5% credit**.\n"
        "- No plan: **1% future-charge credit**.\n"
        "- Social Leasing 2026: **<=50 kW 0.39; >50 kW 0.45 EUR/kWh**, eligibility-limited through 2026-12-31.\n"
        "- Roaming via Zunder on third-party CPO: **0.99 EUR/session + CPO price**.\n"
        "- Troyes dynamic public tariff: **0.49 EUR/kWh 08:00-18:00; 0.40 EUR/kWh 18:00-08:00**.\n"
        "- Network-wide idle/parking fee: **not asserted**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
