#!/usr/bin/env python3
"""Extract IECharge France direct-tariff rules from official public sources."""
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
    "pricing": "https://iecharge.io/fr/prix/",
    "faq": "https://iecharge.io/fr/faq-fr/",
    "stations": "https://iecharge.io/fr/stations/",
    "networkDesign": "https://iecharge.io/fr/emplacement-stations-iecharge-en-france/",
    "current2026": "https://iecharge.io/fr/numero-un-en-rapport-qualite-prix/",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
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


def require_any(text: str, needles: tuple[str, ...], label: str) -> None:
    n = norm(text)
    if not any(norm(x) in n for x in needles):
        raise RuntimeError(f"{label}: expected official evidence not found")


def has_price(text: str, value: float) -> bool:
    whole, frac = f"{value:.2f}".split(".")
    return bool(re.search(rf"(?<!\d){whole}[,.]{frac}(?!\d)\s*€?\s*/?\s*kwh", norm(text), flags=re.I))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/iecharge")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    texts: dict[str, str] = {}
    statuses: dict[str, int] = {}
    for key, url in SOURCES.items():
        status, raw = fetch(url)
        if status != 200:
            raise RuntimeError(f"{key}: HTTP {status}")
        statuses[key] = status
        texts[key] = text_from_html(raw)

    pricing = norm(texts["pricing"])
    faq = norm(texts["faq"])
    stations = norm(texts["stations"])
    design = norm(texts["networkDesign"])
    current = norm(texts["current2026"])

    if not has_price(pricing, 0.25):
        raise RuntimeError("IECharge current 0.25 EUR/kWh direct price not found")
    require_any(pricing, ("jusqu'a 320 kw", "jusqu’à 320 kw", "320 kw"), "IECharge max power")
    require_any(pricing, ("via l'application", "application iecharge"), "IECharge app direct payment")
    require_any(pricing, ("par carte bancaire", "carte bancaire"), "IECharge bank-card direct payment")
    require_any(pricing, ("votre fournisseur peut vous facturer un tarif different", "fournisseur peut vous facturer"), "IECharge eMSP separation")
    require_any(pricing, ("20€", "20 €", "jusqu'a 20", "jusqu’à 20"), "IECharge card reservation")
    require_any(current, ("0,25", "0.25"), "IECharge 2026 current price corroboration")
    require_any(current, ("meilleur tarif actuel", "meilleur tarif"), "IECharge 2026 current status")
    require_any(stations, ("4 points de charge", "quatre points de charge"), "IECharge points per station")
    require_any(design, ("deux de 320 kw", "deux de 320kw"), "IECharge 320 kW points")
    require_any(design, ("deux de 160kw", "deux de 160 kw"), "IECharge 160 kW points")
    require_any(faq, ("vous verrez egalement le prix", "vous verrez également le prix"), "IECharge price shown in app")

    live_count = None
    m = re.search(r"en service\s*(\d{2,4})", stations)
    if m:
        live_count = int(m.group(1))

    facts = {
        "classification": {
            "singleNationalDirectTariff": True,
            "stationLevelPriceLookupRequiredForIEChargeDirect": False,
            "thirdPartyEmspPriceCanDiffer": True,
        },
        "operatorDirect": {
            "highPowerFrance": {
                "eurPerKwh": 0.25,
                "maxPowerKwPublished": 320,
                "geography": "France",
                "paymentMethods": ["IECharge app", "bank card"],
                "subscriptionRequired": False,
            },
            "bankCard": {
                "eurPerKwh": 0.25,
                "preauthorizationOrReservationEur": 20.0,
                "unusedAmountReleaseStatedWithinHours": 24,
            },
        },
        "roaming": {
            "classification": "third_party_eMSP",
            "operatorDirect": False,
            "rfidSupported": True,
            "providerMayChargeDifferentTariff": True,
        },
        "fees": {
            "idleOrOccupation": {
                "status": "not_stated_network_wide_on_current_official_pricing_or_faq",
                "eurPerMin": None,
            },
            "parking": {
                "status": "site_specific_not_asserted_network_wide",
            },
        },
        "network": {
            "officialMapProvidesLiveStatus": True,
            "liveStationCountObserved": live_count,
            "typicalPointsPerStationPublished": 4,
            "publishedStationDesign": {
                "points320Kw": 2,
                "points160Kw": 2,
                "sourceIsOfficialNetworkDesignArticle": True,
            },
        },
    }

    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "iecharge-official-france",
        "generatedAt": now_iso(),
        "operator": "IECharge",
        "country": "FR",
        **facts,
        "sourceEvidence": {
            "officialOnly": True,
            "sources": [{"key": k, "url": u, "httpStatus": statuses[k]} for k, u in SOURCES.items()],
            "relevantTariffFingerprintSha256": fingerprint,
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "0.25 EUR/kWh is the current published IECharge direct France high-power tariff.",
            "Third-party RFID/eMSP pricing must remain separate because the provider may charge a different rate.",
            "No network-wide idle or parking fee is asserted without explicit current official evidence.",
            "The live station count is an observed website counter and may change independently of tariff evidence.",
        ],
    }
    (out / "iecharge_official_france.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = (
        "# IECharge France official check\n\n"
        "- Direct national tariff: **0.25 EUR/kWh**.\n"
        "- Published maximum power: **320 kW**.\n"
        "- Direct methods: **IECharge app / bank card**.\n"
        "- Bank-card reservation/preauthorization: **20 EUR**, unused amount released within 24 h.\n"
        "- Third-party RFID: **eMSP tariff may differ**.\n"
        "- Subscription required for direct price: **no**.\n"
        "- Network-wide idle/parking fee: **not asserted** from current official sources.\n"
        f"- Live station counter observed: **{live_count}**.\n"
        f"- Fingerprint: `{fingerprint}`\n"
    )
    (out / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
