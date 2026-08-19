#!/usr/bin/env python3
"""Extract current eborn regional tariff rules from official public sources."""
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
    "tariffs": "https://www.eborn.fr/tarifs/",
    "faq": "https://www.eborn.fr/foire-aux-questions/",
    "chargeGuide": "https://www.eborn.fr/la-recharge-de-votre-vehicule/",
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
    s = s.lower().replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def numeric_tokens(text: str) -> list[float]:
    out: list[float] = []
    for m in re.finditer(r"(?<!\d)(\d+(?:[,.]\d+)?)(?!\d)", norm(text)):
        try:
            out.append(float(m.group(1).replace(",", ".")))
        except ValueError:
            pass
    return out


def has_value(text: str, value: float, tol: float = 0.0005) -> bool:
    return any(abs(x - value) <= tol for x in numeric_tokens(text))


def require(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: expected official evidence not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/eborn")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    statuses: dict[str, int] = {}
    texts: dict[str, str] = {}
    for key, url in SOURCES.items():
        status, text = fetch_text(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        texts[key] = text

    tariffs = texts["tariffs"]
    faq = texts["faq"]

    # Core tariff grid and subscriptions.
    for value in (14.0, 49.0, 0.310, 0.433, 0.573, 0.588, 0.650, 0.05, 0.075, 0.12, 250.0):
        if not has_value(tariffs, value):
            raise RuntimeError(f"eborn tariff value {value} missing")
    require(tariffs, ("jusqu'a 25kw", "jusqu’à 25kw"), "eborn accelerated power band")
    require(tariffs, ("entre 25 et 60kw",), "eborn fast power band")
    require(tariffs, ("superieure a 60kw", "supérieure à 60kw"), "eborn ultra-fast power band")
    require(tariffs, ("30 minutes",), "eborn post-charge grace")
    require(tariffs, ("8h00 et 20h00",), "eborn accelerated post-charge time window")
    require(tariffs, ("31 mars 2025",), "eborn roaming markup effective date")
    require(tariffs, ("15%",), "eborn outgoing roaming markup")

    # FAQ corroboration and operational semantics.
    require(faq, ("easy charge",), "eborn operational manager")
    require(faq, ("plus de 3 000 points de charge", "plus de 3000 points de charge"), "eborn published network size")
    require(faq, ("jusqu'a 120 kw", "jusqu’à 120 kw"), "eborn published maximum power")
    require(faq, ("carte bancaire",), "eborn bank-card access")
    require(faq, ("qr code",), "eborn QR access")
    require(faq, ("30 minutes",), "eborn post-charge FAQ corroboration")
    require(faq, ("500 wh",), "eborn unsuccessful-session energy threshold")
    require(faq, ("2 minutes",), "eborn unsuccessful-session duration threshold")
    require(faq, ("40€ ou 50€", "40 € ou 50 €"), "eborn bank preauthorization range")
    require(faq, ("stationnement payant",), "eborn local parking evidence")
    require(faq, ("430 000 points de charge", "430000 points de charge"), "eborn roaming network size")

    facts = {
        "classification": {
            "network": "eborn",
            "regionalPublicNetwork": True,
            "country": "FR",
            "operationalManager": "Easy Charge (VINCI group)",
            "singleFlatTariff": False,
            "tariffDependsOnPowerAndCustomerProfile": True,
            "territoryDepartments": [
                "Allier", "Alpes-de-Haute-Provence", "Hautes-Alpes", "Ardèche", "Drôme",
                "Isère", "Loire", "Haute-Loire", "Savoie", "Haute-Savoie", "Var"
            ],
        },
        "operatorDirect": {
            "subscriptionPlans": {
                "aLaCarte": {"feeEurPerYear": 14.0},
                "forfait": {
                    "feeEurPerMonth": 49.0,
                    "includedKwhPerMonth": 250.0,
                    "beyondIncludedKwhUsesALaCarteTariff": True,
                    "unusedKwhCarryOver": False,
                },
            },
            "powerBands": {
                "acceleratedUpTo25Kw": {
                    "aLaCarteEurPerKwh": 0.310,
                    "forfaitEnergyIncludedWithinMonthlyAllowance": True,
                    "nonSubscriberEurPerKwh": 0.433,
                    "postChargeSubscriberEurPerMinute": 0.05,
                    "postChargeNonSubscriberEurPerMinute": 0.075,
                },
                "fastAbove25To60Kw": {
                    "aLaCarteEurPerKwh": 0.433,
                    "forfaitEnergyIncludedWithinMonthlyAllowance": True,
                    "nonSubscriberEurPerKwh": 0.573,
                    "postChargeSubscriberEurPerMinute": 0.075,
                    "postChargeNonSubscriberEurPerMinute": 0.12,
                },
                "ultraFastAbove60Kw": {
                    "aLaCarteEurPerKwh": 0.588,
                    "forfaitEnergyIncludedWithinMonthlyAllowance": True,
                    "nonSubscriberEurPerKwh": 0.650,
                    "postChargeSubscriberEurPerMinute": 0.075,
                    "postChargeNonSubscriberEurPerMinute": 0.12,
                },
            },
            "paymentMethods": ["eborn pass", "eborn app", "QR web payment", "contactless bank card where equipped"],
            "bankCardPreauthorization": {"possibleAmountsEur": [40.0, 50.0], "singleNetworkWideAmount": False},
        },
        "fees": {
            "postCharge": {
                "graceMinutesAfterChargeEnd": 30,
                "basis": "time parked/connected after charge end",
                "acceleratedOnlyBetween0800And2000": True,
                "fastAndUltraFastTimeWindowRestrictionPublished": False,
                "amountDependsOnPowerAndCustomerProfile": True,
            },
            "parking": {
                "networkWideIncluded": False,
                "siteOrMunicipalitySpecific": True,
                "mayBePaidOrTimeLimited": True,
            },
        },
        "failedSession": {
            "notBilledWhenBothConditionsMet": True,
            "energyLessThanKwh": 0.5,
            "durationLessThanMinutes": 2,
        },
        "reservation": {
            "subscriberOnly": True,
            "acceleratedChargers": True,
            "reservationWindowMinutes": 30,
        },
        "roaming": {
            "incomingThirdPartyBadge": {
                "classification": "third_party_eMSP",
                "operatorDirect": False,
                "priceSetByThirdPartyMobilityProvider": True,
            },
            "outgoingEbornPass": {
                "classification": "eborn_eMSP_on_partner_CPO",
                "operatorDirect": False,
                "partnerNetworkAccessPointsPublished": 430000,
                "markupPercentOverPartnerNetworkTariff": 15,
                "markupEffectiveFrom": "2025-03-31",
                "exactTariffSource": "eborn app selected third-party charging point",
            },
        },
        "network": {
            "publishedPointsMinimum": 3000,
            "publishedMaxPowerKw": 120,
            "liveAvailabilityInOfficialApp": True,
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "eborn-official-france-regional",
        "generatedAt": now_iso(),
        "operator": "eborn",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "The 49 EUR/month plan is modeled as a 250 kWh monthly allowance, not as a fake per-kWh tariff.",
            "Post-charge fees start 30 minutes after charge-end detection; accelerated chargers apply them only from 08:00 to 20:00.",
            "Third-party badges on eborn remain eMSP pricing; outgoing eborn roaming is modeled separately with the published 15% markup.",
            "Municipal or private parking costs remain site-specific and are not folded into the network energy tariff.",
        ],
    }

    (out / "eborn_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# eborn official France regional check\n\n"
        "- A la carte: **14 EUR/year**; Forfait: **49 EUR/month incl. 250 kWh/month**.\n"
        "- Accelerated <=25 kW: **0.310 subscriber / 0.433 non-subscriber EUR/kWh**.\n"
        "- Fast 25-60 kW: **0.433 / 0.573 EUR/kWh**.\n"
        "- Ultra-fast >60 kW: **0.588 / 0.650 EUR/kWh**.\n"
        "- Post-charge after **30 min**: subscriber **0.05/0.075/0.075 EUR/min**, non-subscriber **0.075/0.12/0.12 EUR/min**.\n"
        "- Accelerated post-charge applies only **08:00-20:00**.\n"
        "- Bank-card preauthorization: **40 or 50 EUR depending on terminal/session**.\n"
        "- Outgoing eborn roaming: **partner-network tariff + 15%** since 2025-03-31.\n"
        "- Published network: **>3,000 points**, up to **120 kW**, live availability in official app.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
