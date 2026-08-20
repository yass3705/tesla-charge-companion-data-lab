#!/usr/bin/env python3
"""Validate current Shell Recharge France public-charging tariff rules.

Operator-rule validator only: no national station database is built. The stable
France tariff page is the automated source of truth for payment/roaming rules.
Rendered first-party station pages are retained as representative current price
samples because their EV tariff blocks are client-rendered and not present in
plain urllib HTML.
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
    "franceTariffs": "https://www.shell.fr/recharge-electrique/tarifs-de-shell-recharge.html",
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
    forms = {f"{amount:.2f}", f"{amount:.2f}".replace(".", ",")}
    if not any(re.search(rf"(?<!\d){re.escape(v)}(?!\d)", n) for v in forms):
        raise RuntimeError(f"{label}: amount {amount:.2f} not found")


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

    national = pages["franceTariffs"]
    require_tokens(
        national,
        ("s'appliquent au reseau shell recharge en france", "application shell", "carte bancaire sans contact", "paiement en ligne"),
        "Shell France direct-network tariff/payment rules",
    )
    require_amount(national, 0.35, "Shell France transaction fee")
    require_tokens(national, ("45", "65", "montant provisoire"), "Shell France preauthorization")
    require_tokens(
        national,
        ("bornes de recharge non shell", "tarif applique par le cpo", "commission fixe", "frais de blocage"),
        "Shell France roaming rules",
    )
    require_tokens(national, ("prix par kwh pour chaque point de recharge", "details des tarifs par point de recharge"), "Shell per-point price lookup")

    facts = {
        "classification": {
            "singleGuaranteedNationalCpoDirectKwhTariff": False,
            "stationLevelPriceLookupRequiredForExactCpoDirect": True,
            "reason": "Shell France states that the applicable prices and exact session details are available per charging point in the Shell app.",
        },
        "operatorDirect": {
            "shellRechargeFranceNetwork": {
                "monthlyFixedFeeEur": 0.0,
                "priceLookup": "Shell app per charging point",
                "representativeCurrentShellAppEurPerKwh": 0.64,
                "representativeSampleCount": len(REPRESENTATIVE_RENDERED_SAMPLES),
                "representativePriceStatus": "observed_on_rendered_first_party_station_pages_2026-08-20_not_promoted_as_universal",
            },
        },
        "payment": {
            "shellRechargeCard": True,
            "shellApp": True,
            "partnerChargingCard": True,
            "contactlessBankCard": True,
            "onlinePortal": True,
            "preauthorization": {
                "shellCardOrAppEur": 45.0,
                "bankCardEur": 65.0,
            },
        },
        "fees": {
            "shellRechargeCardTransactionFeeEur": 0.35,
            "exactSessionFeeDetailLookup": "Shell app",
            "networkWideIdleFee": None,
            "parking": {"status": "site_specific_unless_explicitly_published"},
        },
        "roaming": {
            "classification": "partner_cpo_layer",
            "operatorDirect": False,
            "partnerCpoTariffApplies": True,
            "shellCommissionPerTransactionEur": 0.35,
            "partnerBlockingFeeMayApply": True,
            "exactPartnerPriceLookupRequired": True,
            "priceDisplay": "Shell app per charging point",
        },
        "representativeStationChecks": REPRESENTATIVE_RENDERED_SAMPLES,
        "technical": {
            "representativePowerClassesKw": [50, 150, 300],
            "stationPagesReachable": all(statuses[k] == 200 for k in SOURCES if k != "franceTariffs"),
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.1.0",
        "dataset": "shell-recharge-official-france",
        "generatedAt": now_iso(),
        "operator": "Shell Recharge",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "automatedRuleSource": "Shell France tariff page",
            "representativeStationTariffsCapturedFromRenderedFirstPartyPagesOn": "2026-08-20",
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "This validator intentionally does not build a national station database.",
            "The stable Shell France tariff page proves the nationwide payment, transaction-fee and roaming rules but exposes the exact kWh price through the app/per-point layer.",
            "The 0.64 EUR/kWh observation is retained only as a representative current first-party station sample, not as a guaranteed universal France tariff.",
        ],
    }

    (out / "shell_recharge_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Shell Recharge France official check\n\n"
        "- Validation model: **operator rules only**, no national station extract.\n"
        "- Exact direct kWh price: **per charging point in Shell app**; no universal kWh amount is asserted.\n"
        "- Representative first-party station check: **0.64 EUR/kWh** across 5 sampled sites (50/150/300 kW), retained as observation only.\n"
        "- Shell Recharge card transaction fee: **0.35 EUR/session**.\n"
        "- Payment: **Shell card / Shell app / partner card / contactless bank card / online portal**.\n"
        "- Preauthorization: **45 EUR Shell card/app; 65 EUR bank card**.\n"
        "- Partner roaming: **partner CPO tariff + 0.35 EUR Shell commission**; partner blocking fees may apply.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
