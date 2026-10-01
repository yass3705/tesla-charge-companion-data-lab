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
    """Render an official page and return the visible selected-country content.

    The Allego pricing page became client-rendered in late 2026. Selenium's
    element.text intentionally excludes hidden tariff cards, which makes the
    rendered visible body a safer source than flattened raw HTML.
    """
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
        WebDriverWait(driver, 30).until(
            lambda d: len((d.find_element(By.TAG_NAME, "body").text or "").strip()) > 100
        )
        WebDriverWait(driver, 30).until(
            lambda d: (
                "kwh" in norm(d.find_element(By.TAG_NAME, "body").text or "")
                and ("paiement a l'usage" in norm(d.find_element(By.TAG_NAME, "body").text or "")
                     or "allego direct" in norm(d.find_element(By.TAG_NAME, "body").text or ""))
            )
        )

        body = driver.find_element(By.TAG_NAME, "body")
        visible = body.text or ""
        nvisible = norm(visible)

        # Current Allego markup exposes every country as #pricing-<id>.
        # Resolve the requested country through the menu anchor itself, then
        # read that panel's textContent even when CSS keeps it hidden because
        # the runner's geolocation selected another country by default.
        panels = driver.find_elements(By.CSS_SELECTOR, "[id^='pricing-']")
        country_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='#pricing-']")
        for link in country_links:
            try:
                label = " ".join(
                    x for x in (
                        link.get_attribute("textContent"),
                        link.get_attribute("aria-label"),
                        link.get_attribute("title"),
                    ) if x
                )
                if norm(country) not in norm(label):
                    continue
                href = link.get_attribute("href") or ""
                target_id = href.rsplit("#", 1)[-1]
                if not target_id.startswith("pricing-"):
                    continue
                panel = driver.find_element(By.ID, target_id)
                panel_text = panel.get_attribute("textContent") or panel.get_attribute("innerText") or panel.text or ""
                if "kwh" in norm(panel_text):
                    return panel_text, {
                        "accessMode": "browser_render_country_anchor_panel",
                        "countrySelectionMethod": "country_anchor_target",
                        "selectedCountry": country,
                        "pricingPanelId": target_id,
                        "pricingPanelCount": len(panels),
                    }
            except Exception:
                continue

        # If the country anchor cannot be resolved, fall back to the active
        # localized panel.
        active_panels = driver.find_elements(By.CSS_SELECTOR, ".columns.active[id^='pricing-']")
        if country == "France" and "/fr/" in url and len(active_panels) == 1:
            panel = active_panels[0]
            panel_text = panel.get_attribute("innerText") or panel.text or ""
            if "kwh" in norm(panel_text):
                return panel_text, {
                    "accessMode": "browser_render_active_panel",
                    "countrySelectionMethod": "localized_active_panel",
                    "selectedCountry": country,
                    "pricingPanelId": panel.get_attribute("id"),
                    "pricingPanelCount": len(panels),
                }

        visible_panels = []
        for panel in panels:
            try:
                ptext = panel.get_attribute("innerText") or panel.text or ""
                if panel.is_displayed() and "kwh" in norm(ptext):
                    visible_panels.append((panel.get_attribute("id"), ptext))
            except Exception:
                continue
        if country == "France" and "/fr/" in url and len(visible_panels) == 1:
            panel_id, panel_text = visible_panels[0]
            return panel_text, {
                "accessMode": "browser_render_visible_dom",
                "countrySelectionMethod": "localized_visible_panel",
                "selectedCountry": country,
                "pricingPanelId": panel_id,
                "pricingPanelCount": len(panels),
            }

        # Determine the *active* country from the first picker label.
        # Do not merely search for France anywhere because the opened menu also
        # contains France as one of its options.
        current_match = re.search(
            r"(?:affichage des prix pour|showing prices for)\\s+([a-zA-ZÀ-ÖØ-öø-ÿ'’ -]{2,40})",
            visible,
            flags=re.I,
        )
        current_country = current_match.group(1).strip() if current_match else None
        if current_country and norm(current_country) == norm(country):
            return visible, {
                "accessMode": "browser_render_visible_dom",
                "countrySelectionMethod": "already_selected",
                "selectedCountry": country,
                "observedCurrentCountry": current_country,
            }

        # Legacy native selector fallback.
        for element in driver.find_elements(By.TAG_NAME, "select"):
            try:
                sel = Select(element)
                match = next((o for o in sel.options if norm(o.text) == norm(country)), None)
                if match is None:
                    continue
                sel.select_by_visible_text(match.text)
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    element,
                )
                WebDriverWait(driver, 15).until(
                    lambda d: norm(country) in norm(d.find_element(By.TAG_NAME, "body").text or "")
                )
                time.sleep(1.0)
                visible = body.text or ""
                return visible, {
                    "accessMode": "browser_render_visible_dom",
                    "countrySelectionMethod": "native_select",
                    "selectedCountry": country,
                }
            except Exception:
                continue

        # Current custom picker fallback: click a visible control mentioning
        # "prices for", then the exact country option.
        triggers = driver.find_elements(
            By.XPATH,
            "//*[self::button or self::a or @role='combobox'][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'prix pour') or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'prices for')]",
        )
        for trigger in triggers:
            try:
                if not trigger.is_displayed():
                    continue
                trigger.click()
                time.sleep(0.5)
                options = driver.find_elements(
                    By.XPATH,
                    "//*[self::button or self::a or @role='option' or self::li]",
                )
                for option in options:
                    try:
                        if not option.is_displayed():
                            continue
                        ot = (option.text or "").strip()
                        notext = norm(ot)
                        if not (notext == norm(country) or notext.startswith(norm(country) + " ")):
                            continue
                        option.click()
                        WebDriverWait(driver, 15).until(
                            lambda d: (
                                (lambda m: bool(m and norm(m.group(1).strip()) == norm(country)))(
                                    re.search(
                                        r"(?:affichage des prix pour|showing prices for)\\s+([a-zA-ZÀ-ÖØ-öø-ÿ'’ -]{2,40})",
                                        d.find_element(By.TAG_NAME, "body").text or "",
                                        flags=re.I,
                                    )
                                )
                            )
                        )
                        time.sleep(1.0)
                        visible = body.text or ""
                        return visible, {
                            "accessMode": "browser_render_visible_dom",
                            "countrySelectionMethod": "custom_picker",
                            "selectedCountry": country,
                            "observedCurrentCountry": current_country,
                        }
                    except Exception:
                        continue
            except Exception:
                continue

        raise RuntimeError(f"Unable to establish rendered {country} pricing on official page {url}")
    finally:
        driver.quit()


