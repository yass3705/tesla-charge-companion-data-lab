#!/usr/bin/env python3
"""Extract deer GmbH's official own-network ad-hoc charging tariff.

The deer consumer page publishes one AC+DC ad-hoc price for charging directly
via QR code at a deer charging station, plus a blocking fee. This artifact is
staging-only and deliberately applies only to the exact BNetzA operator name.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.deer-mobility.de/laden-unterwegs/"
UA = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch():
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,*/*",
            "Accept-Language": "de-DE,de;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
        status = getattr(r, "status", 200)
        ctype = r.headers.get("Content-Type")
    return raw, {
        "url": URL,
        "status": status,
        "contentType": ctype,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def textify(raw: bytes) -> str:
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def euro(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def main():
    raw, transport = fetch()
    text = textify(raw)

    section_match = re.search(
        r"Ad-hoc\s+Ladetarif(?P<section>.*?)(?:Roaming\s+Ladetarif|Lade\s+im\s+Partnertarif)",
        text,
        re.I,
    )
    if not section_match:
        raise RuntimeError("Could not isolate deer ad-hoc tariff section")
    section = section_match.group("section")

    price_match = re.search(
        r"AC\s*\+\s*DC\s+Strompreis\s*([0-9]+[,.][0-9]{2})\s*€\s*/\s*kWh",
        section,
        re.I,
    )
    block_match = re.search(
        r"Blockiergebühr.*?([0-9]+[,.][0-9]{2})\s*€\s*/\s*Min\..*?ab\s*Min\.\s*(\d+).*?max\.\s*([0-9]+[,.][0-9]{2})\s*€",
        section,
        re.I,
    )
    scope_ok = bool(
        re.search(
            r"direkt\s+über\s+den\s+QR-Code\s+an\s+einer\s+deer\s+Ladesäule",
            section,
            re.I,
        )
    )
    no_registration = bool(re.search(r"nicht\s+als\s+deer-LadekundIn\s+registriert", section, re.I))

    if not price_match:
        raise RuntimeError("Could not parse deer AC+DC ad-hoc energy price")
    if not block_match:
        raise RuntimeError("Could not parse deer ad-hoc blocking fee")
    if not (scope_ok and no_registration):
        raise RuntimeError("Could not validate deer own-network QR/ad-hoc scope")

    price = euro(price_match.group(1))
    block_per_minute = euro(block_match.group(1))
    first_charged_minute = int(block_match.group(2))
    block_cap = euro(block_match.group(3))
    if first_charged_minute < 2:
        raise RuntimeError("Invalid blocking-fee threshold")

    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-deer-direct-tariff",
        "countryCode": "DE",
        "generatedAt": now(),
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "operatorOwnNetworkOnly": True,
            "adHocOnly": True,
            "siteScalarPriceSafe": True,
        },
        "source": transport,
        "operator": {
            "canonicalName": "deer",
            "bnetzaExactOperators": ["deer GmbH"],
        },
        "directOwnNetwork": {
            "currency": "EUR",
            "eurPerKwh": price,
            "acDcSamePrice": True,
            "accessMethod": "ad_hoc_qr",
            "registrationRequired": False,
            "blockingFee": {
                "afterMinutes": first_charged_minute - 1,
                "firstChargedMinute": first_charged_minute,
                "eurPerMinute": block_per_minute,
                "capEurPerSession": block_cap,
            },
            "rankableCandidate": True,
        },
        "evidence": {
            "officialOwnNetworkQrScopeConfirmed": scope_ok,
            "noRegistrationRequired": no_registration,
            "tariffSection": "Ad-hoc Ladetarif",
        },
    }

    out = Path("data/germany/deer_direct_tariff.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_DEER_DIRECT_TARIFF=" + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
