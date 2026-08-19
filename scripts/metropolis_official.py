#!/usr/bin/env python3
"""Extract current Métropolis Recharge tariff rules from official public sources."""
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
    "home": "https://www.metropolis-recharge.fr/",
    "faq": "https://www.metropolis-recharge.fr/faq/",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_text(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, errors="replace")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return int(getattr(resp, "status", 200)), re.sub(r"\s+", " ", html.unescape(text)).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def numeric_tokens(text: str) -> list[float]:
    values: list[float] = []
    for m in re.finditer(r"(?<!\d)(\d+(?:[,.]\d+)?)(?!\d)", norm(text)):
        try:
            values.append(float(m.group(1).replace(",", ".")))
        except ValueError:
            pass
    return values


def has_value(text: str, value: float, tol: float = 0.0005) -> bool:
    return any(abs(x - value) <= tol for x in numeric_tokens(text))


def require(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: expected official evidence not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/metropolis")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    statuses: dict[str, int] = {}
    texts: dict[str, str] = {}
    for key, url in SOURCES.items():
        status, text = fetch_text(url)
        statuses[key] = status
        texts[key] = text
        if status != 200:
            raise RuntimeError(f"Métropolis source {key}: HTTP {status}")

    home = texts["home"]
    faq = texts["faq"]

    # Public charging prices and power classes.
    for value in (0.44, 0.53, 0.63, 3.7, 22.0, 180.0):
        if not has_value(home, value):
            raise RuntimeError(f"Métropolis current public tariff/power value {value} missing")
    require(home, ("tarification post charge apres 10min sans charge", "tarification post charge après 10min sans charge"), "Métropolis post-charge trigger")
    require(faq, ("0,53 € ttc / kwh (au lieu de 0,63 €)", "0,53 € ttc/kwh"), "Métropolis Express kWh unit and monthly discount")

    # Post-charge rates and local exceptions.
    for value in (0.10, 0.20):
        if not has_value(home, value):
            raise RuntimeError(f"Métropolis post-charge value {value} missing")
    require(home, ("neuilly-sur-seine",), "Métropolis Neuilly exception")
    require(home, ("journee de 8h a 20h", "journée de 8h à 20h"), "Métropolis Neuilly daytime window")
    require(home, ("la nuit de 20h a 8h", "la nuit de 20h à 8h"), "Métropolis Neuilly nighttime window")
    require(home, ("bornes 22 kw situees sur les stations ultra-rapides express", "bornes 22 kw situées sur les stations ultra-rapides express"), "Métropolis Express-site 22 kW exception")

    # Membership layer.
    require(faq, ("10€ par an", "10 € par an"), "Métropolis Liberté annual fee")
    require(faq, ("9,90€ par mois", "9,90 € par mois"), "Métropolis Mensuel monthly fee")
    require(faq, ("2 heures de post charge offert par mois", "2 heures de post charge offertes par mois"), "Métropolis monthly free post-charge allowance")
    require(faq, ("2€ par nuit de post charge", "2 € par nuit de post charge"), "Métropolis night post-charge forfait")
    require(faq, ("entre 20h et 8h",), "Métropolis night post-charge window")
    require(faq, ("hors station express", "hors stations express"), "Métropolis night forfait Express exclusion")

    # Payments, preauthorization and roaming separation.
    require(faq, ("pre-autorisation bancaire de 49€", "pré-autorisation bancaire de 49€", "49 euros"), "Métropolis card preauthorization")
    require(faq, ("apple pay",), "Métropolis Apple Pay")
    require(faq, ("google pay",), "Métropolis Google Pay")
    require(faq, ("qr code",), "Métropolis QR payment")
    require(faq, ("badge abonne metropolis recharge ou d'autres operateurs", "badge abonné métropolis recharge ou d’autres opérateurs"), "Métropolis RFID and roaming badges")
    require(faq, ("l'operateur a la liberte d'appliquer des frais", "l’opérateur a la liberté d’appliquer des frais"), "Métropolis third-party eMSP pricing")
    require(faq, ("badge metropolis ne permet pas", "badge métropolis ne permet pas"), "Métropolis outgoing roaming disabled")

    facts = {
        "classification": {
            "network": "Métropolis Recharge",
            "localPublicNetwork": True,
            "geography": "Métropole du Grand Paris and participating nearby communes",
            "singleFlatPublicTariff": False,
            "tariffDependsOnSelectedOrDeliveredPower": True,
            "postChargeRulesHaveLocalExceptions": True,
        },
        "operatorDirect": {
            "publicNoSubscription": {
                "proximityUpTo3_7Kw": {"eurPerKwh": 0.44},
                "cityAbove3_7To22_25Kw": {"eurPerKwh": 0.53},
                "express150To180Kw": {"eurPerKwh": 0.63},
            },
            "subscriptions": {
                "liberte": {
                    "feeEurPerYear": 10.0,
                    "energyTariff": "public_tariff",
                    "reservationAvailable": True,
                    "reservationLeadMinutes": 30,
                    "freePostChargeHoursPerMonth": 2,
                    "nightPostChargeForfaitEur": 2.0,
                    "nightWindow": "20:00-08:00",
                    "nightForfaitExcludesExpress": True,
                },
                "mensuel": {
                    "feeEurPerMonth": 9.90,
                    "expressEurPerKwh": 0.53,
                    "otherEnergyTariffs": "public_tariff",
                    "includesLiberteBenefits": True,
                    "freePostChargeHoursPerMonth": 2,
                    "nightPostChargeForfaitEur": 2.0,
                    "nightWindow": "20:00-08:00",
                    "nightForfaitExcludesExpress": True,
                },
            },
            "paymentMethods": [
                "contactless bank card",
                "Apple Pay",
                "Google Pay",
                "bank card via web/app/QR",
                "Métropolis RFID badge",
            ],
            "bankCardPreauthorizationEur": 49.0,
        },
        "fees": {
            "postCharge": {
                "trigger": "after_10_minutes_without_charging_while_vehicle_remains_on_space",
                "graceMinutes": 10,
                "default": {
                    "proximityUpTo3_7KwEurPerMinute": 0.10,
                    "cityAbove3_7To22_25KwEurPerMinute": 0.10,
                    "express150To180KwEurPerMinute": 0.20,
                },
                "exceptions": {
                    "neuillySurSeine": {
                        "day0800To2000EurPerMinute": 0.20,
                        "night2000To0800EurPerMinute": 0.10,
                    },
                    "22KwOnExpressSitesEurPerMinute": 0.20,
                },
                "subscriptionBenefitsMustBeAppliedSeparately": True,
            }
        },
        "roaming": {
            "incomingThirdPartyBadge": {
                "classification": "third_party_eMSP",
                "operatorDirect": False,
                "thirdPartyProviderMayAddFees": True,
                "mustNotOverwriteMétropolisDirectTariff": True,
            },
            "outgoingMétropolisBadge": {
                "usableOnOtherNetworksCurrentOfficialFaq": False,
                "gireveMembershipMentioned": True,
            },
        },
        "network": {
            "publishedChargerClasses": {
                "proximityMaxKw": 7.4,
                "cityMaxKw": 22,
                "expressMaxKw": 180,
            },
            "exactStationSource": "Métropolis Recharge map/app",
        },
    }

    fingerprint = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "metropolis-official-grand-paris",
        "generatedAt": now_iso(),
        "operator": "Métropolis Recharge",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Energy charging is billed per kWh; time billing is modeled only as post-charge occupation after 10 minutes without charging.",
            "The tariff table currently prints 0.63 €/kW on the Express row, but the official FAQ explicitly states 0.63 €/kWh; the dataset uses the FAQ-disambiguated energy unit.",
            "Neuilly-sur-Seine and 22 kW connectors located on Express stations have explicit post-charge exceptions.",
            "Third-party interoperability badges remain eMSP pricing and may add fees; the Métropolis badge itself is not currently usable on other networks according to the official FAQ.",
        ],
    }

    (out / "metropolis_official_grand_paris.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# Métropolis Recharge official check\n\n"
        "- Public energy: **0.44 / 0.53 / 0.63 EUR/kWh** by power class.\n"
        "- Post-charge: **after 10 min without charge**, default **0.10 / 0.10 / 0.20 EUR/min**.\n"
        "- Neuilly-sur-Seine: **0.20 EUR/min 08:00-20:00; 0.10 EUR/min 20:00-08:00**.\n"
        "- 22 kW connectors on Express sites: **0.20 EUR/min post-charge**.\n"
        "- Liberté: **10 EUR/year**, 2 free post-charge hours/month, **2 EUR/night 20:00-08:00**, excluding Express.\n"
        "- Mensuel: **9.90 EUR/month**, Express **0.53 EUR/kWh**, plus Liberté benefits.\n"
        "- Contactless bank-card preauthorization: **49 EUR**.\n"
        "- Third-party RFID pricing remains **eMSP/roaming**, separate from Métropolis direct pricing.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
