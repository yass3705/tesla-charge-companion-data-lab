#!/usr/bin/env python3
"""Extract the public Lidl Plus France EV charging tariff from Lidl's official page.

This intentionally avoids authenticated Lidl Plus APIs. Lidl's public E-Mobility page
states both the current AC/DC Lidl Plus tariff and that Lidl charges the same per-kWh
tariff everywhere in France. The resulting dataset is therefore a network-level rule,
not a guessed station-level scrape.
"""
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

SOURCE_URL = "https://www.lidl.fr/c/e-mobilite/s10037236"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"


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
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return int(getattr(resp, "status", 200)), raw.decode(charset, errors="replace")


def visible_text(raw_html: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw_html, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("’", "'")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def section(text: str, start: str, end: str | None) -> str:
    low = norm(text)
    s = low.find(norm(start))
    if s < 0:
        raise RuntimeError(f"missing section: {start}")
    if end:
        e = low.find(norm(end), s + len(norm(start)))
        if e < 0:
            raise RuntimeError(f"missing section end: {end}")
        return low[s:e]
    return low[s:]


def parse_kwh_price(sec: str) -> float:
    # The DC section may contain a struck-out former price before the live price.
    # We keep the last normal EUR/kWh token in the section.
    vals = re.findall(
        r"(?<!\d)(\d+(?:[.,]\d{1,3})?)\s*€(?:\s*ttc)?\s*/\s*kwh",
        sec,
        flags=re.I,
    )
    if not vals:
        raise RuntimeError("no EUR/kWh price found in tariff section")
    return float(vals[-1].replace(",", "."))


def parse_preauth(sec: str) -> float | None:
    vals = re.findall(
        r"(?:pre[- ]?autorisation|empreinte bancaire|empreinte)[^€]{0,140}?(\d+(?:[.,]\d+)?)\s*€",
        sec,
        flags=re.I,
    )
    if not vals:
        return None
    return float(vals[-1].replace(",", "."))


def build_payload(raw_html: str, status: int) -> dict:
    text = visible_text(raw_html)
    text_norm = norm(text)

    dc = section(text, "Tarifs bornes de recharge DC", "Tarifs bornes de recharge AC")
    ac = section(text, "Tarifs bornes de recharge AC", "E-Mobilité - Protection des données")

    ac_price = parse_kwh_price(ac)
    dc_price = parse_kwh_price(dc)
    ac_preauth = parse_preauth(ac)
    dc_preauth = parse_preauth(dc)

    national_phrase = "meme tarif facture au kwh partout en france"
    national_scope = national_phrase in text_norm
    if not national_scope:
        raise RuntimeError("official page no longer confirms one tariff everywhere in France")

    if not (0.05 <= ac_price <= 2.0 and 0.05 <= dc_price <= 2.0):
        raise RuntimeError(f"implausible Lidl Plus tariff: AC={ac_price}, DC={dc_price}")

    dc_limited = "offre a duree limitee" in dc

    relevant = json.dumps(
        {
            "ac": ac_price,
            "dc": dc_price,
            "acPreauth": ac_preauth,
            "dcPreauth": dc_preauth,
            "dcLimited": dc_limited,
            "nationalScope": national_scope,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    return {
        "schemaVersion": "1.0.0",
        "dataset": "operator-direct-lidl-plus-france",
        "generatedAt": now_iso(),
        "source": "operator_direct",
        "provider": "Lidl Plus",
        "operator": "Lidl",
        "country": "FR",
        "networkScope": {
            "kind": "all_lidl_charging_sites_france",
            "confirmedByOfficialSource": True,
            "stationLevelPriceLookupRequired": False,
        },
        "pricing": [
            {
                "currentType": "AC",
                "pricePerKwh": ac_price,
                "currency": "EUR",
                "billingUnit": "kWh",
                "preauthorizationAmountEur": ac_preauth,
                "promotion": False,
            },
            {
                "currentType": "DC",
                "pricePerKwh": dc_price,
                "currency": "EUR",
                "billingUnit": "kWh",
                "preauthorizationAmountEur": dc_preauth,
                "promotion": dc_limited,
                "promotionEnd": None,
                "promotionEndSourceStatus": "not_stated_on_current_official_page" if dc_limited else "not_applicable",
            },
        ],
        "sourceEvidence": {
            "url": SOURCE_URL,
            "httpStatus": status,
            "officialPage": True,
            "sameTariffEverywhereFrance": national_scope,
            "relevantTariffFingerprintSha256": hashlib.sha256(relevant.encode()).hexdigest(),
        },
        "publicationStatus": "candidate_validated_source",
        "notes": [
            "This dataset represents Lidl Plus pricing, not Intercharge ad-hoc payment pricing.",
            "No authenticated account, cookie, token or private Lidl Plus API is used.",
        ],
    }


def summary(payload: dict) -> str:
    p = {x["currentType"]: x for x in payload["pricing"]}
    dc_note = " (limited-duration offer; end date not stated on current page)" if p["DC"]["promotion"] else ""
    return (
        "# Lidl Plus official tariff check\n\n"
        f"- AC: **{p['AC']['pricePerKwh']:.2f} EUR/kWh**\n"
        f"- DC: **{p['DC']['pricePerKwh']:.2f} EUR/kWh**{dc_note}\n"
        f"- Scope: **all Lidl charging sites in France**, per Lidl's official national-pricing statement\n"
        f"- Source: `{payload['sourceEvidence']['url']}`\n"
        f"- Source fingerprint: `{payload['sourceEvidence']['relevantTariffFingerprintSha256']}`\n"
        "- Classification: **Lidl Plus / operator_direct** (separate from Intercharge ad-hoc)\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/lidl-plus")
    args = ap.parse_args()

    status, raw = fetch(SOURCE_URL)
    if status != 200:
        raise RuntimeError(f"unexpected HTTP status {status}")

    payload = build_payload(raw, status)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "lidl_plus_france.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "SUMMARY.md").write_text(summary(payload), encoding="utf-8")
    print(summary(payload))


if __name__ == "__main__":
    main()
