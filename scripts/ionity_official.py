#!/usr/bin/env python3
"""Extract current IONITY France tariff families from official public pages."""
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

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

SOURCES = {
    "access": "https://www.ionity.eu/fr/reseau/acces-et-paiements",
    "pricingFaq": "https://support.ionity.eu/fr/faqs/combien-coute-la-recharge-chez-ionity",
    "subscriptions": "https://support.ionity.eu/fr/faqs/ionity-motion-et-power-abonnements",
    "terms": "https://support.ionity.eu/fr/faqs/what-are-the-conditions-of-ionity-subscriptions",
    "preauth": "https://support.ionity.eu/fr/faqs/pourquoi-ma-carte-de-credit-est-elle-preautorisee-ai-je-ete-debite-deux-fois",
    "priceChange": "https://www.ionity.eu/fr/stories/pourquoi-les-prix-de-recharge-evoluent-ils-en-europe",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
        "Cache-Control": "no-cache",
    })
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
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        s = s.replace(ch, "-")
    return re.sub(r"\s+", " ", s).strip()


def number_before_label(block: str, label: str, currency: bool = False) -> float:
    n = norm(block)
    lbl = re.escape(norm(label))
    if currency:
        pat = rf"(?:€\s*)?(\d+(?:[.,]\d+)?)\s*{lbl}"
    else:
        pat = rf"(\d+(?:[.,]\d+)?)\s*€?\s*/\s*kwh\s*{lbl}"
    m = re.search(pat, n, flags=re.I)
    if not m:
        raise RuntimeError(f"IONITY France pricing label not found: {label}")
    return float(m.group(1).replace(",", "."))


def france_block(text: str) -> str:
    n = norm(text)
    candidates = [m.start() for m in re.finditer(r"\bfrance\b", n)]
    for pos in candidates:
        chunk = n[pos:pos + 1800]
        if "prix direct en kwh" in chunk and "motion-monthly-kwh-price" in chunk and "power-monthly-kwh-price" in chunk:
            return chunk
    raise RuntimeError("IONITY France tariff block not found in official pricing page")


def parse_france_tariffs(text: str) -> dict:
    b = france_block(text)
    result = {
        "directEurPerKwhFrom": number_before_label(b, "prix direct en kwh"),
        "appEurPerKwhFrom": number_before_label(b, "prix en kwh-go"),
        "powerMonthly": {
            "monthlyFeeEur": number_before_label(b, "prix mensuel de l'electricite", currency=True),
            "eurPerKwhFrom": number_before_label(b, "power-monthly-kwh-price"),
        },
        "motionMonthly": {
            "monthlyFeeEur": number_before_label(b, "prix mensuel du mouvement", currency=True),
            "eurPerKwhFrom": number_before_label(b, "motion-monthly-kwh-price"),
        },
        "power365": {
            "regularAnnualFeeEur": number_before_label(b, "prix annuel de l'electricite", currency=True),
            "currentReducedAnnualFeeEur": number_before_label(b, "prix reduit annuel power", currency=True),
            "eurPerKwhFrom": number_before_label(b, "power-annual-kwh-price"),
        },
        "motion365": {
            "regularAnnualFeeEur": number_before_label(b, "prix annuel du mouvement", currency=True),
            "currentReducedAnnualFeeEur": number_before_label(b, "prix reduit annuel de motion", currency=True),
            "eurPerKwhFrom": number_before_label(b, "motion-annual-kwh-price"),
        },
    }
    vals = [
        result["directEurPerKwhFrom"], result["appEurPerKwhFrom"],
        result["powerMonthly"]["eurPerKwhFrom"], result["motionMonthly"]["eurPerKwhFrom"],
        result["power365"]["eurPerKwhFrom"], result["motion365"]["eurPerKwhFrom"],
    ]
    if not all(0.10 <= x <= 2.0 for x in vals):
        raise RuntimeError(f"IONITY France implausible kWh tariff values: {vals}")
    return result


