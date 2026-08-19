#!/usr/bin/env python3
"""Extract Freshmile France public charging rules from official Freshmile sources.

Classification rules:
- Freshmile acts as both CPO and eMSP/EMP; do not merge those tariff layers.
- There is no single guaranteed national Freshmile charging tariff.
- Exact price is network / station specific and must be read from the Freshmile app/map.
- Connection-time and parking components are station/local-policy specific.
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
    "help": "https://www.freshmile.com/aide-contact/",
    "pass": "https://www.freshmile.com/nos-solutions/cartes-de-recharge/cartes-de-recharge-particuliers/",
    "passOverview": "https://www.freshmile.com/nos-solutions/cartes-de-recharge/",
    "empTerms": "https://www.freshmile.com/cgu-cgv/cgu-emp/",
    "cpoTerms": "https://www.freshmile.com/cgu-cgv/cgv/",
    "mapArticle": "https://www.freshmile.com/articles/tout-savoir-sur-la-carte-des-bornes/",
    "shop": "https://charge.freshmile.com/shop",
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


def require_any(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: expected official evidence not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/freshmile")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    fetched: dict[str, str] = {}
    statuses: dict[str, int] = {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        fetched[key] = text_from_html(raw)

    help_text = norm(fetched["help"])
    pass_text = norm(fetched["pass"])
    pass_overview = norm(fetched["passOverview"])
    emp_terms = norm(fetched["empTerms"])
    cpo_terms = norm(fetched["cpoTerms"])
    map_article = norm(fetched["mapArticle"])
    shop = norm(fetched["shop"])

    require_any(help_text, ("entierement gratuits, sans abonnement ni frais mensuels", "entierement gratuit, sans abonnement"), "Freshmile account pricing")
    require_any(help_text, ("varient sur chaque reseau de bornes", "tarifs appliques sur une borne"), "Freshmile station/network pricing")
    require_any(help_text, ("composante de temps de branchement", "temps de branchement"), "Freshmile connection-time component")
    require_any(help_text, ("stationnement peut etre payant", "politique de stationnement locale"), "Freshmile parking policy")
    require_any(help_text, ("carte des bornes en temps reel", "etat des bornes en temps reel"), "Freshmile live map")
    require_any(help_text, ("empreinte bancaire",), "Freshmile card preauthorization")

    if not re.search(r"\b4[,.]99\s*€", pass_text):
        raise RuntimeError("Freshmile Pass: current 4.99 EUR price evidence missing")
    require_any(pass_text, ("650 000", "650000"), "Freshmile Pass roaming coverage")
    require_any(pass_text, ("sans abonnement",), "Freshmile Pass no subscription")

    if not re.search(r"empreinte(?: bancaire)? de\s*50\s*€", pass_overview):
        raise RuntimeError("Freshmile 50 EUR card preauthorization evidence missing")

    require_any(emp_terms, ("freshmile agit en qualite d'operateur de mobilite electrique",), "Freshmile EMP classification")
    require_any(emp_terms, ("bornes de recharge tierces", "itinerance sortante"), "Freshmile outgoing roaming")
    require_any(emp_terms, ("utilisateur tiers", "operateur de mobilite tiers"), "Freshmile incoming roaming")
    require_any(emp_terms, ("tarif fixe par ce dernier et affiche sur l'application et le site internet",), "Freshmile eMSP third-party pricing")

    require_any(cpo_terms, ("client professionnel propose a freshmile les tarifs de recharge",), "Freshmile CPO owner-defined tariff")

    require_any(map_article, ("verifier leur disponibilite et consulter leur tarif",), "Freshmile map price/availability")

    partner_subscriptions = []
    if "connect and go moselle metz" in shop and "3.00 € / mois" in shop:
        partner_subscriptions.append({"network": "Connect and Go Moselle Metz", "feeEur": 3.0, "period": "month"})
    if "morbihan energies" in shop and "20.00 € / an" in shop:
        partner_subscriptions.append({"network": "Morbihan Energies", "feeEur": 20.0, "period": "year"})
    if "connect and go meurthe-et-moselle" in shop and "3.00 € / mois" in shop:
        partner_subscriptions.append({"network": "Connect and Go Meurthe-et-Moselle", "feeEur": 3.0, "period": "month"})

    facts = {
        "classification": {
            "singleGuaranteedNationalTariff": False,
            "stationLevelPriceLookupRequiredForExactSimulation": True,
            "freshmileActsAsCpoAndEmsp": True,
            "reason": "Freshmile states that charging prices vary by network/station and are displayed in its app/map; CPO and eMSP roles must remain separate.",
        },
        "operatorDirect": {
            "freshmileManagedStations": {
                "classification": "cpo_station_or_network_specific",
                "nationalEurPerKwh": None,
                "exactPriceLookupRequired": True,
                "priceDefinedPerNetworkOrSite": True,
                "validatedTariffComponents": ["energy_if_applicable", "connection_time_if_applicable"],
                "otherComponentsRequireExactStationEvidence": True,
            },
            "appOrGuestPayment": {
                "classification": "operator_direct_app_or_guest",
                "accountRequired": False,
                "priceShownBeforeCharge": True,
                "exactStationPriceLookupRequired": True,
            },
            "bankCard": {
                "classification": "operator_direct_card_where_supported",
                "tpeAvailableOnSomeStations": True,
                "preauthorizationEur": 50.0,
                "onlyActualSessionAmountCaptured": True,
            },
        },
        "mobilityProvider": {
            "freshmileAccount": {
                "classification": "emsp_account",
                "registrationFeeEur": 0.0,
                "monthlyFeeEur": 0.0,
            },
            "freshmilePass": {
                "classification": "emsp_rfid_pass",
                "purchasePriceEur": 4.99,
                "monthlyFeeEur": 0.0,
                "coveragePointsEuropePublished": 650000,
                "thirdPartyRoamingPriceSetByFreshmileAndShownInApp": True,
                "mustNotBeClassifiedAsThirdPartyCpoDirect": True,
            },
            "incomingRoamingOnFreshmileCpo": {
                "classification": "third_party_emsp",
                "operatorDirect": False,
                "priceOwnedBy": "third-party mobility provider",
            },
        },
        "fees": {
            "connectionTime": {
                "status": "station_tariff_specific",
                "networkWideEurPerMin": None,
                "canContinueAfterEnergyStops": True,
                "exactStationLookupRequired": True,
            },
            "parking": {
                "status": "local_parking_policy",
                "networkWideParkingFee": None,
                "checkLocalSigns": True,
            },
        },
        "sessionRules": {
            "failedShortSessions": {
                "scope": "most_stations_not_guaranteed_all",
                "typicallyNotBilledIfDurationUnderMinutes": 2,
                "orEnergyUnderKwh": 0.5,
            },
        },
        "liveMap": {
            "officialUrl": "https://charge.freshmile.com/map",
            "realTimeStatusAvailable": True,
            "tariffDisplayed": True,
            "powerAndConnectorDetailsDisplayed": True,
            "preferredSourceForExactPriceAndAvailability": True,
        },
        "partnerNetworkSubscriptions": partner_subscriptions,
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.1",
        "dataset": "freshmile-official-france",
        "generatedAt": now_iso(),
        "operator": "Freshmile",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [
                {"key": key, "url": url, "httpStatus": statuses.get(key)}
                for key, url in SOURCES.items()
            ],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Do not invent a national Freshmile kWh price: the official help page says tariffs vary by network/station.",
            "Freshmile CPO-managed-station pricing and Freshmile eMSP roaming pricing are distinct layers.",
            "Connection-time components and parking rules must be resolved at station/local-policy level.",
            "The official Freshmile map is the preferred source for exact price and live availability before simulation.",
        ],
    }

    (out / "freshmile_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Freshmile France official check\n\n"
        "- National guaranteed charging tariff: **none**; network/station lookup required.\n"
        "- Freshmile account: **free, no monthly fee**.\n"
        "- Freshmile Pass: **4.99 EUR**, no monthly subscription, **650,000** published interoperable points in Europe.\n"
        "- Bank-card preauthorization: **50 EUR**; only actual session amount captured.\n"
        "- Connection-time component: **station-specific** and can continue after energy stops.\n"
        "- Parking: **local policy**, not a Freshmile-wide fee.\n"
        "- Exact price / live availability source: **Freshmile app/map**.\n"
        f"- Partner-network subscriptions observed in official shop: **{len(partner_subscriptions)}**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