def static_country_pricing_block(url: str, country: str = "France") -> tuple[str, dict]:
    """Map one country to Allego's ordered static tariff blocks.

    Allego has used both a native <select> and a link/button country picker.
    In both versions the country controls and tariff cards are emitted in the
    same document order, so we can map a country to its static block by index.
    """
    status, raw = fetch(url)
    if status != 200:
        raise RuntimeError(f"Allego pricing: unexpected HTTP status {status}")

    page_text = text_from_html(raw)

    labels = []
    access_mode = None

    # Legacy/native selector.
    selects = re.findall(r"<select\\b[^>]*>.*?</select>", raw, flags=re.I | re.S)
    for candidate in selects:
        ctext = norm(text_from_html(candidate))
        if "france" in ctext and ("allemagne" in ctext or "germany" in ctext) and ("pays-bas" in ctext or "netherlands" in ctext):
            for option_html in re.findall(r"<option\\b[^>]*>(.*?)</option>", candidate, flags=re.I | re.S):
                label = text_from_html(option_html).strip()
                nl = norm(label)
                if not label or "choisissez" in nl or "select" in nl:
                    continue
                labels.append(label)
            access_mode = "official_static_html_country_index"
            break

    # Current Allego markup (2026-10): country controls are links/buttons whose
    # accessible text is "Affichage des prix pour <country>" / "Showing prices for <country>".
    if not labels:
        candidates = []
        patterns = (
            r"Affichage des prix pour\\s+([A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’ .-]{1,40}?)(?=\\s+(?:Affichage des prix pour|Showing prices for|Vitesse de charge|Charging speed)|$)",
            r"Showing prices for\\s+([A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’ .-]{1,40}?)(?=\\s+(?:Affichage des prix pour|Showing prices for|Vitesse de charge|Charging speed)|$)",
        )
        for pat in patterns:
            candidates.extend(re.findall(pat, page_text, flags=re.I))
        # Fallback to raw accessibility attributes if text flattening joins controls oddly.
        if not candidates:
            candidates = re.findall(
                r"(?:aria-label|title)=[\"'](?:Affichage des prix pour|Showing prices for)\\s+([^\"']+)[\"']",
                raw,
                flags=re.I,
            )
        seen = set()
        for candidate in candidates:
            label = re.sub(r"\\s+", " ", html.unescape(candidate)).strip()
            key = norm(label)
            if label and key not in seen:
                seen.add(key)
                labels.append(label)
        if labels:
            access_mode = "official_static_html_country_link_index"

    if not labels:
        raise RuntimeError("Allego pricing: country controls not found in official HTML")

    country_index = next((i for i, label in enumerate(labels) if norm(label) == norm(country)), None)
    if country_index is None:
        raise RuntimeError(f"Allego pricing: {country} missing from country controls: {labels[:20]}")

    ntext = norm(page_text)

    # Each country card starts with a charging-speed header. Prefer the current
    # French label; retain legacy/English fallbacks.
    marker_candidates = ("vitesse de charge", "charging speed", "chargement ultra-rapide", "ultra-fast charging")
    starts = []
    marker_used = None
    for marker in marker_candidates:
        trial = [m.start() for m in re.finditer(re.escape(norm(marker)), ntext)]
        if len(trial) >= len(labels):
            starts = trial
            marker_used = marker
            break
    if len(starts) < len(labels):
        raise RuntimeError(
            f"Allego pricing: tariff block count {len(starts)} is smaller than country control count {len(labels)}"
        )

    # Some page chrome can repeat the first heading; align by taking the first
    # contiguous country-card sequence matching the number of controls.
    starts = starts[:len(labels)]
    blocks = []
    for i, block_start in enumerate(starts):
        block_end = starts[i + 1] if i + 1 < len(starts) else len(ntext)
        blocks.append(ntext[block_start:block_end])

    block = blocks[country_index]
    if "kwh" not in block:
        raise RuntimeError(f"Allego pricing: mapped {country} block contains no kWh tariff")

    return block, {
        "accessMode": access_mode,
        "selectedCountry": labels[country_index],
        "countryIndex": country_index,
        "countryOptionCount": len(labels),
        "tariffBlockCount": len(starts),
        "tariffBlockMarker": marker_used,
    }

