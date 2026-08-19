#!/usr/bin/env python3
"""Extract current Allego France public pricing facts from official Allego pages.

The extractor separates:
- Allego Direct / country default CPO pricing,
- Allego Smart / Allego Plus app pricing when the official app exposes France,
- third-party MSP / roaming pricing,
- HPC idle and regular-charging overstay fees.

Only public official Allego pages are used. No authentication, cookies or user data.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

SOURCES = {
    "pricing": "https://www.allego.eu/fr/tarifs/",
    "overstay": "https://www.allego.eu/fr/overstay-fee/",
    "faq": "https://www.allego.eu/fr/faq/",
    "app": "https://app.allego.eu/",
}

STATION_SAMPLES = {
    "fenouillet": "https://www.allego.eu/fr/charging-station/rue-des-usines-fenouillet/",
    "vauxbuin": "https://www.allego.eu/fr/charging-station/rue-du-sentier-vauxbuin/",
    "saran": "https://www.allego.eu/fr/charging-station/2380-route-nationale_20-route-de-paris-saran/",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return int(getattr(resp, "status", 200)), raw.decode(charset, errors="replace")


def text_from_html(raw_html: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw_html, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("’", "'").replace("\xa0", " ")
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"):
        s = s.replace(ch, "-")
    return re.sub(r"\s+", " ", s).strip()


def eur(v: str) -> float:
    return float(v.replace(",", "."))


def require(text: str, phrase: str, source: str) -> None:
    if norm(phrase) not in norm(text):
        raise RuntimeError(f"{source}: missing expected official phrase: {phrase}")


def browser_select_country(url: str, country: str = "France") -> tuple[str, dict]:
    """Render an official page and select France in a native or custom country picker."""
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select, WebDriverWait

    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1440,2400")
    opts.add_argument("--lang=fr-FR")
    opts.add_argument(f"--user-agent={UA}")

    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(url)
        WebDriverWait(driver, 20).until(
            lambda d: len((d.find_element(By.TAG_NAME, "body").text or "").strip()) > 100
        )
        method = None
        selected_text = None

        for element in driver.find_elements(By.TAG_NAME, "select"):
            try:
                sel = Select(element)
                match = next(
                    (o for o in sel.options if norm(o.text) == norm(country)),
                    None,
                )
                if match is None:
                    continue
                sel.select_by_visible_text(match.text)
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    element,
                )
                time.sleep(2.5)
                selected_text = Select(element).first_selected_option.text
                if norm(country) in norm(selected_text):
                    method = "native_select"
                    break
            except Exception:
                continue

        if method is None:
            candidates = driver.find_elements(
                By.XPATH,
                "//*[@role='combobox'] | //button[contains(., 'Netherlands')] | //button[contains(., 'Pays-Bas')] | //button[contains(., 'prices for')]",
            )
            for trigger in candidates:
                try:
                    if not trigger.is_displayed():
                        continue
                    trigger.click()
                    time.sleep(0.7)
                    france_nodes = driver.find_elements(
                        By.XPATH,
                        "//*[normalize-space()='France' or normalize-space()='FRANCE']",
                    )
                    clicked = False
                    for node in france_nodes:
                        if node.is_displayed():
                            node.click()
                            clicked = True
                            break
                    if not clicked:
                        continue
                    time.sleep(2.5)
                    selected_text = trigger.text
                    if norm(country) in norm(selected_text):
                        method = "custom_picker"
                        break
                except Exception:
                    continue

        if method is None:
            raise RuntimeError(f"Unable to select {country} on official page {url}")

        body = driver.find_element(By.TAG_NAME, "body").text
        return body, {
            "accessMode": "browser_render",
            "countrySelectionMethod": method,
            "selectedCountry": selected_text,
        }
    finally:
        driver.quit()


def parse_country_direct(text: str) -> dict:
    n = norm(text)
    patterns = {
        "ultraFast": r"(?:chargement ultra-rapide|ultra-fast charging)\s+€?\s*(\d+(?:[.,]\d+)?)\s*€?\s*/\s*kwh",
        "fast": r"(?:chargement rapide|fast charging)\s+€?\s*(\d+(?:[.,]\d+)?)\s*€?\s*/\s*kwh",
        "regular": r"(?:chargement regulier|regular charging)\s+€?\s*(\d+(?:[.,]\d+)?)\s*€?\s*/\s*kwh",
    }
    out = {}
    for key, pat in patterns.items():
        m = re.search(pat, n, flags=re.I)
        if not m:
            raise RuntimeError(f"Allego France pricing: {key} price not found after country selection")
        out[key] = eur(m.group(1))

    idle = re.search(r"idle fee\s*:\s*€?\s*(\d+(?:[.,]\d+)?)\s*€?\s*/\s*min", n)
    if not idle:
        raise RuntimeError("Allego France pricing: HPC idle fee not found")
    idle_fee = eur(idle.group(1))

    overstay = re.search(r"overstay fee\s*:\s*€?\s*(\d+(?:[.,]\d+)?)\s*€?\s*/\s*min", n)
    regular_overstay = eur(overstay.group(1)) if overstay else None

    for value in out.values():
        if not (0.10 <= value <= 2.0):
            raise RuntimeError(f"Implausible Allego France price: {value}")
    if not (0.0 <= idle_fee <= 2.0):
        raise RuntimeError(f"Implausible Allego France idle fee: {idle_fee}")

    return {
        "defaultTariffsEurPerKwh": out,
        "hpcIdleFeeEurPerMin": idle_fee,
        "regularOverstayFeeEurPerMin": regular_overstay,
    }


def parse_fee_rules(pricing_text: str, overstay_text: str, direct: dict) -> dict:
    p = norm(pricing_text)
    o = norm(overstay_text)

    require(o, "Aucun frais de dépassement de durée n'est facturé tant que votre véhicule est en cours de recharge", "Allego overstay")
    if "45 minutes" not in o:
        raise RuntimeError("Allego overstay: 45-minute rule missing")
    if "france" not in o or "0,248" not in o:
        raise RuntimeError("Allego overstay: France HPC fee evidence missing")

    regular_fee = direct["regularOverstayFeeEurPerMin"]
    regular_rule_present = (
        regular_fee is not None
        and "5 hours" in p
        and ("23:00-7:00" in p or "23:00 - 7:00" in p)
        and "max 16 hours" in p
    )

    return {
        "hpcIdle": {
            "eurPerMin": direct["hpcIdleFeeEurPerMin"],
            "onlyWhenChargingEnded": True,
            "gracePeriodFromSessionStartMinutes": 45,
            "scope": "Allego-owned HPC chargers",
        },
        "regularChargingOverstay": {
            "eurPerMin": regular_fee,
            "appliesAfterSessionStartMinutes": 300 if regular_rule_present else None,
            "chargeWindowLocalTime": "07:00-23:00" if regular_rule_present else None,
            "notApplicableWindowLocalTime": "23:00-07:00" if regular_rule_present else None,
            "maximumChargedHours": 16 if regular_rule_present else None,
            "status": "validated_from_current_france_pricing_page" if regular_rule_present else "not_confirmed",
        },
    }


def parse_app_plans(text: str) -> dict:
    n = norm(text)
    if "allego plus" not in n or "allego smart" not in n or "allego direct" not in n:
        raise RuntimeError("Allego app: pricing plan labels not found")

    headings = [
        ("ultraFast", ("ultra-fast charging", "ultra-snelladen", "ultra-schnellladen")),
        ("fast", ("fast charging", "snelladen", "schnellladen")),
        ("regular", ("regular charging", "regulier laden", "normalladen")),
    ]

    starts = {}
    for key, labels in headings:
        pos = min([n.find(label) for label in labels if n.find(label) >= 0] or [-1])
        if pos >= 0:
            starts[key] = pos
    if not starts:
        raise RuntimeError("Allego app: charging type sections not found")

    ordered = sorted(starts.items(), key=lambda kv: kv[1])
    result = {}
    for idx, (key, start) in enumerate(ordered):
        end = ordered[idx + 1][1] if idx + 1 < len(ordered) else min(len(n), start + 1800)
        section = n[start:end]

        tiers = {}
        for tier_key, tier_name in (("plus", "allego plus"), ("smart", "allego smart"), ("direct", "allego direct")):
            m = re.search(
                rf"{tier_name}\s+(\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?)\s*€\s*/\s*kwh",
                section,
            )
            if m:
                raw = m.group(1)
                if "-" in raw:
                    lo, hi = [eur(x.strip()) for x in raw.split("-", 1)]
                    tiers[tier_key] = {"minEurPerKwh": lo, "maxEurPerKwh": hi}
                else:
                    tiers[tier_key] = {"eurPerKwh": eur(raw)}
        if tiers:
            result[key] = tiers

    monthly = None
    m = re.search(r"allego plus.{0,120}?(\d+(?:[.,]\d+)?)\s*€?\s*/\s*(?:month|mois|monat|maand)", n)
    if m:
        monthly = eur(m.group(1))

    return {
        "countrySpecificRates": result or None,
        "plusMonthlyFeeEur": monthly,
        "status": "country_selected_official_app" if result else "country_selected_but_rates_not_parsed",
    }


def parse_promo(text: str) -> dict:
    n = norm(text)
    free_months = 2 if ("2 mois" in n and "gratuit" in n) else None
    signup_deadline = "2026-08-31" if "31 aout" in n else None
    value = None
    m = re.search(r"valeur de\s*(\d+(?:[.,]\d+)?)\s*€", n)
    if m:
        value = eur(m.group(1))
    monthly = round(value / free_months, 2) if value is not None and free_months else None
    savings = None
    m = re.search(r"jusqu.?a\s*(\d+)\s*%\s*d.?econom", n)
    if m:
        savings = float(m.group(1))
    return {
        "name": "Allego Plus summer 2026",
        "signupDeadline": signup_deadline,
        "freeMonths": free_months,
        "statedPromotionValueEur": value,
        "derivedStandardMonthlyFeeEur": monthly,
        "savingsUpToPercent": savings,
        "promotionEndAfterActivation": "2 months after activation",
    }


def parse_roaming(faq_text: str) -> dict:
    n = norm(faq_text)
    if "msp" not in n or "tarif final peut differer" not in n:
        raise RuntimeError("Allego FAQ: MSP price-separation evidence missing")
    return {
        "classification": "third_party_eMSP",
        "operatorDirect": False,
        "priceOwnedBy": "mobility service provider / MSP",
        "stationLevelPriceLookupRequired": True,
        "note": "MSP final tariff may differ from Allego default tariff.",
    }


def parse_station(name: str, url: str, text: str) -> dict:
    n = norm(text)
    if "france" not in n:
        raise RuntimeError(f"station {name}: France marker missing")
    powers = [int(x) for x in re.findall(r"(?:jusqu.?a|speeds up to)\s*(\d{2,3})\s*kw", n)]
    ids = sorted(set(re.findall(r"frallego\d+", n)))
    if not ids:
        raise RuntimeError(f"station {name}: no FRALLEGO EVSE IDs found")
    return {
        "key": name,
        "url": url,
        "powerKwObserved": sorted(set(powers)),
        "evseIdsSample": ids[:12],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/allego")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    statuses = {}
    pages = {}
    for key in ("pricing", "overstay", "faq"):
        status, raw = fetch(SOURCES[key])
        if status != 200:
            raise RuntimeError(f"{key}: unexpected HTTP status {status}")
        statuses[key] = status
        pages[key] = text_from_html(raw)

    # Browser selection is deliberate: Allego's pricing page contains multiple countries
    # in the HTML, while only one country block is visible to a real user.
    pricing_fr, pricing_render_meta = browser_select_country(SOURCES["pricing"], "France")
    direct = parse_country_direct(pricing_fr)
    fees = parse_fee_rules(pricing_fr, pages["overstay"], direct)

    # Official page caveat: exact charge-point prices may vary by location/tender.
    pricing_all = norm(pages["pricing"])
    variable_station_prices = (
        "tarifs des bornes de recharge peuvent varier" in pricing_all
        or "prix que vous payez" in norm(pages["faq"])
    )
    if not variable_station_prices:
        raise RuntimeError("Allego: station-level price-variation caveat not found")

    promo = parse_promo(pages["pricing"])
    roaming = parse_roaming(pages["faq"])

    app_plans = {
        "status": "not_retrieved",
        "countrySpecificRates": None,
        "plusMonthlyFeeEur": promo.get("derivedStandardMonthlyFeeEur"),
    }
    app_render_meta = None
    app_error = None
    try:
        app_fr, app_render_meta = browser_select_country(SOURCES["app"], "France")
        app_plans = parse_app_plans(app_fr)
        if app_plans.get("plusMonthlyFeeEur") is None:
            app_plans["plusMonthlyFeeEur"] = promo.get("derivedStandardMonthlyFeeEur")
    except Exception as exc:
        # App rates are useful enrichment but do not invalidate the official Direct tariff.
        app_error = f"{type(exc).__name__}: {exc}"

    station_samples = []
    for key, url in STATION_SAMPLES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"station {key}: unexpected HTTP status {status}")
        statuses[f"station:{key}"] = status
        station_samples.append(parse_station(key, url, text_from_html(raw)))

    facts = {
        "direct": direct,
        "fees": fees,
        "appPlans": app_plans,
        "promo": promo,
        "roaming": roaming,
        "stationSamples": station_samples,
        "stationLevelPriceLookupRequired": True,
    }
    fingerprint = hashlib.sha256(
        json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "allego-official-france",
        "generatedAt": now_iso(),
        "operator": "Allego",
        "country": "FR",
        "classification": {
            "countryDefaultTariffPublished": True,
            "singleGuaranteedNationalTariff": False,
            "stationLevelPriceLookupRequiredForExactSimulation": True,
            "reason": "Allego publishes France default tariffs but explicitly states charge-point prices may vary by charger type and location/tender.",
        },
        "operatorDirect": {
            "allegoDirectCountryDefault": {
                "currency": "EUR",
                "billingUnit": "kWh",
                "ultraFastEurPerKwh": direct["defaultTariffsEurPerKwh"]["ultraFast"],
                "fastEurPerKwh": direct["defaultTariffsEurPerKwh"]["fast"],
                "regularEurPerKwh": direct["defaultTariffsEurPerKwh"]["regular"],
                "stationLevelPriceLookupRequired": True,
            },
            "allegoApp": app_plans,
            "allegoPlusPromotion": promo,
        },
        "fees": fees,
        "roaming": roaming,
        "stationValidationSamples": station_samples,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [
                {"key": key, "url": url, "httpStatus": statuses.get(key)}
                for key, url in SOURCES.items()
            ] + [
                {"key": f"station:{key}", "url": url, "httpStatus": statuses.get(f"station:{key}")}
                for key, url in STATION_SAMPLES.items()
            ],
            "pricingRender": pricing_render_meta,
            "appRender": app_render_meta,
            "appRenderError": app_error,
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Allego Direct country prices are defaults, not a guarantee for every Allego charge point.",
            "HPC idle fee is charged only after active charging has ended; the first 45 minutes from session start are exempt.",
            "Regular-charging overstay fee is modeled separately from the HPC idle fee.",
            "Third-party MSP pricing must not be treated as Allego Direct/App pricing.",
        ],
    }

    (out / "allego_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    app_status = app_plans.get("status")
    summary = (
        "# Allego France official tariff check\n\n"
        f"- Direct default ultra-fast: **{direct['defaultTariffsEurPerKwh']['ultraFast']:.3f} EUR/kWh**\n"
        f"- Direct default fast: **{direct['defaultTariffsEurPerKwh']['fast']:.3f} EUR/kWh**\n"
        f"- Direct default regular: **{direct['defaultTariffsEurPerKwh']['regular']:.3f} EUR/kWh**\n"
        f"- HPC idle fee: **{fees['hpcIdle']['eurPerMin']:.3f} EUR/min** after charging ends, with first 45 min exempt\n"
        f"- Regular overstay: **{fees['regularChargingOverstay']['eurPerMin']} EUR/min** after 5 h, 07:00-23:00, max 16 h\n"
        f"- Allego Plus summer promo: **{promo.get('freeMonths')} months free**, signup through **{promo.get('signupDeadline')}**, derived standard fee **{promo.get('derivedStandardMonthlyFeeEur')} EUR/month**\n"
        f"- Official Allego App France pricing parse: **{app_status}**\n"
        "- Exact station price lookup remains required because Allego explicitly allows location/tender variation.\n"
        f"- Official French station samples checked: **{len(station_samples)}**\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
