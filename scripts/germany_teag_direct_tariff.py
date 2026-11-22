#!/usr/bin/env python3
"""Extract TEAG Mobil's official own-network app tariff and active 29-ab-29 promo.

The public TEAG pages currently publish a normal 0.49 EUR/kWh app tariff at
TEAG Mobil charge points and a temporary app-only promotion: kWh 1-28 at
0.49 EUR/kWh, then 0.29 EUR/kWh from the 29th kWh through 2026-09-30.
Other payment/access methods explicitly use the price shown at the station or in
the billing system, so this artifact must never be used as an ad-hoc station
fallback. It is staging/research evidence only until the TCC billing model can
represent the energy-volume tier exactly.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://www.teag-mobil.de/ladeapp"
PROMO_URL = "https://www.teag-mobil.de/default"
UA = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
        return raw, {
            "requestedUrl": url,
            "url": r.geturl(),
            "status": getattr(r, "status", 200),
            "contentType": r.headers.get("Content-Type"),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }


def textify(raw: bytes) -> str:
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    base_raw, base_source = fetch(BASE_URL)
    promo_raw, promo_source = fetch(PROMO_URL)
    base = textify(base_raw)
    promo = textify(promo_raw)

    base_price = re.search(
        r"Vorteilspreis\s+von\s+49\s+Cent\s*/\s*kWh\s+an\s+TEAG\s+Mobil-Ladepunkten",
        base,
        re.I,
    )
    no_base_fee = bool(re.search(r"49\s+Cent\s*/\s*kWh.*?ohne\s+Grundgebühr", base, re.I))

    promo_checks = {
        "firstTier": bool(re.search(r"1\s*[–-]\s*28\s*kWh.*?49\s*ct\s*/\s*kWh", promo, re.I)),
        "secondTier": bool(re.search(r"ab\s+der\s+29\.?\s*(?:geladenen\s+)?kWh.*?29\s*ct\s*/\s*kWh", promo, re.I)),
        "validity": bool(re.search(r"23\.07\.2026.*?30\.09\.2026", promo, re.I)),
        "teagStationsOnly": bool(re.search(r"ausschließlich.*?TEAG\s+Mobil-Ladesäulen", promo, re.I)),
        "appOnly": bool(re.search(r"über\s+die\s+TEAG\s+Mobil\s+Ladeapp\s+gestartet\s+und\s+abgerechnet", promo, re.I)),
        "otherMethodsStationPrice": bool(re.search(r"anderen\s+Zahlungsmethoden.*?an\s+der\s+Ladesäule.*?ausgewiesenen\s+Tarife", promo, re.I)),
    }

    if not base_price or not no_base_fee:
        raise RuntimeError("TEAG normal app tariff evidence changed")
    if not all(promo_checks.values()):
        raise RuntimeError(f"TEAG 29-ab-29 promotion evidence changed: {promo_checks}")

    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-teag-direct-app-tariff",
        "countryCode": "DE",
        "generatedAt": now(),
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "operatorOwnNetworkOnly": True,
            "appOnly": True,
            "adHocFallbackSafe": False,
            "requiresEnergyVolumeTierBilling": True,
            "productionRankable": False,
        },
        "operator": {
            "canonicalName": "TEAG Mobil",
            "bnetzaExactOperators": ["TEAG Mobil GmbH"],
            "evsePartyPrefixes": ["DETMO"],
        },
        "sources": {
            "normalAppTariff": base_source,
            "activePromotion": promo_source,
        },
        "normalAppTariff": {
            "currency": "EUR",
            "eurPerKwh": 0.49,
            "monthlyFeeEur": 0.0,
            "networkScope": "TEAG Mobil-Ladepunkte",
        },
        "activePromotion": {
            "name": "29 ab 29",
            "validFrom": "2026-07-23",
            "validThrough": "2026-09-30",
            "currency": "EUR",
            "taxIncluded": True,
            "networkScope": "TEAG Mobil-Ladesäulen",
            "accessMethod": "TEAG Mobil Ladeapp",
            "energyTiers": [
                {"fromKwhInclusive": 0.0, "toKwhInclusive": 28.0, "eurPerKwh": 0.49},
                {"fromKwhExclusive": 28.0, "eurPerKwh": 0.29},
            ],
            "otherPaymentMethodsUseStationOrBillingSystemDisplayedTariff": True,
        },
        "evidence": promo_checks,
    }

    out = Path("data/germany/teag_direct_app_tariff.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_TEAG_DIRECT_APP_TARIFF=" + json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