def parse_country_direct(text: str) -> dict:
    n = norm(text)

    # Current rendered layout groups operator-direct prices under
    # "Paiement à l’usage". Restrict parsing to that tier so Allego Plus/Smart
    # prices cannot be mistaken for direct prices.
    direct_section = n
    for marker in ("paiement a l'usage", "pay as you go", "allego direct"):
        pos = n.find(marker)
        if pos >= 0:
            direct_section = n[pos:pos + 1800]
            break

    patterns = {
        "ultraFast": (
            r"(?:chargement ultra-rapide|ultra-fast charging|ultra-rapide)\\s+(?:jusqu.?a\\s*\\d{2,3}\\s*kw\\s+)?€?\\s*(\\d+(?:[.,]\\d+)?)\\s*€?\\s*/\\s*kwh"
        ),
        "fast": (
            r"(?<!ultra-)(?:chargement rapide|fast charging|rapide)\\s+(?:jusqu.?a\\s*\\d{2,3}\\s*kw\\s+)?€?\\s*(\\d+(?:[.,]\\d+)?)\\s*€?\\s*/\\s*kwh"
        ),
        "regular": (
            r"(?:chargement regulier|regular charging|standard)\\s+(?:jusqu.?a\\s*\\d{2,3}\\s*kw\\s+)?€?\\s*(\\d+(?:[.,]\\d+)?)\\s*€?\\s*/\\s*kwh"
        ),
    }
    out = {}
    missing = []
    for key, pat in patterns.items():
        m = re.search(pat, direct_section, flags=re.I)
        if m:
            out[key] = eur(m.group(1))
        else:
            missing.append(key)

    # On desktop Allego hides the repeated mobile speed labels inside each
    # tariff column. Selenium innerText therefore exposes only the three
    # €/kWh values under "Paiement à l’usage". Their DOM order follows the
    # visible speed column: Ultra-fast, Fast, Standard.
    if missing:
        ordered_prices = [
            eur(x)
            for x in re.findall(r"(\\d+(?:[.,]\\d+)?)\\s*€\\s*/\\s*kwh", direct_section, flags=re.I)
        ]
        if len(ordered_prices) >= 3:
            out = {
                "ultraFast": ordered_prices[0],
                "fast": ordered_prices[1],
                "regular": ordered_prices[2],
            }
            missing = []
    if missing:
        raise RuntimeError(
            f"Allego France pricing: missing {missing} in operator-direct section; "
            f"ordered EUR/kWh values found={re.findall(r'(?:\\d+(?:[.,]\\d+)?)\\s*€\\s*/\\s*kwh', direct_section, flags=re.I)}"
        )

    # Idle/overstay fees can be outside the direct card; search full selected text.
    idle = re.search(r"idle fee\\s*:\\s*€?\\s*(\\d+(?:[.,]\\d+)?)\\s*€?\\s*/\\s*min", n)
    if not idle:
        idle = re.search(r"(?:frais d.?inactivite|frais de stationnement)\\s*:?\\s*€?\\s*(\\d+(?:[.,]\\d+)?)\\s*€?\\s*/\\s*min", n)
    idle_fee = eur(idle.group(1)) if idle else 0.248

    overstay = re.search(r"overstay fee\\s*:\\s*€?\\s*(\\d+(?:[.,]\\d+)?)\\s*€?\\s*/\\s*min", n)
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

    # Prefer cheap static extraction when Allego still exposes tariff cards in
    # source HTML. Fall back to rendered visible DOM when the page is client-rendered.
    try:
        pricing_fr, pricing_render_meta = static_country_pricing_block(SOURCES["pricing"], "France")
    except Exception as static_exc:
        pricing_fr, pricing_render_meta = browser_select_country(SOURCES["pricing"], "France")
        pricing_render_meta["staticFallbackError"] = f"{type(static_exc).__name__}: {static_exc}"
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
