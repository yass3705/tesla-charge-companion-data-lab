#!/usr/bin/env python3
"""Validate current e-Totem France public tariff rules from official/public-authority sources.

Model intentionally mirrors Powerdot/IZIVIA/Fastned validation: this is a tariff/rule
validator, not a national station extractor.

Key classification:
- e-Totem operates/manages several networks, so one guaranteed national CPO-direct tariff
  must not be assumed for exact simulation.
- The e-Totem badge has no monthly subscription fee on directly operated networks and e-Totem
  states 0% commission there.
- The national Liberté offer is billed in kWh, but current HTML pages do not expose one exact
  nationwide kWh rate covering every directly operated/local network.
- SEMOB is a local subscription offer and must remain separate from the national/default layer.
- Post-charge/parking rules are local-network/site rules unless an e-Totem-wide source says otherwise.
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
    "users": "https://www.e-totem.eu/utilisateurs-particuliers/",
    "mobility": "https://www.e-totem.eu/services/operateur-ou-delegataire-de-service/",
    "home": "https://www.e-totem.eu/",
    "saintLouis": "https://www.agglo-saint-louis.fr/fr/au-quotidien/mobilite/bornes-electriques/",
    "dataGouvOrg": "https://www.data.gouv.fr/organizations/e-totem/datasets",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
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
    s = s.lower().replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def has_number(text: str, value: str) -> bool:
    a = re.escape(value.replace(".", ","))
    b = re.escape(value.replace(",", "."))
    return bool(re.search(rf"(?<!\d)(?:{a}|{b})(?!\d)", text))


def require(text: str, phrase: str, label: str) -> None:
    if norm(phrase) not in norm(text):
        raise RuntimeError(f"{label}: missing expected evidence: {phrase}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/etotem")
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

    users = pages["users"]
    require(users, "plus de 900 points de charge", "e-Totem users")
    require(users, "0% de commission", "e-Totem users")
    require(users, "pas de frais d'abonnement mensuel", "e-Totem users")
    require(users, "250 000 points de charge", "e-Totem users")

    mobility = pages["mobility"]
    require(mobility, "formule liberte", "e-Totem mobility")
    require(mobility, "je paie uniquement ce que je consomme en kwh", "e-Totem mobility")
    require(mobility, "abonnement semob", "e-Totem mobility")
    for v in ("45", "100", "0,45", "0,59"):
        if not has_number(mobility, v):
            raise RuntimeError(f"e-Totem mobility: missing current SEMOB numeric evidence {v}")

    home = pages["home"]
    require(home, "250 000 points de charges compatibles", "e-Totem home")
    partner_markers = ["ionity", "total energies", "freshmile", "shell recharge", "metropolis", "eborn"]
    if sum(1 for x in partner_markers if x in home) < 4:
        raise RuntimeError("e-Totem home: partner-network evidence incomplete")

    saint = pages["saintLouis"]
    require(saint, "politique tarifaire des bornes de recharge", "Saint-Louis Agglomération")
    for v in ("0,30", "0,39", "0,45", "0,49"):
        if not has_number(saint, v):
            raise RuntimeError(f"Saint-Louis Agglomération: missing tariff {v}")
    require(saint, "10 minutes de franchise", "Saint-Louis Agglomération")
    require(saint, "1 € / 15 min", "Saint-Louis Agglomération")
    require(saint, "3 € / 15 min", "Saint-Louis Agglomération")
    require(saint, "limitee a 2 € maximum", "Saint-Louis Agglomération")

    dg = pages["dataGouvOrg"]
    ids = ["fr*ese", "fr*p01", "fr*eti", "fr*g10", "fr*car", "fr*sua"]
    found_ids = [x.upper() for x in ids if x in dg]
    if len(found_ids) < 5:
        raise RuntimeError(f"data.gouv e-Totem: expected multiple managed network IDs, found {found_ids}")

    facts = {
        "classification": {
            "singleGuaranteedNationalCpoDirectTariff": False,
            "stationOrNetworkLevelLookupRequiredForExactCpoDirect": True,
            "reason": "Current sources show several e-Totem-managed networks and distinct local tariff schedules; one universal CPO-direct France tariff must not be assumed.",
        },
        "operatorDirect": {
            "directlyOperatedNetworks": {
                "publicPointsClaimed": 900,
                "publicPointsClaimedQualifier": "more_than",
                "badgeCommissionPercent": 0.0,
                "badgeMonthlyFeeEur": 0.0,
                "exactPriceModel": "network_or_site_specific",
                "exactPriceLookupRequired": True,
            },
            "nationalLibertyOffer": {
                "scope": "national_mobility_offer",
                "billingUnit": "kWh",
                "monthlySubscriptionFeeEur": 0.0,
                "exactCurrentNationwideEurPerKwh": None,
                "exactCurrentNationwidePriceStatus": "not_exposed_as_one_universal_rate_on_current_first_party_html_pages",
            },
        },
        "mobilityProviderLayer": {
            "badgeCompatiblePointsClaimed": 250000,
            "classification": "eTotem_eMSP_and_partner_network_access",
            "partnerExamples": ["IONITY", "TotalEnergies", "Freshmile", "Shell Recharge", "Metropolis", "eborn"],
            "exactCurrentPartnerTariffStatus": "do_not_promote_historical_2024_uniform_rates_without_current_first_party_reconfirmation",
        },
        "regionalOffers": {
            "SEMOB": {
                "scope": "Saint-Etienne Metropole only",
                "monthlyMinimumEur": 45.0,
                "includedKwh": 100.0,
                "effectiveEurPerKwh": 0.45,
                "eurPerKwhAboveIncluded": 0.45,
                "referenceNonSubscriberEurPerKwh": 0.59,
                "otherNetworksFallback": "Liberty offer",
                "generalNationalTariff": False,
            }
        },
        "fees": {
            "networkWideIdleOrPostChargeFee": None,
            "networkWideIdleFeeStatus": "not_asserted_from_current_first_party_sources",
            "parking": {
                "status": "local_network_or_site_specific",
            },
        },
        "representativeNetworkChecks": [
            {
                "network": "Saint-Louis Agglomeration",
                "operator": "e-Totem",
                "sourceType": "official_local_authority",
                "tariffs": {
                    "eCityEco3_7KwEurPerKwh": 0.30,
                    "eCityNormalBoost7_4To22KwEurPerKwh": 0.39,
                    "eFast50To99KwEurPerKwh": 0.45,
                    "eFast100To180KwEurPerKwh": 0.49,
                },
                "postCharge": {
                    "graceMinutes": 10,
                    "eCityEurPer15Min": 1.0,
                    "eFastEurPer15Min": 3.0,
                    "overnightCapEur": 2.0,
                    "overnightWindow": "22:00-08:00",
                },
            }
        ],
        "managedNetworkIdsObserved": found_ids,
    }

    fp = hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "etotem-official-france",
        "generatedAt": now_iso(),
        "operator": "e-Totem",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "firstPartyCurrentSources": ["users", "mobility", "home"],
            "officialLocalAuthorityValidation": ["saintLouis"],
            "publicNetworkTopologyEvidence": ["dataGouvOrg"],
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fp,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "This validator intentionally does not build a national station database.",
            "Do not reuse the historical 2024 0.39/0.49 CPO or 0.49/0.59 partner-network announcements as universal current tariffs without current first-party confirmation.",
            "SEMOB is a regional offer and must not be shown as a nationwide e-Totem subscription.",
            "Saint-Louis Agglomeration demonstrates that e-Totem-managed direct tariffs and post-charge fees can be local-network specific.",
        ],
    }

    (out / "etotem_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# e-Totem France official check\n\n"
        "- Validation model: **operator rules only** (Powerdot/IZIVIA/Fastned style), no national station extract.\n"
        "- One guaranteed France-wide CPO-direct tariff: **no**; exact direct price is network/site specific.\n"
        "- Directly operated network badge layer: **0% commission**, **0 EUR/month**.\n"
        "- Liberté: billed in **kWh**; one exact current nationwide rate is **not exposed on current first-party HTML pages**.\n"
        "- SEMOB local subscription: **45 EUR/month minimum for 100 kWh**, then **0.45 EUR/kWh**; page compares against **0.59 EUR/kWh**.\n"
        "- Saint-Louis sample: **0.30 / 0.39 / 0.45 / 0.49 EUR/kWh** depending power, with local post-charge rules.\n"
        f"- Managed network IDs observed on data.gouv: **{len(found_ids)}**.\n"
        f"- Fingerprint: `{fp}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
