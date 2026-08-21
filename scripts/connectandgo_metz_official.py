#!/usr/bin/env python3
"""Validate current official Connect&go Euro-Métropole de Metz tariff rules."""
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
TARIFFS = "https://eurometropolemetz.connectandgo.fr/tarifs/"
HOME = "https://eurometropolemetz.connectandgo.fr/"


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
        raise RuntimeError("Connect&go Metz official evidence missing: " + ", ".join(missing))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/connectandgo_metz")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    hs, hraw, hfinal = fetch(HOME)
    ts, traw, tfinal = fetch(TARIFFS)
    if hs != 200 or ts != 200:
        raise RuntimeError(f"HTTP failure home={hs} tariffs={ts}")

    htext = plain(hraw)
    ttext = plain(traw)
    require(htext, "Euro-Métropole", "22 kW", "25 kW", "120 kW", "Freshmile")
    require(
        ttext,
        "SANS ABONNEMENT",
        "0€ /mois",
        "De 8h30 à 20h : 0,29 € par kWh entamé et 0,029 € par minute",
        "0,495 € par kWh entamé et 0,029 € par minute",
        "après 4h de branchement, 0,16 € par minute sans consommation",
        "après 1h30 de branchement, 0,20 € par minute sans consommation",
        "De 20h à 8h30 : 0,28 € par kWh entamé",
        "AVEC ABONNEMENT",
        "3€ /mois",
        "De 9h à 20h : 0,27 € par kWh entamé et 0,025 € par minute",
        "0,47 € par kWh entamé et 0,025 € par minute",
        "après 4h de branchement, 0,13 € par minute sans consommation",
        "après 1h30 de branchement, 0,15€ par minute de branchement sans consommation",
        "De 20h à 9h : 0,23 € par kWh entamé",
        "La tarification continue tant que le véhicule est branché",
    )

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "connectandgo-metz-official-grandest",
        "generatedAt": now(),
        "operator": "Connect&go - Euro-Métropole de Metz",
        "serviceOperator": "Freshmile",
        "country": "FR",
        "region": "Grand Est",
        "department": "Moselle",
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
            "publishedConnectorPowerKw": [22, 25, 120],
            "freshmileAccess": True,
        },
        "operatorDirect": {
            "withoutSubscription": {
                "monthlyEur": 0.0,
                "day": {
                    "window": "08:30-20:00",
                    "upTo25Kw": {"eurPerKwh": 0.29, "eurPerMinute": 0.029},
                    "above25Kw": {"eurPerKwh": 0.495, "eurPerMinute": 0.029},
                },
                "night": {
                    "window": "20:00-08:30",
                    "upTo25Kw": {"eurPerKwh": 0.28, "eurPerMinute": 0.0},
                    "above25Kw": {"eurPerKwh": 0.495, "eurPerMinute": 0.029},
                },
                "idle": {
                    "upTo25Kw": {"afterMinutes": 240, "eurPerMinute": 0.16, "condition": "without_consumption"},
                    "above25Kw": {"afterMinutes": 90, "eurPerMinute": 0.20, "condition": "without_consumption"},
                },
            },
            "withSubscription": {
                "monthlyEur": 3.0,
                "day": {
                    "window": "09:00-20:00",
                    "upTo25Kw": {"eurPerKwh": 0.27, "eurPerMinute": 0.025},
                    "above25Kw": {"eurPerKwh": 0.47, "eurPerMinute": 0.025},
                },
                "night": {
                    "window": "20:00-09:00",
                    "upTo25Kw": {"eurPerKwh": 0.23, "eurPerMinute": 0.0},
                    "above25Kw": {"eurPerKwh": 0.47, "eurPerMinute": 0.025},
                },
                "idle": {
                    "upTo25Kw": {"afterMinutes": 240, "eurPerMinute": 0.13, "condition": "without_consumption"},
                    "above25Kw": {"afterMinutes": 90, "eurPerMinute": 0.15, "condition": "without_consumption"},
                },
            },
        },
        "rules": {
            "billingContinuesWhileVehicleConnected": True,
            "lowPowerNightIdleStartsWhenDayHoursResumeIfFullyCharged": True,
            "tariffThresholdLabel": "25 kW",
        },
        "tccDecision": {
            "operatorValidated": True,
            "directTariffClassable": True,
            "subscriptionSeparateOffer": True,
            "roamingSeparate": True,
            "idleFeeMustBeModeled": True,
            "note": "Use Connect&go Euro-Métropole de Metz as a local direct Freshmile-backed offer; keep subscription and roaming prices as separate tariff variants.",
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

    (out / "connectandgo_metz_official_grandest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    (out / "SUMMARY.md").write_text(
        "# Connect&go — Euro-Métropole de Metz\n\n"
        "Official public tariff validated from the network's own Connect&go site. The offer combines kWh + time pricing, day/night windows, power tiers, optional 3 EUR/month subscription, and idle surcharges. Freshmile is the access/service partner. Keep roaming tariffs separate.\n"
    )


if __name__ == "__main__":
    main()
