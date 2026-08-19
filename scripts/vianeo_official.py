#!/usr/bin/env python3
"""Extract current ENGIE Vianeo France charging tariff families from official sources.

Classification rules:
- ENGIE Vianeo Max is an operator-direct subscription: 0.33 EUR/kWh + 9.99 EUR/month.
- Vianeo+ / app without subscription is operator-direct, but station price remains variable.
- Bank-card / QR payment is operator-direct public pricing, also station-specific.
- Third-party RFID/roaming pricing belongs to the mobility-service provider, not Vianeo.
- Minute/occupation fees are station-specific unless a station rule is explicitly known.
- Temporary promotional prices are stored separately from normal tariffs.
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
    "pricing": "https://www.engie-vianeo.com/tarifs-recharge-voiture-electrique/",
    "maxSubscription": "https://www.engie-vianeo.com/abonnement-recharge-voiture-electrique/",
    "help": "https://www.engie-vianeo.com/aide/",
    "terms": "https://www.engie-vianeo.com/cguv/",
    "superOffPeak": "https://www.engie-vianeo.com/super-heures-creuses/",
    "selection": "https://www.engie-vianeo.com/selection/",
    "inventoryOrg": "https://www.data.gouv.fr/organizations/engie-mobilites-electriques/datasets",
}

SAMPLE_STATIONS = [
    "Igny Palaiseau",
    "Lieusaint Carré Sénart",
    "Noisy-le-Grand",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
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


def require(text: str, pattern: str, label: str) -> None:
    if not re.search(pattern, text, flags=re.I):
        raise RuntimeError(f"{label}: expected official evidence not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/vianeo")
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
        fetched[key] = norm(text_from_html(raw))

    pricing = fetched["pricing"]
    max_page = fetched["maxSubscription"]
    help_page = fetched["help"]
    terms = fetched["terms"]
    offpeak = fetched["superOffPeak"]
    selection = fetched["selection"]
    inventory = fetched["inventoryOrg"]

    require(max_page, r"0[,.]33\s*€?\s*/\s*kwh", "Vianeo Max kWh price")
    require(max_page, r"9[,.]99\s*€?\s*/\s*mois", "Vianeo Max monthly fee")
    require(max_page, r"sans engagement", "Vianeo Max no commitment")
    require(max_page, r"toutes les bornes.*france|partout en france", "Vianeo Max France-wide scope")

    require(pricing, r"0[,.]54\s*€?\s*/\s*kwh", "Vianeo app highway from price")
    require(pricing, r"0[,.]60\s*€?\s*/\s*kwh", "Vianeo card highway from price")
    require(pricing, r"10\s*%.*tarif public", "Vianeo app discount")
    require(pricing, r"tarif fixe par votre fournisseur de carte", "Vianeo roaming ownership")
    require(pricing, r"frais a la minute.*certaines stations", "Vianeo minute-fee caveat")

    require(help_page, r"pre-autorisation de 50\s*€", "Vianeo card preauthorization")
    require(terms, r"200\s*kwh\s*/\s*jour|200kwh/jour", "Vianeo Max daily cap")
    require(terms, r"points de charge dedies aux vehicules poids lourds", "Vianeo Max HGV exclusion")
    require(terms, r"prix.*kwh.*et/ou.*duree", "Vianeo energy/time pricing")

    require(offpeak, r"0[,.]29\s*€?\s*/\s*kwh", "Vianeo Super Heures Creuses price")
    require(offpeak, r"22h.*8h|22h00.*8h00", "Vianeo Super Heures Creuses time window")
    require(offpeak, r"31/12/2026", "Vianeo Super Heures Creuses end date")
    require(offpeak, r"uniquement.*application|via.*application", "Vianeo Super Heures Creuses app requirement")

    for station in SAMPLE_STATIONS:
        if norm(station) not in selection:
            raise RuntimeError(f"Vianeo selected-site sample missing: {station}")

    if "engie_vianeo" not in inventory and "engie vianeo" not in inventory:
        raise RuntimeError("ENGIE Vianeo data.gouv inventory marker missing")
    if "juillet 2026" not in inventory:
        raise RuntimeError("ENGIE Vianeo July 2026 inventory dataset marker missing")

    facts = {
        "classification": {
            "singleGuaranteedNationalPublicTariff": False,
            "stationLevelPriceLookupRequiredForExactSimulation": True,
            "nationalSubscriptionTariffExists": True,
            "reason": "Public/app/card prices vary by station, power and time, while Vianeo Max publishes one France-wide subscription kWh tariff.",
        },
        "operatorDirect": {
            "vianeoMax": {
                "classification": "operator_direct_subscription",
                "monthlyFeeEur": 9.99,
                "eurPerKwh": 0.33,
                "geography": "France",
                "allVianeoPassengerVehicleStationsFrance": True,
                "appOnly": True,
                "noCommitment": True,
                "dailyEnergyCapKwh": 200,
                "excludesHeavyGoodsDedicatedPoints": True,
                "stationMinuteFeesCanStillApply": True,
            },
            "appNoSubscription": {
                "classification": "operator_direct_app",
                "discountPercentVsPublic": 10.0,
                "highwayEurPerKwhFrom": 0.54,
                "nonHighwayAverageEurPerKwhPublished": 0.53,
                "exactStationPriceLookupRequired": True,
            },
            "bankCardOrQr": {
                "classification": "operator_direct_ad_hoc",
                "highwayEurPerKwhFrom": 0.60,
                "nonHighwayAverageEurPerKwhPublished": 0.59,
                "exactStationPriceLookupRequired": True,
                "paymentMethods": ["contactless bank card where present", "QR/web card payment", "Apple Pay / Google Pay where supported"],
                "preauthorizationEur": 50.0,
            },
        },
        "roaming": {
            "classification": "third_party_eMSP",
            "operatorDirect": False,
            "priceOwnedBy": "RFID/card provider",
            "exactPriceLookupRequired": True,
        },
        "fees": {
            "minuteOrOccupation": {
                "networkWideRateEurPerMin": None,
                "status": "station_specific",
                "canApplyDuringOrAfterCharge": True,
                "exactStationLookupRequired": True,
            },
            "parking": {
                "status": "site_or_landowner_rules_apply",
                "networkWideParkingFee": None,
            },
        },
        "promotions": {
            "superHeuresCreuses": {
                "classification": "temporary_operator_direct_promotion",
                "eurPerKwh": 0.29,
                "localTimeWindow": "22:00-08:00",
                "validThrough": "2026-12-31",
                "selectedStationsOnly": True,
                "appOnly": True,
                "vianeoPlusMembershipRequired": True,
                "notGeneralTariff": True,
            },
            "selectedFastDcSites": {
                "classification": "selected_site_promotion",
                "publishedEurPerKwh": 0.351,
                "stationLevelScope": True,
                "notGeneralTariff": True,
                "sampleEligibleStations": SAMPLE_STATIONS,
            },
        },
        "inventory": {
            "publisher": "Engie Mobilites Electriques",
            "source": "data.gouv.fr organization datasets",
            "latestDatasetMarkerObserved": "IRVE_STatique_ENGIE_Vianeo_All_Juillet 2026",
            "freshnessStatus": "official_static_inventory_monthly_dataset_marker",
            "sampleStationsForManualCheck": [
                {"station": "Igny Palaiseau", "region": "Ile-de-France", "selectedSitePromotionPage": True},
                {"station": "Lieusaint Carré Sénart", "region": "Ile-de-France", "selectedSitePromotionPage": True},
                {"station": "Noisy-le-Grand", "region": "Ile-de-France", "selectedSitePromotionPage": True},
            ],
        },
    }

    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "engie-vianeo-official-france",
        "generatedAt": now_iso(),
        "operator": "ENGIE Vianeo",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": v, "httpStatus": statuses.get(k)} for k, v in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Do not use the 0.54/0.60 highway figures as universal national tariffs: they are published as starting prices.",
            "Do not convert RFID roaming prices into ENGIE Vianeo direct prices.",
            "Minute/occupation fees require station-level lookup even with Vianeo Max.",
            "Temporary 0.29 and selected-site 0.351 EUR/kWh offers remain separate from standard tariff families.",
        ],
    }

    (out / "vianeo_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# ENGIE Vianeo France official check\n\n"
        "- Vianeo Max: **0.33 EUR/kWh + 9.99 EUR/month**, France-wide, app-only, 200 kWh/day cap.\n"
        "- App without subscription: **10% below public tariff**; highway from **0.54 EUR/kWh**; exact station lookup required.\n"
        "- Bank card / QR: highway from **0.60 EUR/kWh**; exact station lookup required; **50 EUR preauthorization**.\n"
        "- RFID/roaming: **third-party eMSP price**, never operator-direct.\n"
        "- Minute/occupation fees: **station-specific**, including for subscribers.\n"
        "- Super Heures Creuses: **0.29 EUR/kWh**, 22:00-08:00, selected stations, through 2026-12-31.\n"
        "- Selected fast-DC page: **0.351 EUR/kWh** on listed sites; stored as promotion only.\n"
        f"- Manual IDF samples: **{', '.join(SAMPLE_STATIONS)}**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
