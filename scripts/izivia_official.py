#!/usr/bin/env python3
"""Extract public IZIVIA charging-pricing facts from official IZIVIA pages.

IZIVIA is both a CPO/operator and an eMSP (Pass IZIVIA). Unlike Lidl Plus, there is
no single national IZIVIA tariff. This extractor therefore keeps operator-direct
networks (FAST, Express, Grand Lyon) separate from Pass IZIVIA roaming policy.
It intentionally does not use authenticated APIs, private cookies or user data.
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
    "fast": "https://izivia.com/installation-bornes-de-recharge/izivia-bornes-recharge-ultra-rapide-mcdonalds-france",
    "express": "https://izivia.com/installation-bornes-de-recharge/izivia-express",
    "grand_lyon": "https://grandlyon.izivia.com/",
    "grand_lyon_offers": "https://grandlyon.izivia.com/nos-offres/",
    "pass": "https://izivia.com/pass-de-recharge-voitures-electriques",
    "roaming_fee": "https://izivia.com/questions-frequentes/service-recharge-izivia/quel-est-le-prix-d-une-recharge-hors-bornes-izivia",
    "paynow": "https://izivia.com/questions-frequentes/comment-utiliser-bornes-electriques/utiliser-borne-electrique-sans-carte-de-recharge",
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


def visible_text(raw_html: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw_html, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def extractable_text(raw_html: str) -> str:
    """Keep visible text plus script/JSON text as a fallback for dynamic pages."""
    visible = visible_text(raw_html)
    raw_flat = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
    raw_flat = raw_flat.replace("\\u20ac", "€").replace("\\/", "/")
    raw_flat = re.sub(r"\\u00([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), raw_flat)
    raw_flat = re.sub(r"\s+", " ", raw_flat).strip()
    return f"{visible} {raw_flat}".strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"):
        s = s.replace(ch, "-")
    s = s.lower().replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def eur(v: str) -> float:
    return float(v.replace(",", "."))


def require(text: str, phrase: str, source: str) -> None:
    if norm(phrase) not in norm(text):
        raise RuntimeError(f"{source}: missing expected official phrase: {phrase}")


def require_regex(text: str, pattern: str, source: str, label: str) -> None:
    if not re.search(pattern, norm(text), flags=re.I):
        raise RuntimeError(f"{source}: missing expected official tariff token: {label}")


def parse_fast(text: str) -> dict:
    n = norm(text)
    require(n, "izivia fast", "FAST")
    require(n, "happy hour", "FAST")
    m_price = re.search(r"kwh a partir de\s*(\d+(?:[.,]\d+)?)\s*€\s*en happy hour", n)
    if not m_price:
        raise RuntimeError("FAST: current official page no longer exposes the Happy Hour floor price")
    pows = [int(x) for x in re.findall(r"(?:de|a)\s*(\d{2,3})\s*kw", n)]
    for lo, hi in re.findall(r"(\d{2,3})\s*kw\s*a\s*(\d{2,3})\s*kw", n):
        pows.extend([int(lo), int(hi)])
    powers = sorted({x for x in pows if 50 <= x <= 400})
    return {
        "network": "IZIVIA FAST",
        "scope": "McDonald's France parking network",
        "operatorDirect": True,
        "stationLevelPriceLookupRequired": True,
        "powerKwObserved": powers,
        "pricing": {
            "happyHourFloorEurPerKwh": eur(m_price.group(1)),
            "standardTariff": None,
            "happyHourSchedule": None,
            "currentOfficialPageCompleteness": "partial",
        },
        "parkingFees": {"status": "not_stated_on_current_network_page"},
        "notes": [
            "Current official network page confirms only a Happy Hour price floor, not the complete tariff schedule.",
            "Do not infer a station tariff solely from the network-level floor price.",
        ],
    }


def parse_express(text: str) -> dict:
    n = norm(text)
    require(n, "izivia express", "Express")
    m = re.search(r"tarifs sont fixes entre\s*(\d+(?:[.,]\d+)?)\s*a\s*(\d+(?:[.,]\d+)?)\s*€\s*ttc\s*par\s*kwh", n)
    if not m:
        raise RuntimeError("Express: official tariff range not found")
    max_power = None
    mp = re.search(r"jusqu'a\s*(\d{2,3})\s*kw", n)
    if mp:
        max_power = int(mp.group(1))
    return {
        "network": "IZIVIA Express",
        "operatorDirect": True,
        "stationLevelPriceLookupRequired": True,
        "powerKwMax": max_power,
        "pricing": {
            "minEurPerKwh": eur(m.group(1)),
            "maxEurPerKwh": eur(m.group(2)),
            "billingUnit": "kWh",
            "currency": "EUR",
        },
        "paymentMethods": ["Pass IZIVIA", "roaming badge", "bank card / online payment where supported"],
        "parkingFees": {"status": "not_stated_on_current_network_page"},
    }


def parse_grand_lyon(text: str, offers_text: str) -> dict:
    n = norm(text)
    no = norm(offers_text)

    tariff_patterns = [
        (r"3[.,]50\s*€\s*/\s*h", "3.50 EUR/h"),
        (r"2[.,]50\s*€\s*/\s*h", "2.50 EUR/h"),
        (r"1[.,]50\s*€\s*/\s*h", "1.50 EUR/h"),
        (r"6\s*€\s*/\s*h", "6 EUR/h"),
        (r"5\s*€\s*/\s*h", "5 EUR/h"),
        (r"4\s*€\s*/\s*h", "4 EUR/h"),
        (r"0[.,]45\s*€\s*/\s*kwh", "0.45 EUR/kWh"),
        (r"0[.,]40\s*€\s*/\s*kwh", "0.40 EUR/kWh"),
        (r"0[.,]30\s*€\s*/\s*kwh", "0.30 EUR/kWh"),
        (r"0[.,]55\s*€\s*/\s*kwh", "0.55 EUR/kWh"),
        (r"0[.,]50\s*€\s*/\s*kwh", "0.50 EUR/kWh"),
        (r"\+?\s*0[.,]20\s*€\s*/\s*min\s*apres\s*45\s*min", "idle 0.20 EUR/min after 45 min"),
        (r"6\s*€\s*\+\s*0[.,]38\s*€\s*/\s*kwh\s*apres\s*20\s*kwh", "night visitor 6 + 0.38"),
        (r"5\s*€\s*\+\s*0[.,]38\s*€\s*/\s*kwh\s*apres\s*20\s*kwh", "night standard 5 + 0.38"),
        (r"4\s*€\s*\+\s*0[.,]38\s*€\s*/\s*kwh\s*apres\s*20\s*kwh", "night frequency 4 + 0.38"),
    ]
    for pattern, label in tariff_patterns:
        require_regex(n, pattern, "Grand Lyon", label)

    require(no, "stationnement n'est pas payant ni limite dans le temps", "Grand Lyon offers")
    require(no, "paynow.izivia.com", "Grand Lyon offers")

    return {
        "network": "IZIVIA Grand Lyon",
        "operatorDirect": True,
        "stationLevelPriceLookupRequired": False,
        "dayWindow": "08:00-20:00",
        "nightWindow": "20:00-08:00",
        "pricing": {
            "day": {
                "upTo7Kw": {"visitorEurPerHour": 3.50, "standardEurPerHour": 2.50, "frequencyEurPerHour": 1.50},
                "upTo24Kw": {"visitorEurPerHour": 6.00, "standardEurPerHour": 5.00, "frequencyEurPerHour": 4.00},
                "upTo50Kw": {"visitorEurPerKwh": 0.45, "standardEurPerKwh": 0.40, "frequencyEurPerKwh": 0.30, "afterMinutes": 45, "idleEurPerMin": 0.20},
                "from100Kw": {"visitorEurPerKwh": 0.55, "standardEurPerKwh": 0.50, "frequencyEurPerKwh": 0.40, "afterMinutes": 45, "idleEurPerMin": 0.20},
            },
            "night": {
                "upTo7Kw": {"visitorConnectionEur": 6.00, "standardConnectionEur": 5.00, "frequencyConnectionEur": 4.00, "includedKwh": 20, "afterIncludedEurPerKwh": 0.38},
                "upTo24Kw": {"visitorConnectionEur": 6.00, "standardConnectionEur": 5.00, "frequencyConnectionEur": 4.00, "includedKwh": 20, "afterIncludedEurPerKwh": 0.38},
                "upTo50Kw": {"visitorEurPerKwh": 0.45, "standardEurPerKwh": 0.40, "frequencyEurPerKwh": 0.30, "afterMinutes": 45, "idleEurPerMin": 0.20},
                "from100Kw": {"visitorEurPerKwh": 0.55, "standardEurPerKwh": 0.50, "frequencyEurPerKwh": 0.40, "afterMinutes": 45, "idleEurPerMin": 0.20},
            },
        },
        "parking": {
            "separateParkingFee": False,
            "officialNote": "Stationnement non payant et non limité; seul le service de recharge est payant.",
        },
        "adHoc": {"supported": True, "channel": "paynow.izivia.com", "usesVisitorTariff": True},
    }


def parse_pass(pass_text: str, roaming_text: str, paynow_text: str) -> dict:
    p = norm(pass_text)
    r = norm(roaming_text)
    q = norm(paynow_text)
    require(p, "sans abonnement", "Pass IZIVIA")
    m_pass = re.search(r"(\d+(?:[.,]\d+)?)\s*€\s*ttc\s*le pass izivia", p)
    if not m_pass:
        raise RuntimeError("Pass IZIVIA: Access pass purchase price not found")
    m_fee = re.search(r"frais de service de\s*(\d+(?:[.,]\d+)?)\s*%", r)
    if not m_fee:
        raise RuntimeError("Pass IZIVIA: current third-party service fee not found")
    require(q, "paynow", "PayNow")
    return {
        "product": "Pass IZIVIA Access",
        "classification": "eMSP_roaming",
        "operatorDirect": False,
        "purchasePriceEur": eur(m_pass.group(1)),
        "subscriptionEurPerMonth": 0.0,
        "thirdPartyNetworks": {
            "stationLevelPriceLookupRequired": True,
            "currentDefaultServiceFeePercent": eur(m_fee.group(1)),
            "rule": "third-party operator tariff plus IZIVIA service fee",
        },
        "adHocWithoutPass": {
            "supportedOnCompatibleStations": True,
            "channels": ["IZIVIA app", "paynow.izivia.com / station QR code"],
            "nationalTariff": None,
            "stationLevelPriceLookupRequired": True,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/izivia")
    args = ap.parse_args()

    pages = {}
    statuses = {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: unexpected HTTP status {status}")
        pages[key] = extractable_text(raw)
        statuses[key] = status

    fast = parse_fast(pages["fast"])
    express = parse_express(pages["express"])
    grand = parse_grand_lyon(pages["grand_lyon"], pages["grand_lyon_offers"])
    pass_rule = parse_pass(pages["pass"], pages["roaming_fee"], pages["paynow"])

    facts = {"fast": fast, "express": express, "grandLyon": grand, "passIzivia": pass_rule}
    fingerprint_payload = json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "izivia-official-france",
        "generatedAt": now_iso(),
        "operator": "IZIVIA / EDF business services",
        "country": "FR",
        "classification": {
            "singleNationalOperatorTariff": False,
            "reason": "IZIVIA operates multiple networks with distinct tariff grids and also acts as an eMSP via Pass IZIVIA.",
        },
        "operatorDirectNetworks": [fast, express, grand],
        "mobilityProvider": pass_rule,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": SOURCES[k], "httpStatus": statuses[k]} for k in SOURCES],
            "relevantTariffFingerprintSha256": hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest(),
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "FAST and Express require station-level tariff lookup for exact trip simulation.",
            "Grand Lyon has a complete official network-level tariff grid and can be modelled without station-specific price lookup, subject to power class and time window.",
            "Pass IZIVIA roaming must never be confused with the direct CPO tariff of the station operator.",
        ],
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "izivia_official_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = (
        "# IZIVIA official tariff check\n\n"
        f"- FAST: Happy Hour floor **{fast['pricing']['happyHourFloorEurPerKwh']:.2f} EUR/kWh**; exact current station tariff still requires lookup.\n"
        f"- Express: official range **{express['pricing']['minEurPerKwh']:.2f}-{express['pricing']['maxEurPerKwh']:.2f} EUR/kWh**; station lookup required.\n"
        "- Grand Lyon: complete official visitor / Standard / Frequency day-night matrix captured.\n"
        f"- Pass IZIVIA Access: **{pass_rule['purchasePriceEur']:.2f} EUR**, no subscription; third-party service fee currently **{pass_rule['thirdPartyNetworks']['currentDefaultServiceFeePercent']:.0f}%**.\n"
        "- Ad-hoc: supported on compatible stations via app / PayNow; no national ad-hoc tariff.\n"
        f"- Fingerprint: `{payload['sourceEvidence']['relevantTariffFingerprintSha256']}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
