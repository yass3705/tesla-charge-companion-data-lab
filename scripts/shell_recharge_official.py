#!/usr/bin/env python3
"""Validate current Shell Recharge France public-charging tariff rules.

Operator-rule validator only: no national station database is built. Stable
Shell France support articles are used for automated payment, uniform-fast-rate,
preauthorization and roaming rules. Rendered first-party station pages are kept
as representative price samples because their EV tariff blocks are client-rendered.
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
    "uniformFastRate": "https://support.shell.fr/hc/fr-fr/articles/40801882587409-Le-prix-par-kWh-est-il-le-m%C3%AAme-%C3%A0-toutes-les-bornes-rapides-Shell-Recharge",
    "payment": "https://support.shell.fr/hc/fr-fr/articles/46950711091729-Quels-sont-les-moyens-de-paiement-pour-recharger-avec-Shell-Recharge",
    "preauthorization": "https://support.shell.fr/hc/fr-fr/articles/41384776749457-Montant-de-pr%C3%A9-autorisation",
    "roamingCost": "https://support.shell.fr/hc/fr-fr/articles/40801847438225-Combien-co%C3%BBte-la-recharge-avec-la-carte-Shell-Recharge-sur-d-autres-bornes",
    "directCost": "https://support.shell.fr/hc/fr-fr/articles/40801845990161-Combien-co%C3%BBte-la-recharge-rapide-aux-bornes-Shell-Recharge-dans-les-stations-Shell",
    "sommesous": "https://find.shell.com/fr/fuel/10029225-sommesous-a26/fr_TN",
    "roussillon": "https://find.shell.com/fr/fuel/12166202-roussillon-a7/fr_TN",
    "cestas": "https://find.shell.com/fr/fuel/10029643-cestas-ouest-a63/fr_MA",
    "lesSalles": "https://find.shell.com/fr/fuel/11796090-les-salles-haut-forez-nord-a89/fr_LU",
    "criquetot": "https://find.shell.com/fr/fuel/13078456-ev-criquetot-le-havre/fr_FR",
}

REPRESENTATIVE_RENDERED_SAMPLES = [
    {"key": "sommesous", "shellAppEurPerKwh": 0.64, "sessionFeeEur": 0.35, "powerKwObserved": [150, 300]},
    {"key": "roussillon", "shellAppEurPerKwh": 0.64, "sessionFeeEur": 0.35, "powerKwObserved": [300]},
    {"key": "cestas", "shellAppEurPerKwh": 0.64, "sessionFeeEur": 0.35, "powerKwObserved": [300]},
    {"key": "lesSalles", "shellAppEurPerKwh": 0.64, "sessionFeeEur": 0.35, "powerKwObserved": [50, 300]},
    {"key": "criquetot", "shellAppEurPerKwh": 0.64, "sessionFeeEur": 0.35, "powerKwObserved": [300]},
]

STATION_KEYS = {x["key"] for x in REPRESENTATIVE_RENDERED_SAMPLES}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    })
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
    return re.sub(r"\s+", " ", s.lower().replace("’", "'")).strip()


def require_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    n = norm(text)
    missing = [token for token in tokens if norm(token) not in n]
    if missing:
        raise RuntimeError(f"{label}: missing markers: {', '.join(missing)}")


def require_amount(text: str, amount: float, label: str) -> None:
    n = norm(text)
    candidates = {f"{amount:g}", f"{amount:.2f}", f"{amount:.2f}".replace(".", ",")}
    if not any(re.search(rf"(?<!\d){re.escape(v)}(?!\d)", n) for v in candidates):
        raise RuntimeError(f"{label}: amount {amount:g} not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/shell_recharge")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    statuses = {}
    pages = {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        pages[key] = norm(text_from_html(raw))

    uniform = pages["uniformFastRate"]
    require_tokens(uniform, ("meme tarif", "toutes les bornes rapides shell recharge", "carte shell recharge", "application shell"), "Shell uniform fast-rate rule")

    direct = pages["directCost"]
    require_tokens(direct, ("tarif avantageux", "reseau shell recharge", "aucun frais d'abonnement", "carte shell recharge"), "Shell direct-network cost rule")

    payment = pages["payment"]
    require_tokens(payment, ("application shell", "carte shell recharge", "qr code", "carte bancaire sans contact", "apple pay", "google pay"), "Shell payment methods")

    pre = pages["preauthorization"]
    require_tokens(pre, ("montant provisoire", "carte de recharge shell recharge", "application shell", "carte bancaire"), "Shell preauthorization")
    require_amount(pre, 45.0, "Shell app/card preauthorization")
    require_amount(pre, 65.0, "Shell bank-card preauthorization")

    roaming = pages["roamingCost"]
    require_tokens(roaming, ("bornes autres que shell recharge", "tarifs des operateurs de borne", "frais de transaction", "0,35"), "Shell roaming price rule")

    facts = {
        "classification": {
            "singleNationalFastShellRechargeCardTariffRule": True,
            "exactCurrentKwhAmountAutoExtracted": False,
            "stationLevelLookupRecommendedForNonShellCardOrRoaming": True,
            "reason": "Shell explicitly states that Shell Recharge card users pay the same tariff at all Shell Recharge fast chargers; the current numeric kWh tariff is exposed on the tariff/app or rendered station layer.",
        },
        "operatorDirect": {
            "fastShellRechargeWithShellCard": {
                "uniformAcrossFastShellRechargeStations": True,
                "representativeCurrentEurPerKwh": 0.64,
                "representativePriceStatus": "observed_on_rendered_first_party_station_pages_2026-08-20",
                "monthlySubscriptionFeeEur": 0.0,
                "cardOrderFeeEur": 0.0,
            },
            "renderedFirstPartySamples": {
                "count": len(REPRESENTATIVE_RENDERED_SAMPLES),
                "allObservedEurPerKwh": 0.64,
                "allObservedSessionFeeEur": 0.35,
                "powerClassesKw": [50, 150, 300],
            },
        },
        "payment": {
            "shellApp": True,
            "shellRechargeCard": True,
            "adHocQrOnline": True,
            "contactlessBankCardFastChargers": True,
            "applePayFastChargers": True,
            "googlePayFastChargers": True,
            "preauthorization": {
                "shellCardOrAppEur": 45.0,
                "bankCardEur": 65.0,
                "temporaryReservation": True,
            },
        },
        "fees": {
            "representativeShellAppSessionFeeEur": 0.35,
            "networkWideIdleFee": None,
            "parking": {"status": "site_specific_unless_explicitly_published"},
        },
        "roaming": {
            "classification": "partner_cpo_layer",
            "operatorDirect": False,
            "partnerCpoTariffApplies": True,
            "shellTransactionFeePerSessionEur": 0.35,
            "exactPartnerPriceLookupRequired": True,
            "priceDisplay": "Shell app / tariff layer",
        },
        "representativeStationChecks": REPRESENTATIVE_RENDERED_SAMPLES,
        "technical": {
            "representativePowerClassesKw": [50, 150, 300],
            "stationPagesReachable": all(statuses[k] == 200 for k in STATION_KEYS),
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.2.0",
        "dataset": "shell-recharge-official-france",
        "generatedAt": now_iso(),
        "operator": "Shell Recharge",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "automatedRuleSources": ["uniformFastRate", "directCost", "payment", "preauthorization", "roamingCost"],
            "representativeStationTariffsCapturedFromRenderedFirstPartyPagesOn": "2026-08-20",
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "This validator intentionally does not build a national station database.",
            "Shell's official support confirms a uniform tariff rule for Shell Recharge card users across fast Shell Recharge stations.",
            "The current 0.64 EUR/kWh value is retained from five rendered first-party Shell station samples; automated plain-HTML checks validate the rule layer rather than client-rendered numeric tariff blocks.",
            "Roaming remains separate: partner CPO tariff plus Shell transaction fee.",
        ],
    }

    (out / "shell_recharge_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# Shell Recharge France official check\n\n"
        "- Validation model: **operator rules only**, no national station extract.\n"
        "- Shell Recharge card: official support confirms **the same tariff at all fast Shell Recharge stations**.\n"
        "- Current representative first-party sample: **0.64 EUR/kWh** across 5 sites (50/150/300 kW).\n"
        "- Representative rendered station session fee: **0.35 EUR**.\n"
        "- No subscription fee; Shell Recharge card order is free.\n"
        "- Payment: **app/card, QR ad hoc, contactless bank card, Apple Pay, Google Pay**.\n"
        "- Preauthorization: **45 EUR app/Shell card; 65 EUR bank card**.\n"
        "- Roaming: **partner CPO tariff + 0.35 EUR/session Shell transaction fee**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