def require(text: str, phrase: str, source: str) -> None:
    if norm(phrase) not in norm(text):
        raise RuntimeError(f"{source}: expected phrase missing: {phrase}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/ionity")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    statuses, texts = {}, {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: unexpected HTTP status {status}")
        statuses[key] = status
        texts[key] = text_from_html(raw)

    tariffs = parse_france_tariffs(texts["access"])

    require(texts["pricingFaq"], "les prix peuvent varier d'un site à l'autre", "IONITY pricing FAQ")
    require(texts["pricingFaq"], "fournisseurs de services de mobilité", "IONITY pricing FAQ")
    require(texts["subscriptions"], "5,99", "IONITY subscriptions")
    require(texts["subscriptions"], "11,99", "IONITY subscriptions")
    require(texts["terms"], "23 pays", "IONITY subscription terms")
    require(texts["preauth"], "40 EUR", "IONITY preauthorization")
    require(texts["priceChange"], "1er juillet 2026", "IONITY price change")

    facts = {
        "tariffs": tariffs,
        "stationSpecific": True,
        "preauthorizationEur": 40.0,
        "monthlyNoMinimumTerm": True,
        "annualTermMonths": 12,
        "annualAutoRenew": False,
    }
    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "ionity-official-france",
        "generatedAt": now_iso(),
        "operator": "IONITY",
        "country": "FR",
        "classification": {
            "singleGuaranteedNationalTariff": False,
            "stationLevelPriceLookupRequiredForExactSimulation": True,
            "reason": "IONITY publishes France minimum prices, while exact kWh prices may vary by station even within France.",
        },
        "operatorDirect": {
            "directAdHoc": {
                "eurPerKwhFrom": tariffs["directEurPerKwhFrom"],
                "subscriptionFeeEur": 0.0,
                "payment": ["contactless card", "QR/payment site"],
            },
            "appNoSubscription": {
                "eurPerKwhFrom": tariffs["appEurPerKwhFrom"],
                "subscriptionFeeEur": 0.0,
            },
            "motionMonthly": tariffs["motionMonthly"],
            "powerMonthly": tariffs["powerMonthly"],
            "motion365": {**tariffs["motion365"], "termMonths": 12, "autoRenew": False},
            "power365": {**tariffs["power365"], "termMonths": 12, "autoRenew": False},
            "pricingRule": {
                "publishedValuesAreMinimums": True,
                "stationPriceMayBeHigher": True,
                "exactPriceShownBeforeSession": True,
                "newPriceRegimeEffective": "2026-07-01",
            },
        },
        "payment": {
            "cardPreauthorizationEur": 40.0,
            "preauthorizationAppliesToAppOrPaymentSite": True,
            "contactlessOnSiteSupportedWhereAvailable": True,
        },
        "roaming": {
            "classification": "third_party_MSP",
            "operatorDirect": False,
            "priceOwnedBy": "MSP",
            "stationLevelLookupRequired": True,
        },
        "fees": {
            "idleOrOccupation": {
                "status": "not_stated_network_wide_on_current_official_pricing_support_pages",
                "eurPerMin": None,
            },
        },
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "IONITY Direct, IONITY App, Motion/Power subscriptions and third-party MSP roaming are separate tariff families.",
            "All France kWh values stored here are official current minimums; exact station price must still be looked up before simulation.",
            "No network-wide idle/occupation fee is asserted because none is stated on the current official pricing/support pages checked by this extractor.",
        ],
    }

    (out / "ionity_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# IONITY France official tariff check\n\n"
        f"- Direct/ad hoc: from **{tariffs['directEurPerKwhFrom']:.2f} EUR/kWh**\n"
        f"- IONITY App: from **{tariffs['appEurPerKwhFrom']:.2f} EUR/kWh**\n"
        f"- Motion monthly: **{tariffs['motionMonthly']['monthlyFeeEur']:.2f} EUR/month** + from **{tariffs['motionMonthly']['eurPerKwhFrom']:.2f} EUR/kWh**\n"
        f"- Power monthly: **{tariffs['powerMonthly']['monthlyFeeEur']:.2f} EUR/month** + from **{tariffs['powerMonthly']['eurPerKwhFrom']:.2f} EUR/kWh**\n"
        f"- Motion 365: current annual fee **{tariffs['motion365']['currentReducedAnnualFeeEur']:.2f} EUR**, from **{tariffs['motion365']['eurPerKwhFrom']:.2f} EUR/kWh**\n"
        f"- Power 365: current annual fee **{tariffs['power365']['currentReducedAnnualFeeEur']:.2f} EUR**, from **{tariffs['power365']['eurPerKwhFrom']:.2f} EUR/kWh**\n"
        "- Exact station price lookup remains required.\n"
        "- Card preauthorization: **40 EUR**\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
