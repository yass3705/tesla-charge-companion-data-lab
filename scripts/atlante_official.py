#!/usr/bin/env python3
"""Extract Atlante France tariff/subscription rules from official public sources."""
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
    "app": "https://atlante.energy/fr/myatlante-app/",
    "drivers": "https://atlante.energy/fr/conducteurs/",
    "home": "https://atlante.energy/fr/",
    "goPress": "https://atlante.energy/fr/pressrelease/atlante-lance-atlante-go-son-offre-dabonnement/",
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
    s = s.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def require_any(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: expected official evidence not found")


def has_price(text: str, value: float) -> bool:
    whole, frac = f"{value:.2f}".split(".")
    return bool(re.search(rf"(?<!\d){whole}[,.]{frac}(?!\d)\s*€?\s*/?\s*kwh", norm(text), flags=re.I))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/atlante")
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

    app = norm(texts["app"])
    drivers = norm(texts["drivers"])
    home = norm(texts["home"])
    press = norm(texts["goPress"])

    # Current Atlante Go France tariff grid.
    for price in (0.29, 0.42, 0.49):
        if not has_price(app, price):
            raise RuntimeError(f"Atlante Go current France price {price:.2f} EUR/kWh not found")
    require_any(app, ("stations atlante : 0,29", "stations atlante: 0,29"), "Atlante Go France Atlante tier")
    require_any(app, ("stations powerdot: 0,42", "powerdot 0,42", "powerdot: 0,42"), "Atlante Go France Powerdot tier")
    require_any(app, ("stations chargeleague : 0,49", "chargeleague 0,49", "chargeleague : 0,49"), "Atlante Go France ChargeLeague tier")
    require_any(app, ("electra, fastned et ionity", "electra, fastned, ionity"), "ChargeLeague operator membership")
    require_any(app, ("9,99 €/mois", "9,99€/mois", "9.99 €/mois"), "Atlante Go monthly fee")
    require_any(app, ("sans engagement", "resilier a tout moment", "résilier à tout moment"), "Atlante Go no commitment")
    require_any(app, ("reserve uniquement aux particuliers", "réservé uniquement aux particuliers", "clients particuliers"), "Atlante Go private-customer restriction")

    # No-Go direct pricing is explicitly station/charger specific.
    require_any(
        app,
        (
            "le prix de la recharge varie selon le pays et la borne choisie",
            "les prix de recharge varient selon le pays et le chargeur",
        ),
        "Atlante non-subscription station-specific pricing",
    )
    require_any(app, ("consultez l'application myatlante", "consultez l’application myatlante"), "Atlante exact station price in app")

    # Loyalty / ChargeBack is distinct from the energy tariff.
    require_any(app, ("chez atlante, vous cagnottez 50 %", "50 % de cagnottage"), "Atlante ChargeBack 50 percent")
    require_any(app, ("powerdot et chargeleague",), "Atlante partner ChargeBack scope")
    require_any(app, ("10 % de cagnottage", "10% de cagnottage"), "Atlante partner ChargeBack 10 percent")
    require_any(app, ("credit a disposition que dans les stations atlante et powerdot", "crédit à disposition que dans les stations atlante et powerdot"), "ChargeBack redemption scope")

    # Direct vs eMSP/roaming payment routes.
    require_any(drivers, ("application myatlante",), "myAtlante direct app")
    require_any(drivers, ("carte rfid atlante",), "Atlante RFID direct")
    require_any(drivers, ("applications de mobilite (emsp)", "applications de mobilité (emsp)"), "Atlante eMSP roaming")
    require_any(drivers, ("surcout applique par l'operateur de mobilite", "surcoût appliqué par l’opérateur de mobilité"), "Atlante eMSP surcharge separation")
    require_any(drivers, ("carte de credit", "carte de crédit"), "Atlante bank-card availability")
    require_any(home, ("jusqu'a 400 kw", "jusqu’à 400 kw", "400 kw"), "Atlante published max power")

    # App payment-method limitations are current official facts, useful for UX.
    require_any(app, ("mastercard, visa, maestro",), "myAtlante accepted cards")
    require_any(app, ("american express",), "myAtlante Amex statement")
    require_any(app, ("apple pay",), "myAtlante Apple Pay statement")

    # Temporary first-month-free promotion is separate from the recurring fee.
    promo_first_month_free = (
        ("31 aout" in app or "31 août" in texts["app"].lower())
        and "1er mois gratuit" in app
    )

    facts = {
        "classification": {
            "singleGuaranteedNationalDirectTariffWithoutSubscription": False,
            "stationLevelPriceLookupRequiredWithoutSubscription": True,
            "atlanteGoHasNationalFranceTariff": True,
            "partnerNetworksInAtlanteGoAreMobilityServicePricing": True,
        },
        "operatorDirect": {
            "withoutAtlanteGo": {
                "priceModel": "station_specific",
                "exactPriceSource": "myAtlante selected charger",
                "singleNationalPrice": None,
            },
            "atlanteGo": {
                "monthlyFeeEur": 9.99,
                "commitment": "none",
                "eligibleCustomerType": "private_individuals",
                "france": {
                    "atlanteEurPerKwh": 0.29,
                    "powerdotEurPerKwh": 0.42,
                    "chargeLeagueEurPerKwh": 0.49,
                    "chargeLeagueOperators": ["Electra", "Fastned", "IONITY"],
                },
                "promotion": {
                    "firstMonthFreeObserved": promo_first_month_free,
                    "subscriptionDeadlineLocal": "2026-08-31T23:59:00" if promo_first_month_free else None,
                    "mustNotReplaceRecurringMonthlyFee": True,
                },
            },
            "paymentMethods": {
                "myAtlanteApp": True,
                "atlanteRfid": True,
                "bankCardAtSomeStations": True,
                "appAcceptedCards": ["Mastercard", "Visa", "Maestro"],
                "appCurrentlyNotAccepted": ["American Express", "PayPal", "Google Pay", "Apple Pay"],
            },
            "publishedMaxPowerKw": 400,
        },
        "loyalty": {
            "program": "ChargeBack / Green Gems",
            "atlanteEarnRatePercentOfSpend": 50,
            "powerdotAndChargeLeagueEarnRatePercentOfSpend": 10,
            "creditRedeemableOn": ["Atlante", "Powerdot"],
            "mustNotBeNetterIntoBaseEnergyTariff": True,
        },
        "roaming": {
            "classification": "third_party_eMSP",
            "operatorDirect": False,
            "emspPriceCanDiffer": True,
            "emspSurchargeExplicitlyStated": True,
            "examplesFrance": ["Chargemap", "Bump", "Ulys", "Freshmile", "Shell Recharge", "Elli", "ChargePoint"],
        },
        "fees": {
            "idleOrOccupation": {
                "status": "not_stated_network_wide_on_current_official_pages",
                "networkWideAmount": None,
                "stationSpecificRulesMayStillExist": True,
            },
            "parking": {
                "status": "site_specific_not_asserted_network_wide",
            },
            "bankCardPreauthorization": {
                "status": "not_stated_network_wide_on_current_official_pages",
                "amountEur": None,
            },
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "atlante-official-france",
        "generatedAt": now_iso(),
        "operator": "Atlante",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Without Atlante Go, exact direct pricing is station/charger-specific and must be resolved in myAtlante.",
            "Atlante Go partner-network prices are a myAtlante mobility-service offer and must not overwrite each CPO's own direct tariff.",
            "ChargeBack/Green Gems are loyalty credits and must remain separate from the base energy tariff in simulations.",
            "No network-wide idle, parking or bank-card preauthorization amount is asserted without current official evidence.",
        ],
    }
    (out / "atlante_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Atlante France official check\n\n"
        "- Without Atlante Go: **station-specific direct pricing**, exact price in myAtlante.\n"
        "- Atlante Go: **9.99 EUR/month**, no commitment, private customers only.\n"
        "- France with Atlante Go: **Atlante 0.29 / Powerdot 0.42 / ChargeLeague 0.49 EUR/kWh**.\n"
        "- ChargeLeague in this offer: **Electra / Fastned / IONITY**.\n"
        "- ChargeBack: **50% earn at Atlante; 10% at Powerdot/ChargeLeague**; redeem on Atlante/Powerdot.\n"
        "- Third-party eMSP tariffs remain separate and can include an eMSP surcharge.\n"
        "- Network-wide idle/parking/preauthorization fee: **not asserted** from current official pages.\n"
        f"- First-month-free promotion observed: **{promo_first_month_free}**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
