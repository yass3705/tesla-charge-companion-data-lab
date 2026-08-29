#!/usr/bin/env python3
"""Extract the current German Pfalzwerke ad-hoc own-network tariff.

The official consumer page may also contain temporary promotional pricing. This
extractor deliberately validates only the dedicated 'Preise für das Ad-Hoc-Laden'
section and ignores promotional banners. Output is staging-only.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.pfalzwerke.de/privatkunden/emobilitaet/unterwegs-laden"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def textify(raw: bytes):
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " ")).strip()


def fetch():
    req = urllib.request.Request(URL, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
        meta = {
            "url": r.geturl(),
            "requestedUrl": URL,
            "status": getattr(r, "status", 200),
            "contentType": r.headers.get("Content-Type"),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    return raw, meta


def main():
    raw, source = fetch()
    text = textify(raw)
    m = re.search(
        r"Preise\s+für\s+das\s+Ad-Hoc-Laden\s+an\s+Pfalzwerke\s+Ladestationen(.{1,1800}?)Finden\s+Sie\s+E-Mobility-Ladestationen",
        text,
        re.I | re.S,
    )
    if not m:
        raise RuntimeError("official Pfalzwerke ad-hoc tariff section not found")
    section = m.group(1)
    ac = re.search(r"\bAC\s*:\s*58\s*Cent\s*/?\s*kWh", section, re.I)
    dc = re.search(r"\bDC\s*:\s*79\s*Cent\s*/?\s*kWh", section, re.I)
    all_sites = re.search(r"Gültig\s+an\s+allen\s+Pfalzwerke\s+Ladestationen", section, re.I)
    vat = re.search(r"Alle\s+Preise\s+inkl\.?\s*MwSt", section, re.I)
    no_account = re.search(r"Ohne\s+Registrierung|Kein\s+Kundenkonto\s+notwendig", section, re.I)
    if not all((ac, dc, all_sites, vat, no_account)):
        raise RuntimeError("Pfalzwerke ad-hoc tariff evidence changed; refusing stale tariff")

    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-pfalzwerke-direct-tariff",
        "countryCode": "DE",
        "generatedAt": utc_now(),
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "operatorOwnNetworkOnly": True,
            "adHocWithoutAccount": True,
            "connectorClassRequired": True,
            "promotionBannerIgnored": True,
            "productionRankable": False,
        },
        "source": source,
        "operator": {
            "canonicalName": "Pfalzwerke",
            "bnetzaExactOperators": ["Pfalzwerke AG"],
        },
        "directOwnNetwork": {
            "accessMethod": "ad-hoc-credit-card",
            "currency": "EUR",
            "taxIncluded": True,
            "monthlyFeeEur": 0.0,
            "connectorClassTariffs": {
                "AC": {"eurPerKwh": 0.58, "currency": "EUR", "taxIncluded": True},
                "DC": {"eurPerKwh": 0.79, "currency": "EUR", "taxIncluded": True},
            },
            "blockingFee": {
                "status": "not_stated_in_official_ad_hoc_price_section",
                "assumedZero": False,
            },
            "siteScalarPriceSafe": False,
            "rankableCandidateWhenConnectorClassKnown": True,
        },
    }
    out = Path("data/germany/pfalzwerke_direct_tariff.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_PFALZWERKE_DIRECT_TARIFF=" + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
