#!/usr/bin/env python3
"""Validate current official Elsass Recharge tariff and access rules."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
import urllib.error
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


def fetch(url: str, required: bool = True):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "fr-FR,fr;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return int(getattr(r, "status", 200)), r.read(), r.geturl()
    except urllib.error.HTTPError as exc:
        if required:
            raise
        return int(exc.code), b"", url
    except urllib.error.URLError:
        if required:
            raise
        return 0, b"", url


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


def source_record(status: int, raw: bytes, final: str):
    return {
        "url": final,
        "httpStatus": status,
        "sha256": hashlib.sha256(raw).hexdigest() if raw else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/elsass_recharge")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sources = {}
    for key, url in {"home": HOME, "tariffs": TARIFFS, "faq": FAQ}.items():
        status, raw, final = fetch(url, required=True)
        if status != 200:
            raise RuntimeError(f"HTTP failure {key}={status}")
        sources[key] = {"status": status, "raw": raw, "final": final, "text": plain(raw)}

    for key, url in {"strasbourg": STRASBOURG, "freshmileShop": FRESHMILE_SHOP, "freshmileArticle": FRESHMILE_ARTICLE}.items():
        status, raw, final = fetch(url, required=False)
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

    strasbourg_project_validated = False
    if sources["strasbourg"]["status"] == 200:
        st = norm(sources["strasbourg"]["text"])
        strasbourg_project_validated = all(norm(x) in st for x in ("255 bornes", "ENGIE Solutions/Freshmile", "Elsass Recharge"))

    historical_subscription_documented = False
    if sources["freshmileArticle"]["status"] == 200:
        at = norm(sources["freshmileArticle"]["text"])
        historical_subscription_documented = norm("abonnement coûte 8 € par mois") in at and norm("tarifs préférentiels") in at

    current_shop_has_subscription = None
    if sources["freshmileShop"]["status"] == 200:
        current_shop_has_subscription = "elsass recharge" in norm(sources["freshmileShop"]["text"])

    public = {
        "upTo22Kw": {"powerKwMax": 22, "energyEurPerKwh": 0.34, "day": {"window": "08:00-20:00", "eurPerMinuteConnected": 0.03}, "night": {"window": "20:00-08:00", "eurPerMinuteConnected": 0.0}},
        "dc24Kw": {"powerKw": 24, "energyEurPerKwh": 0.39, "day": {"eurPerMinuteConnected": 0.03}, "night": {"eurPerMinuteConnected": 0.03}},
        "dc50Kw": {"powerKw": 50, "energyEurPerKwh": 0.49, "time": {"eurPerMinuteFirst60": 0.05, "eurPerMinuteAfter60": 0.30}},
        "dc150Kw": {"powerKw": 150, "energyEurPerKwh": 0.51, "time": {"eurPerMinuteFirst60": 0.05, "eurPerMinuteAfter60": 0.30}},
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
        "classification": {"localPublicNetwork": True, "directPublishedTariff": True, "energyAndTimeBased": True, "powerDependent": True, "dayNightDependent": True, "appDiscount": True, "highPowerTimeSurcharge": True, "roamingMayDiffer": True},
        "network": {"publishedPowerClassesKw": [22, 24, 50, 150], "territoryCommunes": 33, "publicProjectTargetStations": 255 if strasbourg_project_validated else None, "projectTargetSourceValidatedThisRun": strasbourg_project_validated},
        "operatorDirect": {"publicTariff": public, "engieVianeoApp": engie_app, "freshmileGuestCbSupported": True, "freshmilePassSupported": True, "otherMobilityOperatorsSupported": True},
        "subscription": {
            "historicalOfficialFreshmileMonthlyEur": 8.0 if historical_subscription_documented else None,
            "historicalPreferentialTariffs": historical_subscription_documented,
            "currentlyListedOnProductionFreshmileShop": current_shop_has_subscription,
            "currentExactMemberTariffValidated": False,
            "rankableAsSeparateOffer": False,
            "note": "An older official Freshmile page describes an 8 EUR/month Elsass subscription, but the current exact member tariff and current purchaseability are not proven by the tariff page. Keep the member offer out of ranking until reconfirmed.",
        },
        "parkingAndOccupancy": {
            "separateParkingFeeValidated": False,
            "connectionTimeFeeIsTariffComponent": True,
            "upTo22KwNoNightConnectionTimeFee": True,
            "dc50And150TimeRateIncreasesAfter60Min": True,
            "note": "Model the published connection-time component separately from municipal parking. The official FAQ also states non-connected vehicles may be ticketed.",
        },
        "tccDecision": {"operatorValidated": True, "publicTariffClassable": True, "engieVianeoAppTariffClassable": True, "subscriptionTariffClassable": False, "roamingSeparate": True, "timeFeeMustBeModeled": True, "note": "Use the current Elsass public tariff and ENGIE Vianeo app -10% energy tariff as separate rankable variants. Keep member and roaming prices separate until current exact pricing is proven."},
        "sourceEvidence": {
            "officialOnly": True,
            "coreSourcesValidated": ["home", "tariffs", "faq"],
            "sources": {key: source_record(value["status"], value["raw"], value["final"]) for key, value in sources.items()},
        },
        "publicationStatus": "validated_candidate",
    }
    sig = {k: payload[k] for k in ("network", "operatorDirect", "subscription", "parkingAndOccupancy", "tccDecision")}
    payload["sourceEvidence"]["relevantTariffFingerprintSha256"] = hashlib.sha256(json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    (out / "elsass_recharge_official_grandest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (out / "SUMMARY.md").write_text(
        "# Elsass Recharge — Eurométropole de Strasbourg\n\n"
        "Current official public and ENGIE Vianeo app tariffs are validated for 22/24/50/150 kW classes. The app gives 10% off the energy component. Connection-time pricing is power- and day/night-dependent, with a sharp rate increase after 60 minutes on 50/150 kW. The older Freshmile member offer is intentionally kept non-rankable until current purchaseability and exact prices are reconfirmed.\n"
    )


if __name__ == "__main__":
    main()
