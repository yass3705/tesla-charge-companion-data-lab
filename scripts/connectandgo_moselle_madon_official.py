#!/usr/bin/env python3
"""Validate current official Connect&go Moselle et Madon tariff rules."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
TARIFFS = "https://mosellemadon.connectandgo.fr/tarifs/"
HOME = "https://mosellemadon.connectandgo.fr/"


def fetch(url: str):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "fr-FR,fr;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(getattr(r, "status", 200)), r.read(), r.geturl()


def plain(raw: bytes) -> str:
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", "'").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def require(text: str, *items: str):
    n = norm(text)
    missing = [x for x in items if norm(x) not in n]
    if missing:
        raise RuntimeError("Connect&go Moselle et Madon official evidence missing: " + ", ".join(missing))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/connectandgo_moselle_madon")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    hs, hraw, hfinal = fetch(HOME)
    ts, traw, tfinal = fetch(TARIFFS)
    if hs != 200 or ts != 200:
        raise RuntimeError(f"HTTP failure home={hs} tariffs={ts}")

    htext = plain(hraw)
    ttext = plain(traw)
    require(
        htext,
        "24 bornes réparties sur 14 communes",
        "22 kW",
        "25 kW",
        "120 kW",
        "Freshmile",
        "100% verte",
    )
    require(
        ttext,
        "SANS ABONNEMENT",
        "0€ /mois",
        "De 8h30 à 20h : 0,27 € par kWh entamé et 0,025 € par minute",
        "0,45 € par kWh entamé et 0,025 € par minute",
        "après 3h de branchement, 0,16 € par minute sans consommation",
        "après 1h de branchement, 0,20 € par minute sans consommation",
        "De 20h à 8h30 : 0,25 € par kWh entamé",
        "AVEC ABONNEMENT",
        "3€ /mois",
        "De 9h à 20h : 0,25 € par kWh entamé et 0,025 € par minute",
        "0,43 € par kWh entamé et 0,02 € par minute",
        "après 4h de branchement, 0,13 € par minute sans consommation",
        "après 1h30 de branchement, 0,15 € par minute sans consommation",
        "De 20h à 9h : 0,20 € par kWh entamé",
    )

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "connectandgo-moselle-madon-official-grandest",
        "generatedAt": now(),
        "operator": "Connect&go - Moselle et Madon",
        "serviceOperator": "Freshmile",
        "country": "FR",
        "region": "Grand Est",
        "department": "Meurthe-et-Moselle",
        "classification": {
            "localPublicNetwork": True,
            "directPublishedTariff": True,
            "energyAndTimeBased": True,
            "powerDependent": True,
            "dayNightDependent": True,
            "memberTariffAvailable": True,
            "idleSurcharge": True,
            "roamingMayDiffer": True,
        },
        "network": {
            "publishedPlannedStationCount": 24,
            "publishedMunicipalityCount": 14,
            "publishedConnectorPowerKw": [22, 25, 120],
            "freshmileAccess": True,
            "electricity100PercentGreen": True,
        },
        "operatorDirect": {
            "withoutSubscription": {
                "monthlyEur": 0.0,
                "day": {
                    "window": "08:30-20:00",
                    "below30Kw": {"eurPerKwh": 0.27, "eurPerMinute": 0.025},
                    "above30Kw": {"eurPerKwh": 0.45, "eurPerMinute": 0.025},
                },
                "night": {
                    "window": "20:00-08:30",
                    "below30Kw": {"eurPerKwh": 0.25, "eurPerMinute": 0.0},
                    "above30Kw": {"eurPerKwh": 0.45, "eurPerMinute": 0.025},
                },
                "idle": {
                    "below30Kw": {"afterMinutes": 180, "eurPerMinute": 0.16, "condition": "without_consumption"},
                    "above30Kw": {"afterMinutes": 60, "eurPerMinute": 0.20, "condition": "without_consumption"},
                },
            },
            "withSubscription": {
                "monthlyEur": 3.0,
                "day": {
                    "window": "09:00-20:00",
                    "below30Kw": {"eurPerKwh": 0.25, "eurPerMinute": 0.025},
                    "above30Kw": {"eurPerKwh": 0.43, "eurPerMinute": 0.02},
                },
                "night": {
                    "window": "20:00-09:00",
                    "below30Kw": {"eurPerKwh": 0.20, "eurPerMinute": 0.0},
                    "above30Kw": {"eurPerKwh": 0.43, "eurPerMinute": 0.02},
                },
                "idle": {
                    "below30Kw": {"afterMinutes": 240, "eurPerMinute": 0.13, "condition": "without_consumption"},
                    "above30Kw": {"afterMinutes": 90, "eurPerMinute": 0.15, "condition": "without_consumption"},
                },
            },
        },
        "rules": {
            "tariffThresholdLabel": "30 kW",
            "idleSurchargeAppliesWithoutConsumption": True,
            "lowPowerNightHasNoMinuteComponent": True,
        },
        "tccDecision": {
            "operatorValidated": True,
            "directTariffClassable": True,
            "subscriptionSeparateOffer": True,
            "roamingSeparate": True,
            "idleFeeMustBeModeled": True,
            "note": "Use Connect&go Moselle et Madon as a local direct Freshmile-backed offer; keep the 3 EUR/month subscription and roaming prices as separate tariff variants.",
        },
        "sourceEvidence": {
            "officialOnly": True,
            "homeUrl": hfinal,
            "homeHttpStatus": hs,
            "tariffsUrl": tfinal,
            "tariffsHttpStatus": ts,
            "homeSha256": hashlib.sha256(hraw).hexdigest(),
            "tariffsSha256": hashlib.sha256(traw).hexdigest(),
        },
        "publicationStatus": "validated_candidate",
    }
    sig = {k: payload[k] for k in ("network", "operatorDirect", "rules", "tccDecision")}
    payload["sourceEvidence"]["relevantTariffFingerprintSha256"] = hashlib.sha256(
        json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    (out / "connectandgo_moselle_madon_official_grandest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    (out / "SUMMARY.md").write_text(
        "# Connect&go — Moselle et Madon\n\n"
        "Official local tariff validated from the network's own Connect&go site. The offer combines kWh + time pricing, day/night windows, a 30 kW threshold, optional 3 EUR/month subscription, and idle surcharges that apply without consumption. The network page announces 24 stations across 14 municipalities with 22/25/120 kW equipment. Freshmile is the access/service partner. Keep roaming tariffs separate.\n"
    )


if __name__ == "__main__":
    main()
