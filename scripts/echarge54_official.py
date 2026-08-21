#!/usr/bin/env python3
"""Validate current eCharge54 / SDE54 public charging tariff groups."""
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
SERVICE = "https://www.electromaps.com/fr/partenaires/citeos/meurthe-et-moselle"
AUTHORITY = "https://www.sde54.fr/fr/irve-bornes-de-recharge.html"
DATASET = "https://www.data.gouv.fr/datasets/sde54-1"


def fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "fr-FR,fr;q=0.9"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(getattr(r, "status", 200)), r.read(), r.geturl()


def plain(raw: bytes) -> str:
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " ")).strip()


def norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def require(text: str, *items: str):
    n = norm(text)
    missing = [x for x in items if norm(x) not in n]
    if missing:
        raise RuntimeError("eCharge54 evidence missing: " + ", ".join(missing))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/echarge54")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    ss, sraw, sfinal = fetch(SERVICE)
    as_, araw, afinal = fetch(AUTHORITY)
    ds, draw, dfinal = fetch(DATASET)
    if ss != 200 or as_ != 200 or ds != 200:
        raise RuntimeError(f"HTTP failure service={ss} authority={as_} dataset={ds}")

    service = plain(sraw)
    authority = plain(araw)
    dataset = plain(draw)

    require(service, "eCharge54", "plus de 120 stations", "LES TARIFS DE RECHARGE")
    require(service, "Station normale (jusqu'à 22kW AC)", "0,20€", "Station haute puissance (supérieur à 25 kW DC)", "0,40€")
    require(service, "0,50€ / 30 minutes", "0,4 € / kwh + 0,07 € / min à partir de 4h de branchement", "hors de 20h à 8h")
    require(service, "Tarif itinérant", "ne tient pas compte des coûts éventuels de service appliqués en sus par votre opérateur de mobilité")
    require(authority, "Schéma Directeur des Infrastructures de Recharge", "SDE54", "Meurthe-et-Moselle")
    require(dataset, "eCharge54", "plus de 120 stations", "Meurthe & Moselle")

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "echarge54-official-grandest",
        "generatedAt": now(),
        "operator": "eCharge54 - SDE54",
        "serviceOperator": "Citeos / Electromaps",
        "country": "FR",
        "region": "Grand Est",
        "department": "Meurthe-et-Moselle",
        "classification": {
            "departmentalPublicNetwork": True,
            "directPublishedTariffs": True,
            "multipleLocalTariffGroups": True,
            "energyBased": True,
            "timeBased": True,
            "mixedEnergyTimeTariff": True,
            "roamingMayAddFees": True,
            "stationScopeRequired": True,
        },
        "network": {
            "publishedStationsAtLeast": 120,
            "territory": "Meurthe-et-Moselle",
            "sdirveValidatedByAuthority": True,
        },
        "operatorDirect": {
            "cd54": {
                "scopeLabel": "CD54",
                "normalAcUpTo22Kw": {"eurPerKwh": 0.20},
                "highPowerDcAbove25Kw": {"eurPerKwh": 0.40},
                "sameBasePriceSubscriberAdHocRoaming": True,
            },
            "groupTime30Min": {
                "publishedScopes": ["CCCPH", "CCMM", "CCPCST", "Heillecourt", "Ville de Nancy", "T2L"],
                "normalAcUpTo22Kw": {"eurPer30Minutes": 0.50, "blockMinutes": 30},
                "publishedCapHours": 4.0,
            },
            "groupMixed": {
                "publishedScopes": ["Blénod-lès-Pont-à-Mousson", "CCBP", "CCPS", "CCTLB", "CCTT", "Dieulouard", "PETR", "SDE54"],
                "normalAcUpTo22Kw": {
                    "eurPerKwh": 0.40,
                    "idleAfterConnectionMinutes": 240,
                    "idleEurPerStartedMinute": 0.07,
                    "idleActiveLocalTime": {"start": "08:00", "end": "20:00"},
                },
            },
        },
        "roaming": {
            "baseNetworkTariffPublishedSame": True,
            "emspServiceFeesMayBeAdded": True,
        },
        "tccDecision": {
            "operatorValidated": True,
            "directTariffClassable": True,
            "requiresStationTariffGroupMapping": True,
            "thirtyMinuteBlocksMustBeModeled": True,
            "startedMinuteIdleMustBeModeled": True,
            "roamingSeparate": True,
            "stationTestsDeferred": True,
            "note": "Do not apply one universal eCharge54 tariff. Select the published local tariff group for the station, preserve 30-minute blocks and the 0.07 EUR started-minute idle rule where applicable, and keep eMSP surcharges separate.",
        },
        "sourceEvidence": {
            "serviceTariffUrl": sfinal,
            "serviceTariffHttpStatus": ss,
            "serviceTariffSha256": hashlib.sha256(sraw).hexdigest(),
            "sde54AuthorityUrl": afinal,
            "sde54AuthorityHttpStatus": as_,
            "sde54AuthoritySha256": hashlib.sha256(araw).hexdigest(),
            "dataGouvOperatorDatasetUrl": dfinal,
            "dataGouvOperatorDatasetHttpStatus": ds,
            "dataGouvOperatorDatasetSha256": hashlib.sha256(draw).hexdigest(),
            "sourceModel": "public-authority + operator-published service tariff + operator data.gouv dataset",
        },
        "publicationStatus": "validated_candidate",
    }

    sig = {k: payload[k] for k in ("classification", "operatorDirect", "roaming", "tccDecision")}
    payload["sourceEvidence"]["relevantTariffFingerprintSha256"] = hashlib.sha256(
        json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    (out / "echarge54_official_grandest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (out / "SUMMARY.md").write_text(
        "# eCharge54 / SDE54\n\n"
        "Current public eCharge54 tariff page validated with SDE54 authority and operator dataset context. The network has multiple local tariff groups: CD54 at 0.20 EUR/kWh AC up to 22 kW and 0.40 EUR/kWh DC above 25 kW; a 0.50 EUR/30-minute AC group for CCCPH/CCMM/CCPCST/Heillecourt/Nancy/T2L; and a mixed 0.40 EUR/kWh + 0.07 EUR per started minute after 4 hours (08:00-20:00 only) group for the listed SDE54 local scopes. Roaming base prices are published the same but eMSP service fees may be added. Station-to-group mapping is mandatory before ranking.\n"
    )


if __name__ == "__main__":
    main()
