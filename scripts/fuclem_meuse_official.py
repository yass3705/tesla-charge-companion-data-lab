#!/usr/bin/env python3
"""Validate current public FUCLEM / Meuse network evidence conservatively."""
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
PORTES = "https://www.portesdemeuse.fr/transports/"
SDIRVE = "https://www.data.gouv.fr/datasets/schema-directeur-des-infrastructures-de-recharge-pour-vehicules-electriques-de-la-meuse"


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
        raise RuntimeError("FUCLEM official evidence missing: " + ", ".join(missing))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/fuclem_meuse")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    ps, praw, pfinal = fetch(PORTES)
    ds, draw, dfinal = fetch(SDIRVE)
    if ps != 200 or ds != 200:
        raise RuntimeError(f"HTTP failure portes={ps} sdirve={ds}")

    ptext = plain(praw)
    dtext = plain(draw)
    require(
        ptext,
        "VÉHICULES ÉLECTRIQUES",
        "FUCLEM",
        "Syndicat départemental des énergies de la Meuse",
        "bornes de recharges",
        "tarifs",
        "demandes de badges",
    )
    require(
        dtext,
        "Schéma Directeur des Infrastructures de Recharge pour Véhicules Electriques de la Meuse",
        "FUCLEM",
        "2026",
        "Syndicat Mixte FUCLEM",
    )

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "fuclem-meuse-official-grandest",
        "generatedAt": now(),
        "operator": "FUCLEM",
        "country": "FR",
        "region": "Grand Est",
        "department": "Meuse",
        "classification": {
            "localPublicNetwork": True,
            "departmentalEnergySyndicateNetwork": True,
            "networkExistenceValidated": True,
            "currentExactDirectConsumerTariffResolved": False,
            "directTariffClassable": False,
            "legacyTariffPointerPresent": True,
        },
        "network": {
            "authority": "Syndicat Mixte FUCLEM",
            "publicAuthorityPageConfirmsInstalledNetwork": True,
            "sdirveProducer": "Syndicat Mixte FUCLEM",
            "sdirveOperationalHorizon": 2026,
            "badgeAccessMentioned": True,
        },
        "tariff": {
            "exactCurrentAmount": None,
            "status": "unresolved_from_current_validated_official_sources",
            "note": "The current public authority page points users to FUCLEM tariff/badge information but does not expose a current exact consumer amount in the page content validated here. Do not reuse historical prices as current TCC ranking data.",
        },
        "tccDecision": {
            "operatorValidated": True,
            "directTariffClassable": False,
            "defaultDisplay": "reference_only",
            "stationTestsDeferred": True,
            "exactTariffFollowupRequired": True,
            "note": "Keep FUCLEM as a validated Meuse public network, but leave its direct price out of ranking until a current exact tariff is recovered from an authoritative live source or station flow.",
        },
        "sourceEvidence": {
            "officialOnly": True,
            "publicAuthorityUrl": pfinal,
            "publicAuthorityHttpStatus": ps,
            "publicAuthoritySha256": hashlib.sha256(praw).hexdigest(),
            "sdirveUrl": dfinal,
            "sdirveHttpStatus": ds,
            "sdirveSha256": hashlib.sha256(draw).hexdigest(),
        },
        "publicationStatus": "validated_candidate_reference_only",
    }
    sig = {k: payload[k] for k in ("classification", "network", "tariff", "tccDecision")}
    payload["sourceEvidence"]["relevantFingerprintSha256"] = hashlib.sha256(
        json.dumps(sig, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    (out / "fuclem_meuse_official_grandest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    (out / "SUMMARY.md").write_text(
        "# FUCLEM — Meuse\n\n"
        "FUCLEM is validated as the Meuse departmental public charging network. Current official/public-authority sources confirm the network and the FUCLEM-led SDIRVE horizon through 2026, but the exact current consumer direct tariff is not exposed in the validated page content. Keep the network reference-only in TCC until an authoritative exact tariff is recovered.\n"
    )


if __name__ == "__main__":
    main()
