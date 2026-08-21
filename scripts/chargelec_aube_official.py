#!/usr/bin/env python3
"""Validate current official SDEA Chargelec Aube public charging tariffs."""
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
SERVICE = "https://chargelec.sde-aube.fr/"
SDEA = "https://www.sde-aube.fr/au-service-des-collectivites-et-des-aubois/la-transition-energetique"


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
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def require(text: str, *items: str):
    n = norm(text)
    missing = [x for x in items if norm(x) not in n]
    if missing:
        raise RuntimeError("Chargelec Aube official evidence missing: " + ", ".join(missing))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/chargelec_aube")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # The branded Chargelec portal is dynamic and its server-side HTML can omit
    # the visible tariff text. Keep it as a reachability/source fingerprint, but
    # validate tariff values against SDEA's own current authority page.
    ss, sraw, sfinal = fetch(SERVICE)
    as_, araw, afinal = fetch(SDEA)
    if ss != 200 or as_ != 200:
        raise RuntimeError(f"HTTP failure service={ss} sdea={as_}")

    authority = plain(araw)
    require(
        authority,
        "Plus de 180 bornes de recharge accélérée 22 kVA",
        "quatorze bornes de recharge rapide (50 kVA)",
        "utilisateur abonné",
        "2 € l’unité",
        "2,5 € l’unité",
        "utilisateur occasionnel",
        "3 € l’unité",
        "6 kWh",
    )

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "chargelec-aube-official-grandest",
        "generatedAt": now(),
        "operator": "Chargelec - SDEA Aube",
        "country": "FR",
        "region": "Grand Est",
        "department": "Aube",
        "classification": {
            "localPublicNetwork": True,
            "directPublishedTariff": True,
            "energyUnitBased": True,
            "powerDependentForSubscriber": True,
            "adHocAvailable": True,
            "roamingAvailable": True,
        },
        "network": {
            "publishedAcceleratedStations22Kva": 180,
            "publishedRapidStations50Kva": 14,
            "subscriberAccess": True,
            "occasionalSmartphoneAccess": True,
            "roamingAccess": True,
        },
        "billingUnit": {
            "energyKwhPerUnit": 6.0,
            "note": "Official consumer tariff is sold/billed in 6 kWh units; preserve the unit structure instead of silently converting it to continuous per-kWh billing.",
        },
        "operatorDirect": {
            "subscriber": {
                "upTo36Kva": {"eurPer6KwhUnit": 2.0, "nominalEurPerKwh": round(2.0 / 6.0, 6)},
                "above36Kva": {"eurPer6KwhUnit": 2.5, "nominalEurPerKwh": round(2.5 / 6.0, 6)},
            },
            "adHoc": {
                "allPowers": {"eurPer6KwhUnit": 3.0, "nominalEurPerKwh": round(3.0 / 6.0, 6)},
                "accountRequired": False,
                "smartphoneAccess": True,
            },
        },
        "tccDecision": {
            "operatorValidated": True,
            "tariffClassableWithUnitBillingSupport": True,
            "continuousPerKwhApproximationForRanking": False,
            "roamingSeparate": True,
            "stationTestsDeferred": True,
            "note": "Use exact 6 kWh unit prices. Nominal €/kWh values are informational only and must not replace the official unit-based billing model.",
        },
        "sourceEvidence": {
            "officialOnly": True,
            "servicePortal": {
                "url": sfinal,
                "httpStatus": ss,
                "sha256": hashlib.sha256(sraw).hexdigest(),
                "tariffTextBlockingValidation": False,
                "note": "Dynamic portal HTML is not used as the blocking tariff authority in CI.",
            },
            "authority": {
                "url": afinal,
                "httpStatus": as_,
                "sha256": hashlib.sha256(araw).hexdigest(),
                "tariffTextBlockingValidation": True,
            },
        },
        "publicationStatus": "validated_candidate",
    }
    sig = {k: payload[k] for k in ("network", "billingUnit", "operatorDirect", "tccDecision")}
    payload["sourceEvidence"]["relevantTariffFingerprintSha256"] = hashlib.sha256(
        json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    (out / "chargelec_aube_official_grandest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (out / "SUMMARY.md").write_text(
        "# Chargelec — SDEA Aube\n\n"
        "Official SDEA tariff validated. Subscriber pricing is 2 EUR per 6 kWh unit up to 36 kVA and 2.50 EUR per 6 kWh unit above 36 kVA; occasional smartphone charging is 3 EUR per 6 kWh unit at all powers. Preserve the official 6 kWh unit billing rather than converting it into continuous kWh pricing.\n"
    )


if __name__ == "__main__":
    main()
