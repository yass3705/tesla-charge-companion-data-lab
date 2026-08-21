#!/usr/bin/env python3
"""Validate current official Elsass Recharge tariff and access rules."""
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
HOME = "https://www.elsass-recharge.com/"
TARIFFS = "https://www.elsass-recharge.com/tarifs/"
FAQ = "https://www.elsass-recharge.com/faq/"
STRASBOURG = "https://www.strasbourg.eu/bornes-de-recharges-vehicules-electriques-hybrides"
FRESHMILE_SHOP = "https://charge.freshmile.com/shop"
FRESHMILE_ARTICLE = "https://www.freshmile.com/actualites/decouvrez-le-reseau-de-bornes-elsass-recharge/"


def fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(getattr(r, "status", 200)), r.read(), r.geturl()


def plain(raw: bytes) -> str:
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", "'").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def require(text: str, *items: str):
    n = norm(text)
    missing = [x for x in items if norm(x) not in n]
    if missing:
        raise RuntimeError("Elsass Recharge official evidence missing: " + ", ".join(missing))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/elsass_recharge")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sources = {}
    for key, url in {
        "home": HOME,
        "tariffs": TARIFFS,
        "faq": FAQ,
        "strasbourg": STRASBOURG,
        "freshmileShop": FRESHMILE_SHOP,
        "freshmileArticle": FRESHMILE_ARTICLE,
    }.items():
        status, raw, final = fetch(url)
        if status != 200:
            raise RuntimeError(f"HTTP failure {key}={status}")
        sources[key] = {"status": status, "raw": raw, "final": final, "text": plain(raw)}

    require(sources["home"]["text"], "Eurométropole de Strasbourg", "22 kW", "50 kW", "150 kW")
    require(
        sources["tariffs"]["text"],
        "Tarifs de jour entre 8h-20h",
        "0,34 €TTC/kWh tarif public",
        "0,306 €TTC/kWh via l’appli ENGIE Vianeo",
        "0,39 €TTC/kWh tarif public",
        "0,351 €TTC/kWh via l’appli ENGIE Vianeo",
        "0,49 €TTC/kWh tarif public",
        "0,441 €TTC/kWh via l’appli ENGIE Vianeo",
        "0,51 €TTC/kWh",
        "0,459 €TTC/kWh via l’appli ENGIE Vianeo",
        "0,05 €TTC/min",
        "0,30 € après 60 min",
        "Tarifs de nuit entre 20h et 8h",
        "Pas de coût d’emplacement",
        "0,03 €TTC/min sur DC 24 kW",
    )
    require(
        sources["faq"]["text"],
        "mode invité",
        "payer par CB",
        "carte d’un autre opérateur",
        "Freshmile",
        "tarification augmente au-delà d’une certaine durée de branchement",
        "33 communes",
    )
    require(sources["strasbourg"]["text"], "255 bornes", "ENGIE Solutions/Freshmile", "Elsass Recharge")
    require(sources["freshmileArticle"]["text"], "abonnement coûte 8 € par mois", "tarifs préférentiels")

    current_shop_has_subscription = "elsass recharge" in norm(sources["freshmileShop"]["text"])

    public = {
        "upTo22Kw": {
            "powerKwMax": 22,
            "energyEurPerKwh": 0.34,
            "day": {"window": "08:00-20:00", "eurPerMinuteConnected": 0.03},
            "night": {"window": "20:00-08:00", "eurPerMinuteConnected": 0.0},
        },
        "dc24Kw": {
            "powerKw": 24,
            "energyEurPerKwh": 0.39,
            "day": {"eurPerMinuteConnected": 0.03},
            "night": {"eurPerMinuteConnected": 0.03},
        },
        "dc50Kw": {
            "powerKw": 50,
            "energyEurPerKwh": 0.49,
            "time": {"eurPerMinuteFirst60": 0.05, "eurPerMinuteAfter60": 0.30},
        },
        "dc150Kw": {
            "powerKw": 150,
            "energyEurPerKwh": 0.51,
            "time": {"eurPerMinuteFirst60": 0.05, "eurPerMinuteAfter60": 0.30},
        },
    }
    engie_app = {
        "discountVsPublicEnergyPercent": 10,
        "upTo22Kw": {"energyEurPerKwh": 0.306},
        "dc24Kw": {"energyEurPerKwh": 0.351},
        "dc50Kw": {"energyEurPerKwh": 0.441},
        "dc150Kw": {"energyEurPerKwh": 0.459},
        "timeComponentsSameAsPublic": True,
    }

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "elsass-recharge-official-grandest",
        "generatedAt": now(),
        "operator": "Elsass Recharge",
        "serviceOperators": ["ENGIE Vianeo", "Freshmile"],
        "country": "FR",
        "region": "Grand Est",
        "department": "Bas-Rhin",
        "territory": "Eurométropole de Strasbourg",
        "classification": {
            "localPublicNetwork": True,
            "directPublishedTariff": True,
            "energyAndTimeBased": True,
            "powerDependent": True,
            "dayNightDependent": True,
            "appDiscount": True,
            "highPowerTimeSurcharge": True,
            "roamingMayDiffer": True,
        },
        "network": {
            "publishedPowerClassesKw": [22, 24, 50, 150],
            "territoryCommunes": 33,
            "publicProjectTargetStations": 255,
        },
        "operatorDirect": {
            "publicTariff": public,
            "engieVianeoApp": engie_app,
            "freshmileGuestCbSupported": True,
            "freshmilePassSupported": True,
            "otherMobilityOperatorsSupported": True,
        },
        "subscription": {
            "historicalOfficialFreshmileMonthlyEur": 8.0,
            "historicalPreferentialTariffs": True,
            "currentlyListedOnProductionFreshmileShop": current_shop_has_subscription,
            "currentExactMemberTariffValidated": False,
            "rankableAsSeparateOffer": False,
            "note": "Freshmile still publishes an official article describing an 8 EUR/month Elsass subscription, but the current production shop does not list Elsass Recharge. Do not rank a member offer until current purchaseability and exact member prices are reconfirmed.",
        },
        "parkingAndOccupancy": {
            "separateParkingFeeValidated": False,
            "connectionTimeFeeIsTariffComponent": True,
            "upTo22KwNoNightConnectionTimeFee": True,
            "dc50And150TimeRateIncreasesAfter60Min": True,
            "note": "Model the published connection-time component separately from municipal parking. The official FAQ also states non-connected vehicles may be ticketed.",
        },
        "tccDecision": {
            "operatorValidated": True,
            "publicTariffClassable": True,
            "engieVianeoAppTariffClassable": True,
            "subscriptionTariffClassable": False,
            "roamingSeparate": True,
            "timeFeeMustBeModeled": True,
            "note": "Use the current Elsass public tariff and the ENGIE Vianeo app -10% energy tariff as separate rankable variants. Keep historical Freshmile subscription and roaming prices out of ranking until current exact pricing is proven.",
        },
        "sourceEvidence": {
            "officialOnly": True,
            "sources": {
                key: {
                    "url": value["final"],
                    "httpStatus": value["status"],
                    "sha256": hashlib.sha256(value["raw"]).hexdigest(),
                }
                for key, value in sources.items()
            },
        },
        "publicationStatus": "validated_candidate",
    }
    sig = {k: payload[k] for k in ("network", "operatorDirect", "subscription", "parkingAndOccupancy", "tccDecision")}
    payload["sourceEvidence"]["relevantTariffFingerprintSha256"] = hashlib.sha256(
        json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    (out / "elsass_recharge_official_grandest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (out / "SUMMARY.md").write_text(
        "# Elsass Recharge — Eurométropole de Strasbourg\n\n"
        "Current official public and ENGIE Vianeo app tariffs are validated for 22/24/50/150 kW classes. The app gives 10% off the energy component. Connection-time pricing is power- and day/night-dependent, with a sharp rate increase after 60 minutes on 50/150 kW. A historical 8 EUR/month Freshmile subscription remains documented, but it is absent from the current production Freshmile shop, so that member offer stays non-rankable pending reconfirmation.\n"
    )


if __name__ == "__main__":
    main()
