#!/usr/bin/env python3
"""Build an official Allego France station/EVSE direct-tariff inventory.

Scope is deliberately CPO-direct only. Allego station pages and Allego's public
charge-point price pages are authoritative for price. The Allego-published
Data.gouv IRVE file is used as an exhaustiveness cross-check, never as a roaming
price source. Country defaults are retained only as non-rankable diagnostics
when an exact station/EVSE price cannot be retrieved.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import io
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"
BASE = "https://www.allego.eu"
SITEMAPS = (f"{BASE}/sitemap.xml", f"{BASE}/sitemap_index.xml", f"{BASE}/sitemap-index.xml")
DATA_GOUV_RESOURCE_ID = "6523db3c-05f2-4c61-9308-e53a92deab37"
DATA_GOUV_URL = f"https://www.data.gouv.fr/fr/datasets/r/{DATA_GOUV_RESOURCE_ID}"
DEFAULT_OUT = Path("data/national/allego_direct_stations_france.json.gz")
DEFAULT_REPORT = Path("data/reports/allego_station_tariffs_report.json")
COUNTRY_DEFAULTS = {"regular": 0.39, "fast": 0.49, "ultraFast": 0.59}
PLUS_MONTHLY_FEE_EUR = 9.99


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = html.unescape(value).lower().replace("’", "'")
    return re.sub(r"\s+", " ", value).strip()


def fetch_text(url: str, attempts: int = 4, timeout: int = 40) -> str:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,fr;q=0.7", "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                enc = response.headers.get_content_charset() or "utf-8"
                return raw.decode(enc, errors="replace")
        except (OSError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(0.8 * (2 ** attempt))
    raise RuntimeError(f"request failed: {url}: {last}")


def text_from_html(raw: str) -> str:
    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def sitemap_locs(xml_text: str) -> tuple[str, list[str]]:
    root = ET.fromstring(xml_text)
    kind = root.tag.rsplit("}", 1)[-1].lower()
    locs = [e.text.strip() for e in root.iter() if e.tag.rsplit("}", 1)[-1].lower() == "loc" and e.text]
    return kind, locs


def station_url(url: str) -> str | None:
    p = urllib.parse.urlparse(url)
    if p.netloc.lower().replace("www.", "") != "allego.eu":
        return None
    m = re.search(r"/(?:[a-z]{2}/)?charging-station/([^/?#]+)/?$", p.path, re.I)
    if not m:
        return None
    return f"{BASE}/charging-station/{m.group(1)}/"


def discover_station_urls() -> tuple[str, list[str]]:
    root_url = ""
    root_xml = ""
    for candidate in SITEMAPS:
        try:
            root_xml = fetch_text(candidate)
            sitemap_locs(root_xml)
            root_url = candidate
            break
        except Exception:
            continue
    if not root_url:
        raise RuntimeError("no Allego sitemap available")
    queue: list[tuple[str, str | None]] = [(root_url, root_xml)]
    seen: set[str] = set()
    pages: set[str] = set()
    while queue:
        url, cached = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        kind, locs = sitemap_locs(cached if cached is not None else fetch_text(url))
        if kind == "sitemapindex":
            queue.extend((x, None) for x in locs if x not in seen)
        else:
            for loc in locs:
                canonical = station_url(loc)
                if canonical:
                    pages.add(canonical)
        if len(seen) > 150:
            raise RuntimeError("Allego sitemap recursion unexpectedly large")
    if len(pages) < 100:
        raise RuntimeError(f"Allego station sitemap unexpectedly small: {len(pages)}")
    return root_url, sorted(pages)


def extract_name(raw_html: str) -> str:
    m = re.search(r"<h1\b[^>]*>(.*?)</h1>", raw_html, re.I | re.S)
    return text_from_html(m.group(1)) if m else ""


def extract_evse_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in re.finditer(r"\b(FRALLEGO[0-9A-Z_-]{4,})\b", text, re.I):
        evse = match.group(1).upper()
        window = text[max(0, match.start() - 150):match.start()]
        powers = re.findall(r"(?:up to|jusqu['’]?a|jusqu’à)?\s*(\d{1,4}(?:[.,]\d+)?)\s*kW", window, re.I)
        power = float(powers[-1].replace(",", ".")) if powers else None
        rows.append({"evseId": evse, "powerKw": power, "kind": "DC" if power and power > 22.5 else "AC"})
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        old = dedup.get(row["evseId"])
        if old is None or (old.get("powerKw") is None and row.get("powerKw") is not None):
            dedup[row["evseId"]] = row
    return sorted(dedup.values(), key=lambda x: x["evseId"])


def extract_address(text: str) -> str:
    patterns = [
        r"\bLocation\s+(.*?)\s+(?:Plugs|Station status|Extra information)\b",
        r"\bLocalisation\s+(.*?)\s+(?:Bouchons|Statut de la station|Informations supplémentaires)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I | re.S)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def extract_direct_kind_prices(text: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    n = text.replace("€", "EUR")
    for kind in ("AC", "DC"):
        m = re.search(rf"\b{kind}\b\s*(\d+(?:[.,]\d+)?)\s*EUR\s*/\s*kWh", n, re.I)
        if m:
            value = float(m.group(1).replace(",", "."))
            if 0.05 <= value <= 2.0:
                prices[kind] = value
    return prices


def extract_named_offers(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    cleaned = re.sub(r"\s+", " ", text.replace("€", "EUR"))
    for key, label in (("direct", "Allego Direct"), ("smart", "Allego Smart"), ("plus", "Allego Plus")):
        m = re.search(rf"{re.escape(label)}.{{0,180}}?(\d+(?:[.,]\d+)?)\s*EUR\s*/\s*kWh", cleaned, re.I)
        if m:
            value = float(m.group(1).replace(",", "."))
            if 0.05 <= value <= 2.0:
                result[key] = value
    return result


def page_fee_evidence(text: str) -> dict[str, bool]:
    n = norm(text)
    return {
        "hpcIdleMentioned": "0.248" in n or "0.25/min" in n or "0.25 eur/min" in n,
        "regularOverstayMentioned": ("0.05" in n and ("overstay" in n or "depassement" in n or "dépassement" in text.lower())),
    }


def parse_station_page(url: str, raw_html: str) -> dict[str, Any] | None:
    text = text_from_html(raw_html)
    evses = extract_evse_rows(text)
    if not evses or "France" not in text:
        return None
    if not any(x["evseId"].startswith("FRALLEGO") for x in evses):
        return None
    name = extract_name(raw_html) or urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]
    return {
        "stationPageUrl": url,
        "name": name,
        "address": extract_address(text),
        "evses": evses,
        "staticDirectPrices": extract_direct_kind_prices(text),
        "staticNamedOffers": extract_named_offers(text),
        "feeEvidence": page_fee_evidence(text),
    }


def build_browser():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError as exc:
        raise RuntimeError("selenium is required with --browser") from exc
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1600")
    options.add_argument(f"--user-agent={UA}")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(35)
    return driver


def browser_text(driver, url: str, wait: float = 1.4) -> str:
    driver.get(url)
    time.sleep(wait)
    return re.sub(r"\s+", " ", driver.find_element("tag name", "body").text).strip()


def enrich_exact(station: dict[str, Any], driver) -> None:
    direct = dict(station.get("staticDirectPrices") or {})
    named = dict(station.get("staticNamedOffers") or {})
    evidence: list[str] = []
    if direct or named:
        evidence.append(station["stationPageUrl"])

    if driver is not None and (not direct or not named):
        try:
            rendered = browser_text(driver, station["stationPageUrl"])
            direct.update({k: v for k, v in extract_direct_kind_prices(rendered).items() if k not in direct})
            named.update({k: v for k, v in extract_named_offers(rendered).items() if k not in named})
            station["feeEvidence"].update(page_fee_evidence(rendered))
            evidence.append(station["stationPageUrl"] + "#rendered")
        except Exception as exc:
            station.setdefault("warnings", []).append(f"station_render_failed:{type(exc).__name__}")

    per_evse: dict[str, dict[str, float]] = {}
    if driver is not None and (not direct or not named):
        for evse in station["evses"]:
            evse_id = evse["evseId"]
            try:
                price_url = f"https://app.allego.eu/price/{urllib.parse.quote(evse_id)}"
                rendered = browser_text(driver, price_url, wait=1.1)
                offers = extract_named_offers(rendered)
                generic = re.search(r"(?:price|tarif).{0,100}?(\d+(?:[.,]\d+)?)\s*(?:EUR|€)\s*/\s*kWh", rendered, re.I)
                if generic and "direct" not in offers:
                    val = float(generic.group(1).replace(",", "."))
                    if 0.05 <= val <= 2.0:
                        offers["direct"] = val
                if offers:
                    per_evse[evse_id] = offers
                    evidence.append(price_url)
            except Exception as exc:
                station.setdefault("warnings", []).append(f"price_page_failed:{evse_id}:{type(exc).__name__}")

    station["exactDirectPricesByKind"] = direct
    station["exactNamedOffers"] = named
    station["exactOffersByEvse"] = per_evse
    station["priceEvidenceUrls"] = sorted(set(evidence))
    exact_evse = len(per_evse)
    exact_kind = bool(direct)
    if exact_evse == len(station["evses"]) and exact_evse:
        status = "exact_official_evse"
    elif exact_evse or exact_kind:
        status = "exact_official_station_partial"
    else:
        status = "lookup_required"
    station["pricingStatus"] = status
    station["rankableDirect"] = status != "lookup_required"


def fetch_data_gouv_ids() -> tuple[set[str], dict[str, Any]]:
    meta: dict[str, Any] = {"resourceId": DATA_GOUV_RESOURCE_ID, "url": DATA_GOUV_URL, "status": "unavailable"}
    try:
        raw = fetch_text(DATA_GOUV_URL)
        sample = raw[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        rows = csv.DictReader(io.StringIO(raw), dialect=dialect)
        ids: set[str] = set()
        count = 0
        for row in rows:
            count += 1
            for key in ("id_pdc_itinerance", "id_pdc_local", "id_pdc"):
                value = str(row.get(key) or "").strip().upper().replace("*", "")
                if value.startswith("FRALLEGO"):
                    ids.add(value)
        meta.update({"status": "ok", "rowCount": count, "allegoEvseCount": len(ids)})
        return ids, meta
    except Exception as exc:
        meta["error"] = f"{type(exc).__name__}: {exc}"
        return set(), meta


def make_payload(stations: list[dict[str, Any]], sitemap: str, data_gouv_ids: set[str], data_gouv_meta: dict[str, Any]) -> dict[str, Any]:
    stations = sorted(stations, key=lambda x: (x["name"].lower(), x["stationPageUrl"]))
    page_ids = {e["evseId"] for s in stations for e in s["evses"]}
    status_counts = Counter(s["pricingStatus"] for s in stations)
    exact_prices = Counter()
    for station in stations:
        for kind, price in station.get("exactDirectPricesByKind", {}).items():
            exact_prices[f"{kind}:{price:.3f}"] += 1
        for offers in station.get("exactOffersByEvse", {}).values():
            if "direct" in offers:
                exact_prices[f"EVSE:{offers['direct']:.3f}"] += 1
    return {
        "schemaVersion": "1.0.0",
        "dataset": "allego-direct-operated-stations-france",
        "generatedAt": now_iso(),
        "operator": "Allego",
        "country": "FR",
        "scope": {
            "operatorDirectOnly": True,
            "roamingIncluded": False,
            "stationOrEvseExactPriceRequiredForRanking": True,
            "countryDefaultsAreRankable": False,
            "countryDefaultsEurPerKwh": COUNTRY_DEFAULTS,
            "allegoPlusMonthlyFeeEur": PLUS_MONTHLY_FEE_EUR,
        },
        "fees": {
            "hpcIdle": {"eurPerMin": 0.248, "onlyWhenChargingEnded": True, "gracePeriodFromSessionStartMinutes": 45, "applyOnlyWithStationEvidence": True},
            "regularOverstay": {"eurPerMin": 0.05, "appliesAfterSessionStartMinutes": 300, "chargeWindowLocalTime": "07:00-23:00", "maximumChargedHours": 16, "applyOnlyWithStationEvidence": True},
        },
        "sources": {
            "stationSitemap": sitemap,
            "stationPages": "https://www.allego.eu/charging-station/<slug>/",
            "chargePointPricePages": "https://app.allego.eu/price/<FRALLEGO_EVSE_ID>",
            "dataGouv": data_gouv_meta,
        },
        "counts": {
            "franceStationCount": len(stations),
            "franceEvseCount": len(page_ids),
            "pricingStatusCounts": dict(sorted(status_counts.items())),
            "exactDirectPriceCounts": dict(sorted(exact_prices.items())),
            "dataGouvEvseCount": len(data_gouv_ids),
            "pageEvseMissingFromDataGouv": len(page_ids - data_gouv_ids) if data_gouv_ids else None,
            "dataGouvEvseMissingFromPages": len(data_gouv_ids - page_ids) if data_gouv_ids else None,
        },
        "matchPolicy": {"exactEvseIdFirst": True, "operatorMustBeAllego": True, "ambiguousOrDefaultOnlyFailsClosed": True},
        "stations": stations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--browser", action="store_true", help="Use headless Chrome for dynamic station/price pages")
    parser.add_argument("--max-stations", type=int, default=0, help="Debug limit only")
    args = parser.parse_args()

    sitemap, urls = discover_station_urls()
    stations: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for i, url in enumerate(urls):
        if args.max_stations and i >= args.max_stations:
            break
        try:
            station = parse_station_page(url, fetch_text(url))
            if station:
                stations.append(station)
        except Exception as exc:
            failures.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
    if len(stations) < 50 and not args.max_stations:
        raise RuntimeError(f"Allego France inventory unexpectedly small: {len(stations)}")

    driver = build_browser() if args.browser else None
    try:
        for idx, station in enumerate(stations, 1):
            enrich_exact(station, driver)
            if idx % 25 == 0:
                print(f"priced {idx}/{len(stations)} Allego France stations")
    finally:
        if driver is not None:
            driver.quit()

    data_gouv_ids, data_gouv_meta = fetch_data_gouv_ids()
    payload = make_payload(stations, sitemap, data_gouv_ids, data_gouv_meta)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out.suffix == ".gz":
        args.out.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))
    else:
        args.out.write_text(rendered, encoding="utf-8")

    report = {
        "generatedAt": payload["generatedAt"],
        "counts": payload["counts"],
        "fetchFailureCount": len(failures),
        "fetchFailures": failures[:100],
        "publicationReadyStationCount": sum(1 for s in stations if s["rankableDirect"]),
        "blockedStationCount": sum(1 for s in stations if not s["rankableDirect"]),
        "blockedStations": [{"name": s["name"], "url": s["stationPageUrl"], "evseIds": [e["evseId"] for e in s["evses"]]} for s in stations if not s["rankableDirect"]],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    print(f"Allego France: {len(stations)} stations / {payload['counts']['franceEvseCount']} EVSE / {report['publicationReadyStationCount']} rankable / sha256={digest}")


if __name__ == "__main__":
    main()
