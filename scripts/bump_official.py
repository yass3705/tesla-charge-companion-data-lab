#!/usr/bin/env python3
"""Validate current Bump France public-charging tariff rules.

Operator-rule validator only: no national station database is built.
Bump-operated station prices are site-defined and shown in the Bump app;
partner-station prices remain a separate roaming layer.
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
    "pricing": "https://help.bump-charge.com/en/articles/9811842",
    "minimumTariff": "https://help.bump-charge.com/en/articles/9811586",
    "usage": "https://help.bump-charge.com/en/articles/4104642",
    "sessionTroubleshooting": "https://help.bump-charge.com/en/articles/9237698",
    "dataGouvDataset": "https://www.data.gouv.fr/datasets/irve-statique-organisation-bump-1",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
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


def require_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    n = norm(text)
    missing = [token for token in tokens if norm(token) not in n]
    if missing:
        raise RuntimeError(f"{label}: missing markers: {', '.join(missing)}")


def require_any(text: str, phrases: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(p) in n for p in phrases):
        raise RuntimeError(f"{label}: expected evidence not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/bump")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pages: dict[str, str] = {}
    statuses: dict[str, int] = {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        pages[key] = norm(text_from_html(raw))

    pricing = pages["pricing"]
    require_tokens(pricing, ("bornes operees par bump", "bornes partenaires", "tarifs", "application"), "Bump pricing layers")
    require_any(pricing, ("tarifs sont definis par le gestionnaire du site", "tarifs sont définis par le gestionnaire du site"), "Bump direct site pricing")
    require_any(pricing, ("prix sont definis par l'operateur du reseau partenaire", "prix sont définis par l’opérateur du réseau partenaire"), "Bump roaming pricing")
    require_tokens(pricing, ("duree de recharge", "temps pendant lequel le vehicule reste branche"), "Bump duration/occupancy pricing")

    minimum = pages["minimumTariff"]
    require_tokens(minimum, ("tarif minimum", "0,50", "stationnement", "duree"), "Bump minimum tariff")
    require_any(minimum, ("n'est pas remboursable", "n’est pas remboursable"), "Bump minimum tariff non-refundable")

    usage = pages["usage"]
    require_tokens(usage, ("22 kw", "150 kw", "carte bancaire", "badge rfid"), "Bump payment and power")
    require_any(usage, ("l'application bump", "lancez votre charge avec l'application bump", "app bump"), "Bump app charging")

    troubleshooting = pages["sessionTroubleshooting"]
    require_tokens(troubleshooting, ("pre-autorisation", "15", "45"), "Bump preauthorization")

    datagouv = pages["dataGouvDataset"]
    require_tokens(datagouv, ("bornes de recharge publiques operees par bump", "mise a jour chaque jour"), "Bump data.gouv inventory")

    facts = {
        "classification": {
            "singleGuaranteedNationalCpoDirectTariff": False,
            "stationLevelPriceLookupRequiredForExactCpoDirect": True,
            "reason": "Bump states that tariffs on Bump-operated stations are defined by the site manager and displayed in the app; prices can therefore differ between stations.",
        },
        "operatorDirect": {
            "bumpOperatedStations": {
                "priceModel": "site_specific",
                "exactPriceLookupRequired": True,
                "priceDisplay": "Bump app / station display where available",
                "nationalEurPerKwh": None,
            },
            "paymentMethods": {
                "bumpApp": True,
                "bumpCardOrPass": True,
                "compatibleRfid": True,
                "bankCardDirect": True,
            },
        },
        "roaming": {
            "classification": "partner_network_eMSP_layer",
            "operatorDirect": False,
            "partnerStationsAccessible": True,
            "partnerPriceOwner": "partner network operator",
            "bumpCanModifyPartnerPrice": False,
            "exactPartnerTariffLookupRequired": True,
        },
        "fees": {
            "minimumTariff": {
                "networkWide": False,
                "status": "some_stations_only",
                "generalStartingAmountEur": 0.50,
                "canApplyWithZeroEnergyDelivered": True,
                "nonRefundableWhenApplied": True,
                "additionalFeesMayAlsoApply": ["parking", "duration"],
            },
            "durationOrOccupancy": {
                "networkWideFixedAmount": None,
                "status": "station_or_operator_specific",
                "note": "Bump explicitly warns that duration and post-charge occupancy may affect the tariff; exact conditions are shown per station.",
            },
            "parking": {
                "status": "station_or_site_specific",
            },
            "paymentPreauthorization": {
                "minEur": 15.0,
                "maxEur": 45.0,
                "stationDependent": True,
            },
        },
        "technical": {
            "representativePowerClassesMentionedByBump": [22, 150],
            "ultraFastPowerQualifier": "150_kW_and_above",
        },
        "inventory": {
            "officialDataGouvDataset": True,
            "staticInventoryOnly": True,
            "publisherSaysUpdatedDaily": True,
            "liveAvailability": False,
            "note": "The official Bump data.gouv dataset is used only as topology/freshness evidence in this validator, not to build a national station database.",
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "bump-official-france",
        "generatedAt": now_iso(),
        "operator": "Bump",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "This validator intentionally does not build a national station database.",
            "Do not invent a France-wide Bump CPO-direct kWh price: current Bump guidance says Bump-operated prices are site-defined.",
            "Partner-network pricing is a separate roaming layer and must not be treated as Bump CPO-direct pricing.",
            "The 0.50 EUR minimum tariff is not network-wide; Bump describes it as a general starting amount used by some stations.",
        ],
    }

    (out / "bump_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Bump France official check\n\n"
        "- Validation model: **operator rules only** (Powerdot/IZIVIA/Fastned style), no national station extract.\n"
        "- One guaranteed France-wide Bump CPO-direct tariff: **no**; Bump-operated prices are **site-specific** and shown in the app.\n"
        "- Partner stations: **separate roaming layer**; partner operator sets the price.\n"
        "- Payment: **Bump app / Bump pass / compatible RFID / direct bank card**.\n"
        "- Preauthorization: **15 to 45 EUR**, depending on station.\n"
        "- Minimum tariff: applies on **some stations**, generally from **0.50 EUR**; not a Bump-wide fee.\n"
        "- Duration/occupancy and parking: **station/site specific**.\n"
        "- Official Bump data.gouv inventory: **updated daily by publisher**, inventory evidence only.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
