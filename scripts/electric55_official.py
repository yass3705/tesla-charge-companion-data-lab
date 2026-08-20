#!/usr/bin/env python3
"""Validate current Electric 55 Charging (E55C) France public-charging rules.

Operator-rule validator only: no national station database is built. Current E55C
consumer ad-hoc access is separated from mobility-provider retail pricing and from
E55C's indicative wholesale rates billed to mobility operators.
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
    "tutorial": "https://www.e55c.com/tutoriel-de-recharge/",
    "faq": "https://www.e55c.com/comment-recharger-sa-voiture/",
    "dataGouv": "https://www.data.gouv.fr/api/1/datasets/caracteristiques-des-points-de-charge-pour-vehicules-electriques-electric-55-charging-e55c-ouverts-au-public/",
}

DAY_RATES = {3: 0.025, 7: 0.038, 11: 0.056, 22: 0.084}
NIGHT_RATES = {3: 0.020, 7: 0.028, 11: 0.034, 22: 0.062}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=40) as resp:
        raw = resp.read()
        ctype = resp.headers.get_content_type() or ""
        charset = resp.headers.get_content_charset() or "utf-8"
        return int(getattr(resp, "status", 200)), raw.decode(charset, errors="replace"), ctype


def text_from_html(raw: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def require_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    n = norm(text)
    missing = [token for token in tokens if norm(token) not in n]
    if missing:
        raise RuntimeError(f"{label}: missing markers: {', '.join(missing)}")


def require_amount(text: str, amount: float, label: str) -> None:
    n = norm(text)
    forms = {
        f"{amount:.3f}", f"{amount:.3f}".replace(".", ","),
        f"{amount:.2f}", f"{amount:.2f}".replace(".", ","),
    }
    if not any(re.search(rf"(?<!\d){re.escape(v)}(?!\d)", n) for v in forms):
        raise RuntimeError(f"{label}: amount {amount:.3f} not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/electric55")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pages: dict[str, str] = {}
    statuses: dict[str, int] = {}
    content_types: dict[str, str] = {}
    for key, url in SOURCES.items():
        status, raw, ctype = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        content_types[key] = ctype
        if "json" in ctype or key == "dataGouv":
            pages[key] = raw
        else:
            pages[key] = text_from_html(raw)

    tutorial = norm(pages["tutorial"])
    require_tokens(
        tutorial,
        (
            "payez a l'acte par carte bancaire",
            "sans inscription",
            "sans application",
            "sans badge",
            "le tarif applicable vous est presente avant validation du paiement",
        ),
        "E55C current ad-hoc consumer access",
    )
    require_tokens(
        tutorial,
        (
            "application de mobilite",
            "le prix affiche et facture peut varier selon l'operateur utilise",
            "prix ttc factures par e55c aux operateurs de mobilite",
            "ne prejuguent pas du tarif final applique a l'utilisateur",
        ),
        "E55C mobility-provider/wholesale separation",
    )
    require_tokens(tutorial, ("de jour", "entre 7h et 23h", "de nuit", "entre 23h et 7h"), "E55C time bands")
    for rate in list(DAY_RATES.values()) + list(NIGHT_RATES.values()):
        require_amount(tutorial, rate, "E55C indicative operator tariff grid")

    faq = norm(pages["faq"])
    require_tokens(faq, ("type 2", "badge", "application"), "E55C FAQ access/connector guidance")
    legacy_conflict = (
        "ne propose pas de facturation directe" in faq
        and "paiement par carte bancaire n'est donc pas directement autorise" in faq
    )

    meta = json.loads(pages["dataGouv"])
    if norm((meta.get("organization") or {}).get("name", "")) != "electric 55 charging":
        raise RuntimeError("data.gouv: Electric 55 Charging organisation marker missing")
    resources = meta.get("resources") or []
    static_resources = [r for r in resources if (r.get("schema") or {}).get("name") == "etalab/schema-irve-statique"]
    dynamic_resources = [r for r in resources if (r.get("schema") or {}).get("name") == "etalab/schema-irve-dynamique"]
    if not static_resources:
        raise RuntimeError("data.gouv: no official E55C static IRVE resource found")

    facts = {
        "classification": {
            "singleGuaranteedNationalConsumerDirectTariff": False,
            "exactAdHocConsumerPriceLookupRequired": True,
            "reason": "E55C's current charging tutorial states that the applicable ad-hoc bank-card price is displayed before payment; no single nationwide consumer amount is published there.",
        },
        "operatorDirect": {
            "adHocBankCard": {
                "available": True,
                "accountRequired": False,
                "appRequired": False,
                "badgeRequired": False,
                "priceDisplayedBeforePayment": True,
                "exactPriceLookupRequired": True,
                "nationalConsumerEurPerKwh": None,
                "nationalConsumerEurPerMinute": None,
            },
        },
        "mobilityProviders": {
            "compatibleAppOrBadge": True,
            "consumerRetailPriceMayVaryByMobilityProvider": True,
            "examplesPublishedByE55C": ["Plugsurfing", "OVO Charge", "Monta Charge"],
            "exactRetailPriceAuthority": "selected mobility provider/app",
        },
        "indicativeWholesaleTariffsToMobilityOperators": {
            "consumerTariff": False,
            "billingUnit": "EUR/minute",
            "dayWindow": "07:00-23:00",
            "nightWindow": "23:00-07:00",
            "dayEurPerMinuteByPowerKw": {str(k): v for k, v in DAY_RATES.items()},
            "nightEurPerMinuteByPowerKw": {str(k): v for k, v in NIGHT_RATES.items()},
            "note": "E55C explicitly says these TTC amounts are billed to mobility operators and do not determine the final user price.",
        },
        "fees": {
            "networkWideIdleOrOccupancyFee": None,
            "parking": {"status": "not_asserted_network_wide_from_current_general_sources"},
            "note": "Any additional direct-session, occupancy or site parking rule must be resolved from the pre-payment station flow or another explicit site source.",
        },
        "technical": {
            "currentPublishedTariffReferencePowerClassesKw": [3, 7, 11, 22],
            "faqConnectorGuidance": "Type 2 cable",
        },
        "sourceConflict": {
            "legacyFaqContradictsCurrentAdHocFlow": legacy_conflict,
            "legacyFaqStatement": "FAQ says E55C does not offer direct billing and direct bank-card payment is not authorised on the network.",
            "currentTutorialStatement": "Current tutorial offers pay-as-you-go bank-card charging without registration, app or badge and shows the tariff before payment.",
            "resolution": "Use the current operational tutorial for present ad-hoc access; retain the FAQ contradiction as a monitored stale-content signal.",
        },
        "inventory": {
            "officialDataGouvDataset": True,
            "officialStaticIrveResource": True,
            "officialDynamicIrveResourcePresent": bool(dynamic_resources),
            "datasetLastUpdate": meta.get("last_update"),
            "nationalStationDatabaseBuiltByThisValidator": False,
            "note": "Official E55C data.gouv resources are used only as network/inventory evidence in this operator-rule validator.",
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "electric55-official-france",
        "generatedAt": now_iso(),
        "operator": "Electric 55 Charging (E55C)",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [
                {"key": k, "url": u, "httpStatus": statuses[k], "contentType": content_types[k]}
                for k, u in SOURCES.items()
            ],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "This validator intentionally does not build a national station database.",
            "Do not use E55C's indicative operator wholesale minute rates as the final Charge Companion consumer tariff.",
            "For direct ad-hoc bank-card charging, resolve the exact station/session price from E55C's pre-payment flow.",
            "The contradictory legacy FAQ is preserved as monitored evidence rather than silently overriding the current ad-hoc flow.",
        ],
    }

    (out / "electric55_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Electric 55 Charging France official check\n\n"
        "- Validation model: **operator rules only**, no national station extract.\n"
        "- Current ad-hoc access: **bank card, no account/app/badge required**; exact tariff is shown before payment.\n"
        "- Therefore no single France-wide direct consumer tariff is asserted.\n"
        "- Mobility-provider retail prices can differ by provider.\n"
        "- E55C publishes indicative **wholesale** minute rates to mobility operators: day 07:00-23:00 and night 23:00-07:00, for 3/7/11/22 kW; these are **not consumer tariffs**.\n"
        f"- Legacy FAQ conflict detected: **{'yes' if legacy_conflict else 'no'}**.\n"
        "- Official E55C data.gouv static IRVE resource confirmed; dynamic resource presence is tracked only as inventory evidence.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
