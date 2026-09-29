#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://www.lidl.co.uk/c/electric-vehicle-charging/s10049808"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
ROOT = Path(__file__).resolve().parents[1]
OUT_DATA = ROOT / "data/national/uk_lidl_official_pricing.json"
OUT_REPORT = ROOT / "reports/uk/lidl-official-pricing-latest.json"

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def visible_text(raw):
    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()

def fetch():
    req = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-GB,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        return int(getattr(r, "status", 200)), r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")

status, raw = fetch()
if status != 200:
    raise SystemExit(f"unexpected HTTP {status}")

text = visible_text(raw)

patterns = {
    "lidlPlusAC": [
        r"tariff for AC Charging is £\s*([0-9]+(?:\.[0-9]+)?)\s*/?kWh",
        r"Fast Charger Tariff.{0,250}?£\s*([0-9]+(?:\.[0-9]+)?)\s*/?kWh with the Lidl Plus",
    ],
    "lidlPlusDC": [
        r"tariff for DC Charging is £\s*([0-9]+(?:\.[0-9]+)?)\s*/?kWh",
        r"Rapid Charger Tariff.{0,250}?£\s*([0-9]+(?:\.[0-9]+)?)\s*/?kWh with the Lidl Plus",
    ],
    "adhocFast": [
        r"Fast Charger Tariff.{0,350}?£\s*([0-9]+(?:\.[0-9]+)?)\s*/?kWh through the third-party website",
    ],
    "adhocRapid": [
        r"Rapid Charger Tariff.{0,400}?£\s*([0-9]+(?:\.[0-9]+)?)\s*/?kWh through the third-party website",
    ],
}

def one(key):
    for p in patterns[key]:
        m = re.search(p, text, flags=re.I | re.S)
        if m:
            return float(m.group(1))
    return None

vals = {k: one(k) for k in patterns}
if any(v is None for v in vals.values()):
    raise SystemExit("could not parse all four Lidl GB tariff values: " + json.dumps(vals))

for k,v in vals.items():
    if not (0.05 <= v <= 2.0):
        raise SystemExit(f"implausible tariff {k}={v}")

payload = {
    "schemaVersion": 1,
    "country": "GB",
    "operator": "Lidl Great Britain Limited",
    "retrievedAt": now_iso(),
    "sourceUrl": SOURCE_URL,
    "officialSource": True,
    "pricingComplete": True,
    "pricing": {
        "lidlPlus": {
            "AC_GBP_per_kWh": vals["lidlPlusAC"],
            "DC_GBP_per_kWh": vals["lidlPlusDC"],
        },
        "adhoc": {
            "fast_GBP_per_kWh": vals["adhocFast"],
            "rapid_GBP_per_kWh": vals["adhocRapid"],
        },
    },
    "inventoryStatus": "not_collected_by_this_script",
    "notes": [
        "Official Lidl GB page states Lidl owns/operates its GB charge points.",
        "Tariffs are network-level published tariffs; station inventory remains a separate problem.",
        "No authenticated Lidl Plus session or paid API is used."
    ],
}

for p in (OUT_DATA, OUT_REPORT):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(json.dumps(payload, ensure_ascii=False, indent=2))
