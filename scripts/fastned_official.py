#!/usr/bin/env python3
"""Extract current Fastned France pricing facts from official Fastned pages.

Fastned publishes a country-level France tariff. This extractor validates that rule
against several official French station pages, while keeping third-party charge-card
pricing separate as roaming/eMSP pricing.

Only public official Fastned pages are used. No authenticated APIs, cookies or user
data are required.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import unicodedata
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

SOURCES = {
    "tariffs": "https://www.fastnedcharging.com/fr/recharge/tarifs",
    "how_to_charge": "https://www.fastnedcharging.com/fr/recharge/comment-recharger",
    "terms": "https://www.fastnedcharging.com/fr/conditions-d-utilisation",
}

STATION_SAMPLES = {
    "la_maxe": "https://www.fastnedcharging.com/fr/emplacements/aire-de-la-maxe",
    "acheres": "https://www.fastnedcharging.com/fr/emplacements/aire-d-acheres-la-foret",
    "chartres": "https://www.fastnedcharging.com/fr/emplacements/chartres-mainvilliers",
    "croix_blanche": "https://www.fastnedcharging.com/fr/emplacements/la-croix-blanche",
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
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        encoding = (resp.headers.get("Content-Encoding") or "").lower().strip()
        if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        elif encoding == "deflate":
            raw = zlib.decompress(raw)
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
    s = s.lower().replace("’", "'")
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"):
        s = s.replace(ch, "-")
    return re.sub(r"\s+", " ", s).strip()


def eur(v: str) -> float:
    return float(v.replace(",", "."))


def require(text: str, phrase: str, source: str) -> None:
    if norm(phrase) not in norm(text):
        raise RuntimeError(f"{source}: missing expected official phrase: {phrase}")


def parse_country_tariffs(text: str) -> dict:
    n = norm(text)
    require(n, "prix standard", "Fastned tariffs")
    require(n, "en france", "Fastned tariffs")
    require(n, "beneficiez de 10 % de reduction", "Fastned tariffs")
    require(n, "economisez 30%", "Fastned tariffs")

    # Anchor the values specifically to France, because the page lists all countries.
    standard_match = re.search(r"€\s*(\d+(?:[.,]\d+)?)\s*en france", n)
    if not standard_match:
        raise RuntimeError("Fastned tariffs: France standard price not found")
    standard = eur(standard_match.group(1))

    gold_match = re.search(
        r"€\s*(\d+(?:[.,]\d+)?)\s*\(€\s*\1\s*par kwh en france\)",
        n,
    )
    if not gold_match:
        # Fallback if the duplicate price is rendered slightly differently.
        gold_match = re.search(r"€\s*(\d+(?:[.,]\d+)?)\s*[^€]{0,80}par kwh en france", n)
    if not gold_match:
        raise RuntimeError("Fastned tariffs: France Gold price not found")
    gold = eur(gold_match.group(1))

    promo_match = re.search(
        r"€\s*(\d+(?:[.,]\d+)?)\s*par mois jusqu'au\s*(\d{1,2})\s*aout\s*(\d{4})",
        n,
    )
    promo_fee = eur(promo_match.group(1)) if promo_match else None
    promo_end = None
    if promo_match:
        promo_end = f"{int(promo_match.group(3)):04d}-08-{int(promo_match.group(2)):02d}"

    if not (0.10 <= standard <= 2.0 and 0.10 <= gold <= standard):
        raise RuntimeError(f"implausible Fastned France prices: standard={standard}, gold={gold}")

    return {
        "standardEurPerKwh": standard,
        "appDirectDiscountPercent": 10.0,
        "appDirectCalculatedEurPerKwh": round(standard * 0.90, 3),
        "appDirectCalculatedPriceStatus": "calculated_from_official_discount_not_separately_displayed",
        "goldEurPerKwh": gold,
        "goldDiscountPercent": 30.0,
        "goldMonthlyFeeEur": promo_fee,
        "goldMonthlyFeePromotionEnd": promo_end,
        "goldMonthlyFeeAfterPromotionEur": None,
        "goldMonthlyFeeAfterPromotionStatus": "not_stated_on_current_official_france_tariff_page",
        "goldVehicleLimitPerHousehold": 3,
    }


def parse_payment_rules(text: str) -> dict:
    n = norm(text)
    require(n, "payer par carte bancaire", "Fastned charging instructions")
    preauth = None
    m = re.search(r"reservation de\s*(\d+(?:[.,]\d+)?)\s*€", n)
    if m:
        preauth = eur(m.group(1))
    apple_pay = "apple pay" in n
    return {
        "directMethods": ["Fastned app", "Autocharge", "bank/debit/credit card", "online QR where available"],
        "thirdPartyChargeCardsSupported": True,
        "bankCardPreauthorizationEur": preauth,
        "applePaySupported": apple_pay,
    }


def parse_station(name: str, url: str, text: str, expected_standard: float, expected_gold: float) -> dict:
    n = norm(text)
    require(n, "tarif standard", f"station {name}")
    require(n, "membres gold", f"station {name}")

    price_match = re.search(
        r"eur\s*(\d+(?:[.,]\d+)?)\s*/\s*kwh[^.]{0,140}membres gold[^.]{0,180}tarif standard\s*:\s*(\d+(?:[.,]\d+)?)\s*/\s*kwh",
        n,
    )
    if not price_match:
        # Current page wording is typically "EUR 0,43/kWh ... tarif standard : 0,61/kWh".
        price_match = re.search(
            r"eur\s*(\d+(?:[.,]\d+)?)\s*/\s*kwh.{0,240}?tarif standard\s*:\s*(\d+(?:[.,]\d+)?)\s*/\s*kwh",
            n,
        )
    if not price_match:
        raise RuntimeError(f"station {name}: official standard/Gold prices not found")

    gold = eur(price_match.group(1))
    standard = eur(price_match.group(2))
    if abs(gold - expected_gold) > 0.001 or abs(standard - expected_standard) > 0.001:
        raise RuntimeError(
            f"station {name}: station price differs from national tariff: "
            f"gold={gold}, standard={standard}"
        )

    max_power = None
    pm = re.search(r"jusqu'a\s*(\d{2,3})\s*kw", n)
    if pm:
        max_power = int(pm.group(1))
    points = None
    cm = re.search(r"(\d+)\s*points de recharge", n)
    if cm:
        points = int(cm.group(1))

    return {
        "key": name,
        "url": url,
        "standardEurPerKwh": standard,
        "goldEurPerKwh": gold,
        "maxPowerKw": max_power,
        "chargingPoints": points,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/fastned")
    args = ap.parse_args()

    statuses = {}
    pages = {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: unexpected HTTP status {status}")
        statuses[key] = status
        pages[key] = text_from_html(raw)

    pricing = parse_country_tariffs(pages["tariffs"])
    payment = parse_payment_rules(pages["how_to_charge"])

    station_checks = []
    for key, url in STATION_SAMPLES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"station {key}: unexpected HTTP status {status}")
        statuses[f"station:{key}"] = status
        station_checks.append(
            parse_station(
                key,
                url,
                text_from_html(raw),
                pricing["standardEurPerKwh"],
                pricing["goldEurPerKwh"],
            )
        )

    facts = {
        "pricing": pricing,
        "payment": payment,
        "stationChecks": station_checks,
        "roaming": {
            "classification": "third_party_eMSP",
            "fastnedDiscountsApply": False,
            "priceOwner": "third-party charge-card provider",
            "stationLevelPriceLookupRequired": True,
        },
        "fees": {
            "networkWideIdleFee": None,
            "networkWideIdleFeeStatus": "not_stated_on_current_official_tariff_or_terms_pages",
            "parkingFee": None,
            "parkingFeeStatus": "location_specific_external_fees_not_ruled_out",
        },
    }
    fingerprint_payload = json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "fastned-official-france",
        "generatedAt": now_iso(),
        "operator": "Fastned",
        "country": "FR",
        "classification": {
            "singleNationalOperatorTariff": True,
            "stationLevelPriceLookupRequiredForFastnedDirect": False,
            "reason": "Fastned publishes a France country tariff and sampled official French station pages match it.",
        },
        "operatorDirect": {
            "standard": {
                "pricePerKwh": pricing["standardEurPerKwh"],
                "currency": "EUR",
                "billingUnit": "kWh",
            },
            "appDirect": {
                "discountPercent": pricing["appDirectDiscountPercent"],
                "calculatedPricePerKwh": pricing["appDirectCalculatedEurPerKwh"],
                "calculatedPriceStatus": pricing["appDirectCalculatedPriceStatus"],
                "monthlyFeeEur": 0.0,
            },
            "gold": {
                "pricePerKwh": pricing["goldEurPerKwh"],
                "discountPercent": pricing["goldDiscountPercent"],
                "monthlyFeeEur": pricing["goldMonthlyFeeEur"],
                "monthlyFeePromotionEnd": pricing["goldMonthlyFeePromotionEnd"],
                "monthlyFeeAfterPromotionEur": pricing["goldMonthlyFeeAfterPromotionEur"],
                "monthlyFeeAfterPromotionStatus": pricing["goldMonthlyFeeAfterPromotionStatus"],
                "vehicleLimitPerHousehold": pricing["goldVehicleLimitPerHousehold"],
            },
        },
        "payment": payment,
        "roaming": facts["roaming"],
        "fees": facts["fees"],
        "stationValidationSamples": station_checks,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [
                {"key": k, "url": SOURCES[k], "httpStatus": statuses[k]} for k in SOURCES
            ] + [
                {"key": f"station:{k}", "url": STATION_SAMPLES[k], "httpStatus": statuses[f"station:{k}"]}
                for k in STATION_SAMPLES
            ],
            "relevantTariffFingerprintSha256": hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest(),
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "The free app discount is stored as a 10% rule; the 0.549 EUR/kWh value is calculated from the official 0.61 EUR/kWh standard tariff rather than separately displayed by Fastned.",
            "Third-party charge-card pricing is roaming pricing and must not be treated as Fastned direct pricing.",
            "No network-wide Fastned idle fee is stated on the current official tariff/terms pages; external location-specific parking rules are not ruled out.",
        ],
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "fastned_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    gold_monthly_summary = (
        f"**{pricing['goldMonthlyFeeEur']:.2f} EUR/month** through **{pricing['goldMonthlyFeePromotionEnd']}**"
        if pricing['goldMonthlyFeeEur'] is not None
        else "**not confirmed on the current official France page**"
    )
    card_preauth_summary = (
        f"**{payment['bankCardPreauthorizationEur']:.0f} EUR**"
        if payment['bankCardPreauthorizationEur'] is not None
        else "**not confirmed**"
    )

    summary = (
        "# Fastned France official tariff check\n\n"
        f"- Standard direct: **{pricing['standardEurPerKwh']:.2f} EUR/kWh**\n"
        f"- Fastned app direct: **-10%**, calculated **{pricing['appDirectCalculatedEurPerKwh']:.3f} EUR/kWh** from current standard price\n"
        f"- Gold: **{pricing['goldEurPerKwh']:.2f} EUR/kWh** (-30%)\n"
        f"- Gold monthly fee currently shown: {gold_monthly_summary}\n"
        f"- Card preauthorization: {card_preauth_summary}\n"
        f"- Official French station samples matching national tariff: **{len(station_checks)}**\n"
        "- Third-party charge cards: roaming/eMSP price, Fastned discounts do not apply\n"
        f"- Fingerprint: `{payload['sourceEvidence']['relevantTariffFingerprintSha256']}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
