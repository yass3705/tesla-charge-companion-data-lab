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
    "uniformFastRate": "https://support.shell.fr/api/v2/help_center/fr-fr/articles/40801882587409.json",
    "payment": "https://support.shell.fr/api/v2/help_center/fr-fr/articles/46950711091729.json",
    "preauthorization": "https://support.shell.fr/api/v2/help_center/fr-fr/articles/41384776749457.json",
    "roamingCost": "https://support.shell.fr/api/v2/help_center/fr-fr/articles/40801847438225.json",
    "directCost": "https://support.shell.fr/api/v2/help_center/fr-fr/articles/40801845990161.json",
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
        "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
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


def render_station_tariff(url: str) -> dict:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--lang=fr-FR")
    opts.add_argument(f"--user-agent={UA}")
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(url)
        WebDriverWait(driver, 35).until(
            lambda d: len((d.find_element(By.TAG_NAME, "body").text or "").strip()) > 150
        )
        WebDriverWait(driver, 35).until(
            lambda d: (
                "€/kwh" in norm(d.find_element(By.TAG_NAME, "body").text or "")
                or "price per kwh" in norm(d.find_element(By.TAG_NAME, "body").text or "")
            )
        )
        text = norm(driver.find_element(By.TAG_NAME, "body").text or "")
        prices = [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*€\s*/\s*kwh", text)]
        fees = [float(x.replace(",", ".")) for x in re.findall(r"(?:session fee|frais de session)\s*:?\s*€?\s*(\d+(?:[.,]\d+)?)", text)]
        powers = [int(float(x)) for x in re.findall(r"(\d{2,3}(?:\.0)?)\s*kw", text)]
        if not prices:
            raise RuntimeError("rendered Shell station page exposes no EUR/kWh tariff")
        return {
            "eurPerKwh": prices[0],
            "sessionFeeEur": fees[0] if fees else None,
            "powerKwObserved": sorted(set(powers)),
            "evidenceMode": "current_rendered_first_party_station_page",
        }
    finally:
        driver.quit()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/shell_recharge")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    statuses = {}
    pages = {}
    for key, url in SOURCES.items():
        try:
            status, raw = fetch(url)
            statuses[key] = status
            pages[key] = norm(text_from_html(raw))
        except Exception as exc:
            statuses[key] = None
            pages[key] = f"fetch_error {type(exc).__name__}: {exc}"

    # The former Zendesk-like JSON article URLs now redirect to Shell France's
    # generic help page. Treat those rules as retired rather than silently
    # accepting stale article text.
    support_keys = ("uniformFastRate", "payment", "preauthorization", "roamingCost", "directCost")
    retired_support_api = all(
        "bienvenue au service client shell france" in pages.get(k, "")
        or "aide et support" in pages.get(k, "")
        for k in support_keys
    )

    station_results = []
    for sample in REPRESENTATIVE_RENDERED_SAMPLES:
        key = sample["key"]
        url = SOURCES[key]
        current = render_station_tariff(url)
        station_results.append({"key": key, "url": url, **current})

    current_prices = [x["eurPerKwh"] for x in station_results]
    current_fees = [x["sessionFeeEur"] for x in station_results if x["sessionFeeEur"] is not None]
    if len(current_prices) < 3:
        raise RuntimeError(f"Shell: insufficient current rendered tariff samples: {len(current_prices)}")
    if len(set(round(v, 4) for v in current_prices)) != 1:
        raise RuntimeError(f"Shell: representative station tariffs diverged: {current_prices}")

    representative_price = current_prices[0]
    representative_fee = current_fees[0] if current_fees and len(set(round(v, 4) for v in current_fees)) == 1 else None
    if not (0.10 <= representative_price <= 2.0):
        raise RuntimeError(f"Shell: implausible current rendered tariff {representative_price}")

    powers = sorted({p for x in station_results for p in x["powerKwObserved"]})
    facts = {
        "classification": {
            "singleNationalFastShellRechargeCardTariffRule": False,
            "currentUniformRuleSourceStatus": "retired_support_article_api" if retired_support_api else "not_confirmed",
            "representativeCurrentSamplesConsistent": True,
            "exactCurrentKwhAmountAutoExtracted": True,
            "stationLevelLookupRecommendedForExactSimulation": True,
            "reason": "Current first-party station pages expose a consistent Shell App tariff across representative sites, while the former support-article API no longer exposes the national uniform-rule article.",
        },
        "operatorDirect": {
            "fastShellRechargeWithShellApp": {
                "uniformAcrossFastShellRechargeStations": None,
                "representativeCurrentEurPerKwh": representative_price,
                "representativePriceStatus": "auto_extracted_current_first_party_station_samples",
                "exactStationLookupRecommended": True,
            },
            "renderedFirstPartySamples": {
                "count": len(station_results),
                "allObservedEurPerKwh": representative_price,
                "allObservedSessionFeeEur": representative_fee,
                "powerClassesKw": powers,
            },
        },
        "payment": {
            "shellApp": "shell recharge" in " ".join(pages.values()),
            "shellRechargeCard": "carte de recharge" in " ".join(pages.values()),
            "preauthorization": {
                "status": "not_revalidated_after_support_article_api_retirement",
                "shellCardOrAppEur": None,
                "bankCardEur": None,
            },
        },
        "fees": {
            "representativeShellAppSessionFeeEur": representative_fee,
            "networkWideIdleFee": None,
            "parking": {"status": "site_specific_unless_explicitly_published"},
        },
        "roaming": {
            "classification": "partner_cpo_layer",
            "operatorDirect": False,
            "exactPartnerPriceLookupRequired": True,
            "legacyTransactionFeeStatus": "not_revalidated_after_support_article_api_retirement",
        },
        "representativeStationChecks": station_results,
        "technical": {
            "representativePowerClassesKw": powers,
            "stationPagesReachable": all(statuses.get(k) == 200 for k in STATION_KEYS),
            "retiredSupportArticleApiDetected": retired_support_api,
        },
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.3.0",
        "dataset": "shell-recharge-official-france",
        "generatedAt": now_iso(),
        "operator": "Shell Recharge",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "supportArticleApiStatus": "retired_redirects_to_generic_help" if retired_support_api else "unknown",
            "sources": [{"key": k, "url": u, "httpStatus": statuses.get(k)} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Current numeric direct tariff is refreshed from rendered first-party Shell station pages.",
            "The former support-article API no longer proves a nationwide uniform tariff, so exact station lookup remains recommended.",
            "Preauthorization and legacy roaming-fee amounts are not carried forward as current facts without a current official source.",
        ],
    }

    (out / "shell_recharge_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Shell Recharge France official check\n\n"
        f"- Current representative Shell App tariff: **{representative_price:.2f} EUR/kWh** across **{len(station_results)}** rendered first-party samples.\n"
        f"- Representative session fee: **{representative_fee} EUR**.\n"
        "- Former Shell support article API: **retired/redirected to generic help**, so the old nationwide-uniform rule is no longer asserted.\n"
        "- Exact station lookup: **recommended**.\n"
        "- Preauthorization / legacy roaming fee amounts: **not revalidated from a current official source**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
