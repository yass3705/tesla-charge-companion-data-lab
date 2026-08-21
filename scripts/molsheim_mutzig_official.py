#!/usr/bin/env python3
"""Validate current official CCRMM / Molsheim-Mutzig public charging tariffs."""
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
OFFICIAL = "https://www.cc-molsheim-mutzig.fr/bornes-de-recharge-pour-vehicules-electriques.htm"


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
        raise RuntimeError("CCRMM official evidence missing: " + ", ".join(missing))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/molsheim_mutzig")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    status, raw, final = fetch(OFFICIAL)
    if status != 200:
        raise RuntimeError(f"HTTP failure official={status}")
    text = plain(raw)

    require(
        text,
        "Délibération du Conseil Communautaire du 5 février 2026",
        "Tarif unique",
        "0,38 € / kWh entamé",
        "Zones denses",
        "au delà de 6h30 après le début de la charge",
        "0,40 € / 15 min",
        "Zones non denses",
        "au delà de 14h30 après le début de la charge",
        "FRESHMILE",
    )

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "molsheim-mutzig-official-grandest",
        "generatedAt": now(),
        "operator": "Communauté de Communes de la Région de Molsheim-Mutzig",
        "serviceOperator": "Freshmile",
        "country": "FR",
        "region": "Grand Est",
        "department": "Bas-Rhin",
        "classification": {
            "localPublicNetwork": True,
            "directPublishedTariff": True,
            "energyBased": True,
            "startedKwhBilling": True,
            "idleSurcharge": True,
            "idleThresholdDependsOnZone": True,
            "roamingMayDiffer": True,
        },
        "operatorDirect": {
            "energy": {
                "eurPerStartedKwh": 0.38,
                "billingIncrementKwh": 1.0,
                "rounding": "ceiling_each_started_kwh",
            },
            "idle": {
                "denseZones": {
                    "thresholdAfterChargeStartMinutes": 390,
                    "eurPer15MinutesWithoutEnergy": 0.40,
                    "publishedExamples": ["Molsheim-Jésuites", "Molsheim-Rue des Sports", "Mutzig-Mairie", "Dorlisheim"],
                },
                "nonDenseZones": {
                    "thresholdAfterChargeStartMinutes": 870,
                    "eurPer15MinutesWithoutEnergy": 0.40,
                },
            },
        },
        "tccDecision": {
            "operatorValidated": True,
            "directTariffClassable": True,
            "startedKwhRoundingMustBeModeled": True,
            "idleFeeMustBeModeled": True,
            "roamingSeparate": True,
            "stationTestsDeferred": True,
            "note": "Preserve the official 'kWh entamé' rule and 15-minute idle blocks; do not silently convert them to continuous billing.",
        },
        "sourceEvidence": {
            "officialOnly": True,
            "officialUrl": final,
            "officialHttpStatus": status,
            "officialSha256": hashlib.sha256(raw).hexdigest(),
            "officialTariffDecisionDate": "2026-02-05",
        },
        "publicationStatus": "validated_candidate",
    }

    sig = {k: payload[k] for k in ("classification", "operatorDirect", "tccDecision")}
    payload["sourceEvidence"]["relevantTariffFingerprintSha256"] = hashlib.sha256(
        json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    (out / "molsheim_mutzig_official_grandest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (out / "SUMMARY.md").write_text(
        "# CCRMM / Molsheim-Mutzig\n\n"
        "Official 5 February 2026 tariff validated: 0.38 EUR per started kWh. When no energy is delivered, dense-zone sites add 0.40 EUR per 15 min after 6h30 from charge start; non-dense sites add the same block fee after 14h30. Freshmile is the service operator. Preserve started-kWh and 15-minute block billing exactly.\n"
    )


if __name__ == "__main__":
    main()
