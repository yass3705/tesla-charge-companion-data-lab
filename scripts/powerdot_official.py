#!/usr/bin/env python3
"""Extract Powerdot France public charging rules from first-party/operator sources.

Important classification rules:
- Powerdot does NOT publish one guaranteed national direct tariff in France.
- Exact connector price must be checked at station/connector level (QR or chosen eMSP).
- Electroverse subscription pricing is an eMSP/member layer, not Powerdot CPO-direct.
- Leasing Social is an eligibility-limited special programme, not a general tariff.
- The Power Dot France data.gouv IRVE file is used only as a static technical inventory
  source and its freshness is reported explicitly.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import subprocess
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

SOURCES = {
    "faq": "https://www.powerdot.eu/faq",
    "driver": "https://www.powerdot.eu/why-charge-with-us",
    "electroverseSubscription": "https://electroverse.com/fr-FR/community/electroverse-features/abonnements-electroverse-qu-est-ce-que-c-est-et-comment-s-inscrire",
    "powerdotInventoryDataset": "https://www.data.gouv.fr/datasets/bornes-de-recharge-pour-ve-du-reseau-power-dot-france-1",
    "powerdotInventoryCsv": "https://www.data.gouv.fr/api/1/datasets/r/1bf98bac-94a9-4909-8726-47a203038a40",
}

TARGET_CITIES = ("Plaisir", "Guyancourt", "Villabe")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,text/csv,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
        },
    )
    first_exc = None
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return int(getattr(resp, "status", 200)), raw.decode(charset, errors="replace")
    except Exception as exc:
        first_exc = exc

    cp = subprocess.run(
        ["curl", "-fsSL", "--max-redirs", "12", "--connect-timeout", "20", "--max-time", "60",
         "-A", UA, "-H", "Accept-Language: fr-FR,fr;q=0.9,en;q=0.6", url],
        capture_output=True,
    )
    if cp.returncode == 0 and cp.stdout:
        return 200, cp.stdout.decode("utf-8", errors="replace")

    # Powerdot's website currently loops 307 redirects specifically for
    # non-browser GitHub-runner clients. A real browser reaches the same
    # first-party page normally.
    if "powerdot.eu/" in url:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        opts = webdriver.ChromeOptions()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--lang=en-GB")
        opts.add_argument(f"--user-agent={UA}")
        driver = webdriver.Chrome(options=opts)
        try:
            driver.get(url)
            WebDriverWait(driver, 30).until(
                lambda d: len((d.find_element(By.TAG_NAME, "body").text or "").strip()) > 100
            )
            return 200, driver.page_source
        finally:
            driver.quit()

    raise RuntimeError(
        f"Powerdot fetch failed for {url}: urllib={type(first_exc).__name__}: {first_exc}; "
        f"curl_exit={cp.returncode}"
    )


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


def require_any(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: expected evidence not found")


def first_matching(row: dict, keys: tuple[str, ...]) -> str | None:
    lower = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        if key.lower() in lower and str(lower[key.lower()] or "").strip():
            return str(lower[key.lower()]).strip()
    return None


def parse_inventory(csv_text: str) -> dict:
    sample = csv_text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    reader = csv.DictReader(io.StringIO(csv_text), dialect=dialect)
    fields = {str(name).strip().lower() for name in (reader.fieldnames or []) if name is not None}
    if not fields.intersection({"id_station_itinerance", "id_pdc_itinerance", "id_pdc_local"}):
        raise RuntimeError("Powerdot inventory CSV: incompatible station/EVSE schema")
    rows = list(reader)

    samples = []
    for city in TARGET_CITIES:
        city_norm = norm(city)
        match = None
        for row in rows:
            haystack = " ".join(str(v or "") for v in row.values())
            if city_norm in norm(haystack):
                match = row
                break
        if match:
            power_raw = first_matching(match, ("puissance_nominale", "puissance_nominale_kw", "puissance"))
            try:
                power = float(str(power_raw).replace(",", ".")) if power_raw else None
            except ValueError:
                power = None
            samples.append({
                "targetCity": city,
                "stationName": first_matching(match, ("nom_station", "nom_enseigne", "nom_site")),
                "address": first_matching(match, ("adresse_station", "adresse", "adresse_complete")),
                "city": first_matching(match, ("consolidated_commune", "nom_commune", "commune", "ville")),
                "postalCode": first_matching(match, ("consolidated_code_postal", "code_postal", "cp")),
                "powerKwObserved": power,
                "evseId": first_matching(match, ("id_pdc_itinerance", "id_pdc_local", "id_pdc")),
            })

    if len(samples) < 3:
        for row in rows:
            if len(samples) >= 3:
                break
            candidate = {
                "targetCity": None,
                "stationName": first_matching(row, ("nom_station", "nom_enseigne", "nom_site")),
                "address": first_matching(row, ("adresse_station", "adresse", "adresse_complete")),
                "city": first_matching(row, ("consolidated_commune", "nom_commune", "commune", "ville")),
                "postalCode": first_matching(row, ("consolidated_code_postal", "code_postal", "cp")),
                "powerKwObserved": None,
                "evseId": first_matching(row, ("id_pdc_itinerance", "id_pdc_local", "id_pdc")),
            }
            signature = (candidate["stationName"], candidate["address"], candidate["evseId"])
            if not any((x["stationName"], x["address"], x["evseId"]) == signature for x in samples):
                samples.append(candidate)

    return {
        "rowCount": len(rows),
        "samples": samples[:3],
        "publisherLastUpdateKnown": "2025-09-14",
        "freshnessStatus": "stale_publisher_dataset_not_live_availability",
    }



def parse_electroverse_subscriptions(page_text: str) -> dict:
    """Extract eMSP discounts inside CPO-specific sections; fail closed on ambiguity.

    The public article is converted from HTML to plain text before this call.
    Never search all 'France: XX%' matches globally: different operators differ.
    """
    page = norm(page_text)
    ionity_start = re.search(r"\bionity\b", page)
    powerdot_start = re.search(r"\bpowerdot\b", page)
    if not ionity_start or not powerdot_start or powerdot_start.start() <= ionity_start.start():
        raise RuntimeError("Electroverse IONITY/Powerdot sections missing or reordered")
    ionity = page[ionity_start.start():powerdot_start.start()]
    powerdot_end = re.search(r"royaume-uni uniquement|\bbe\.ev\b", page[powerdot_start.end():])
    if not powerdot_end:
        raise RuntimeError("Electroverse Powerdot section terminator missing")
    powerdot = page[powerdot_start.start():powerdot_start.end() + powerdot_end.start()]
    def percentage(section: str, country: str) -> float:
        values = re.findall(r"\b" + re.escape(country) + r"\s*:\s*(\d{1,2})\s*%", section)
        if len(values) != 1:
            raise RuntimeError(f"Electroverse {country} subscription evidence missing or ambiguous")
        n = float(values[0])
        if n <= 0 or n >= 100:
            raise RuntimeError(f"Electroverse {country} discount outside valid range")
        return n
    if not re.search(r"11,99\s*€", ionity):
        raise RuntimeError("Electroverse IONITY indicative monthly fee evidence missing")
    if not re.search(r"1,99\s*€\s*par\s*mois", powerdot):
        raise RuntimeError("Electroverse Powerdot monthly fee evidence missing")
    return {
        "ionity": {"FR": {"discountPercent": percentage(ionity, "france"),
                           "monthlyFeeEurIndicative": 11.99}},
        "powerdot": {
            "FR": {"discountPercent": percentage(powerdot, "france"), "monthlyFeeEur": 1.99},
            "ES": {"discountPercent": percentage(powerdot, "espagne"), "monthlyFeeEur": 1.99},
            "BE": {"discountPercent": percentage(powerdot, "belgique"), "monthlyFeeEur": 1.99},
            "PT": {"discountPercent": percentage(powerdot, "portugal"), "monthlyFeeEur": 1.99},
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/powerdot")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    fetched = {}
    statuses = {}
    for key in ("faq", "driver", "electroverseSubscription"):
        status, raw = fetch(SOURCES[key])
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        fetched[key] = text_from_html(raw)

    inv_status, inv_csv = fetch(SOURCES["powerdotInventoryCsv"])
    if inv_status != 200:
        raise RuntimeError(f"inventory CSV: HTTP {inv_status}")
    statuses["powerdotInventoryCsv"] = inv_status
    inventory = parse_inventory(inv_csv)

    faq = norm(fetched["faq"])
    driver = norm(fetched["driver"])
    require_any(driver, ("scan the qr code on the charger",), "Powerdot current QR payment")
    require_any(driver, ("300+ mobility platforms", "300 mobility platforms"), "Powerdot mobility-platform reach")
    require_any(faq, ("miio", "chargemap", "electromaps"), "Powerdot current mobility-app discovery")

    electro = norm(fetched["electroverseSubscription"])
    subscriptions = parse_electroverse_subscriptions(electro)
    discount = subscriptions["powerdot"]["FR"]["discountPercent"]

    august_credit_historical = 10.0 if ("aout 2026" in electro and "10 €" in electro) else None
    preauth_amounts = []

    facts = {
        "classification": {
            "singleGuaranteedNationalTariff": False,
            "stationLevelPriceLookupRequiredForExactSimulation": True,
            "reason": "Powerdot directs users to the exact connector tariff via QR code or mobility-provider app; price varies by location/connector.",
        },
        "operatorDirect": {
            "adHocQr": {
                "available": True,
                "priceModel": "station_connector_specific",
                "exactPriceLookupRequired": True,
                "nationalEurPerKwh": None,
            },
            "ownConsumerApp": {
                "status": "not_identified_on_current_powerdot_official_user_faq",
                "note": "Current Powerdot driver page states that ad-hoc QR payment is available and that the network is connected to 300+ mobility platforms.",
            },
        },
        "mobilityProviders": {
            "generalRoaming": {
                "classification": "third_party_eMSP",
                "operatorDirect": False,
                "stationLevelPriceLookupRequired": True,
                "examplesNamedByPowerdot": ["Chargemap", "Electromaps", "Miio"],
            },
            "electroversePowerdotSubscription": {
                "classification": "third_party_eMSP_subscription",
                "operatorDirect": False,
                "monthlyFeeEur": 1.99,
                "franceDiscountPercent": discount,
                "temporaryAugust2026CreditEur": None,
                "historicalAugust2026CreditEur": august_credit_historical,
                "historicalPromotionStatus": "expired",
                "exactResultingEurPerKwh": None,
                "note": "Discount applies to the Electroverse price and must not be converted into a Powerdot CPO-direct national tariff.",
            },
        },
        "specialPrograms": {
            "leasingSocial": {
                "classification": "eligibility_limited_special_program",
                "generalPublicTariff": False,
                "status": "not_revalidated_on_current_powerdot_site",
                "eurPerKwh": None,
                "freeSubscriptionMonths": None,
                "monthlyFeeAfterFreePeriodEur": None,
                "commitment": None,
                "note": "The former France Leasing Social page is no longer a current reachable first-party source, so historical programme terms are not promoted as current.",
            },
        },
        "fees": {
            "idleOrConnectionFee": {
                "status": "not_asserted_network_wide_from_current_powerdot_cpo_faq",
                "eurPerMin": None,
            },
            "parking": {
                "status": "site_or_landowner_specific_check_required",
                "note": "Parking rules are not modeled as a Powerdot-wide fee.",
            },
            "paymentPreauthorization": {
                "possibleAmountsEur": preauth_amounts,
                "status": "not_revalidated_on_current_powerdot_site",
                "purpose": None,
                "unusedBalanceRefunded": None,
                "statedRefundDelayDays": None,
            },
        },
        "inventory": inventory,
    }

    fingerprint = hashlib.sha256(
        json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    payload = {
        "schemaVersion": "1.1.0",
        "dataset": "powerdot-official-france",
        "generatedAt": now_iso(),
        "operator": "Powerdot",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "cpoFactsFromPowerdotOfficial": True,
            "currentCpoEvidenceScope": "QR payment, mobility-platform access, and static technical inventory; no national direct kWh tariff asserted",
            "emspFactsFromElectroverseOfficial": True,
            "technicalInventoryPublishedByPowerDotFranceOnDataGouv": True,
            "sources": [
                {"key": key, "url": url, "httpStatus": statuses.get(key)}
                for key, url in SOURCES.items()
            ],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "Do not invent a national Powerdot direct kWh price: the current official FAQ requires exact connector lookup.",
            "Electroverse subscription is an eMSP/member layer and must remain separate from Powerdot direct/ad-hoc pricing.",
            "Former Leasing Social terms are retained only as a non-current programme reference until a current first-party source reappears.",
            "Former payment-preauthorization amounts are not carried forward as current without current first-party evidence.",
            "The Power Dot France publisher IRVE file is useful for static IDs/locations but is stale and must not be treated as live availability.",
        ],
    }

    (out / "powerdot_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# Powerdot France official check\n\n"
        "- National guaranteed CPO-direct tariff: **none published**; exact connector lookup required.\n"
        "- Direct/ad-hoc route: **QR code / station-specific price**.\n"
        f"- Electroverse Powerdot subscription (France): **1.99 EUR/month, {discount:g}% discount** (eMSP, not CPO-direct).\n"
        f"- Historical August 2026 Electroverse credit: **{august_credit_historical} EUR**, now expired.\n"
        "- Leasing Social: **not revalidated on the current Powerdot site**; historical terms are not promoted as current.\n"
        "- Payment preauthorization: **not revalidated on the current Powerdot site**.\n"
        "- Network-wide idle fee: **not asserted from current Powerdot CPO FAQ**.\n"
        "- Parking: **site/landowner-specific check required**.\n"
        f"- Power Dot France publisher IRVE rows: **{inventory['rowCount']}**; freshness: **{inventory['freshnessStatus']}**.\n"
        f"- Static station samples retained: **{len(inventory['samples'])}**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
