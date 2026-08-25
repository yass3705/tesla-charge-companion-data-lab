#!/usr/bin/env python3
"""Build a national Fastned France CPO inventory from official Fastned pages.

The official Fastned site exposes one public location page per Fastned station.  The
French-language sitemap contains locations across Europe, so the build crawls those
pages and retains only pages whose official address is in France.  It then checks
that the station-level Standard/Gold prices match the current France country tariff.

The output is deliberately static: TCC keeps Electroverse/Electra as the live-status
authority.  This file supplies Fastned-operated station identity, coordinates,
technical metadata and direct operator pricing only.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import math
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
SITEMAP_CANDIDATES = (
    "https://www.fastnedcharging.com/sitemap.xml",
    "https://www.fastnedcharging.com/sitemap-index.xml",
    "https://www.fastnedcharging.com/sitemap_index.xml",
)
LOCATION_PATH_PREFIX = "/fr/emplacements/"
TARIFF_URL = "https://www.fastnedcharging.com/fr/recharge/tarifs"
DEFAULT_OUT = Path("data/national/fastned_direct_stations_france.json.gz")
MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("’", "'")
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"):
        value = value.replace(ch, "-")
    return re.sub(r"\s+", " ", value).strip()


def eur(value: str) -> float:
    return float(value.replace(",", "."))


def _decode_body(response: Any, raw: bytes) -> str:
    encoding = (response.headers.get("Content-Encoding") or "").lower().strip()
    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    elif encoding == "deflate":
        raw = zlib.decompress(raw)
    charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def fetch_text(url: str, attempts: int = 4) -> str:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
                    "Accept-Encoding": "gzip, deflate",
                    "Cache-Control": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=35) as response:
                status = int(getattr(response, "status", 200))
                if status != 200:
                    raise RuntimeError(f"unexpected HTTP {status} for {url}")
                return _decode_body(response, response.read())
        except (OSError, RuntimeError, urllib.error.HTTPError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(0.8 * (2**attempt))
    raise RuntimeError(f"Fastned request failed after {attempts} attempts: {url}: {last}")


def text_from_html(raw_html: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw_html, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def clean_fragment(fragment: str) -> str:
    return text_from_html(fragment).strip()


def canonical_location_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc.lower() not in {"www.fastnedcharging.com", "fastnedcharging.com"}:
        return None
    path = parsed.path.rstrip("/")
    if not path.startswith(LOCATION_PATH_PREFIX) or path == LOCATION_PATH_PREFIX.rstrip("/"):
        return None
    return urllib.parse.urlunparse(("https", "www.fastnedcharging.com", path, "", "", ""))


def _xml_locs(xml_text: str) -> tuple[str, list[str]]:
    root = ET.fromstring(xml_text)
    kind = root.tag.rsplit("}", 1)[-1].lower()
    locs: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() == "loc" and element.text:
            locs.append(element.text.strip())
    return kind, locs


def discover_location_urls(fetcher=fetch_text) -> tuple[str, list[str], int]:
    root_url = ""
    first_xml = ""
    errors: list[str] = []
    for candidate in SITEMAP_CANDIDATES:
        try:
            first_xml = fetcher(candidate)
            _xml_locs(first_xml)
            root_url = candidate
            break
        except Exception as exc:  # candidates intentionally probe standard sitemap names
            errors.append(f"{candidate}: {exc}")
    if not root_url:
        raise RuntimeError("no usable Fastned sitemap: " + " | ".join(errors))

    queue: list[tuple[str, str | None]] = [(root_url, first_xml)]
    seen_sitemaps: set[str] = set()
    pages: set[str] = set()
    sitemap_count = 0
    while queue:
        url, cached = queue.pop(0)
        if url in seen_sitemaps:
            continue
        seen_sitemaps.add(url)
        kind, locs = _xml_locs(cached if cached is not None else fetcher(url))
        sitemap_count += 1
        if sitemap_count > 100:
            raise RuntimeError("Fastned sitemap recursion unexpectedly large")
        if kind == "sitemapindex":
            for child in locs:
                if child not in seen_sitemaps:
                    queue.append((child, None))
            continue
        for loc in locs:
            canonical = canonical_location_url(loc)
            if canonical:
                pages.add(canonical)

    urls = sorted(pages)
    if len(urls) < 300:
        raise RuntimeError(f"Fastned French-language location inventory unexpectedly small: {len(urls)}")
    if len(urls) > 1200:
        raise RuntimeError(f"Fastned French-language location inventory unexpectedly large: {len(urls)}")
    return root_url, urls, sitemap_count


def parse_country_tariff(text: str) -> dict[str, Any]:
    n = norm(text)
    standard_match = re.search(r"€\s*(\d+(?:[.,]\d+)?)\s*en france", n)
    gold_match = re.search(r"€\s*(\d+(?:[.,]\d+)?)\s*\(€\s*\1\s*par kwh en france\)", n)
    if not standard_match or not gold_match:
        raise RuntimeError("Fastned France Standard/Gold tariff not found")
    standard = eur(standard_match.group(1))
    gold = eur(gold_match.group(1))
    if not (0.10 <= gold <= standard <= 2.0):
        raise RuntimeError(f"implausible Fastned France tariffs: standard={standard}, gold={gold}")
    if "beneficiez de 10 % de reduction" not in n or "economisez 30%" not in n:
        raise RuntimeError("Fastned France discount rules missing")

    promo_match = re.search(
        r"€\s*(\d+(?:[.,]\d+)?)\s*par mois jusqu'au\s*(\d{1,2})\s+([a-z]+)\s+(\d{4})",
        n,
    )
    promo_fee = None
    promo_end = None
    if promo_match:
        month = MONTHS.get(promo_match.group(3))
        if month:
            promo_fee = eur(promo_match.group(1))
            promo_end = f"{int(promo_match.group(4)):04d}-{month:02d}-{int(promo_match.group(2)):02d}"

    return {
        "standardEurPerKwh": standard,
        "appDirectDiscountPercent": 10.0,
        "appDirectEurPerKwh": round(standard * 0.90, 3),
        "goldEurPerKwh": gold,
        "goldDiscountPercent": 30.0,
        "goldMonthlyFeeEur": promo_fee,
        "goldMonthlyFeePromotionEnd": promo_end,
        "goldVehicleLimitPerHousehold": 3,
    }


def _first(pattern: str, text: str, flags: int = re.I | re.S) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def _coordinates(raw_html: str) -> tuple[float, float] | None:
    decoded = urllib.parse.unquote(html.unescape(raw_html))
    match = re.search(r"[?&]destination=([-+]?\d{1,2}(?:\.\d+)?),([-+]?\d{1,3}(?:\.\d+)?)", decoded, re.I)
    if not match:
        return None
    lat, lon = float(match.group(1)), float(match.group(2))
    if not (41.0 <= lat <= 52.0 and -6.0 <= lon <= 10.5):
        return None
    return lat, lon


def parse_location_page(url: str, raw_html: str, tariff: dict[str, Any]) -> dict[str, Any] | None:
    page_text = text_from_html(raw_html)
    n = norm(page_text)
    address = _first(r"\bAddress\s+(.*?)\s+Opening times\b", page_text)
    if not address or not re.search(r"(?:,\s*|\b)France\b", address, re.I):
        return None

    title_fragment = _first(r"<h1\b[^>]*>(.*?)</h1>", raw_html)
    title = clean_fragment(title_fragment or "")
    if not title:
        raise ValueError(f"Fastned France page without title: {url}")

    coords = _coordinates(raw_html)
    if coords is None:
        raise ValueError(f"Fastned France page without usable coordinates: {url}")

    price_match = re.search(
        r"eur\s*(\d+(?:[.,]\d+)?)\s*/\s*kwh.{0,260}?tarif standard\s*:\s*(\d+(?:[.,]\d+)?)\s*/\s*kwh",
        n,
    )
    if not price_match:
        # A French location page without a tariff is not safe to publish as a priced direct station.
        raise ValueError(f"Fastned France page without station Standard/Gold price: {url}")
    gold = eur(price_match.group(1))
    standard = eur(price_match.group(2))
    if abs(standard - tariff["standardEurPerKwh"]) > 0.001 or abs(gold - tariff["goldEurPerKwh"]) > 0.001:
        raise ValueError(
            f"Fastned station tariff differs from national tariff: {url}: standard={standard} gold={gold}"
        )

    points_match = re.search(r"nombre de points de recharge\s+(\d+)", n)
    if not points_match:
        points_match = re.search(r"chargers\s+(\d+)\s+points de recharge", n)
    if not points_match:
        raise ValueError(f"Fastned France page without charging-point count: {url}")
    charging_points = int(points_match.group(1))
    if not (1 <= charging_points <= 100):
        raise ValueError(f"implausible Fastned charging-point count {charging_points}: {url}")

    power_match = re.search(r"puissance maximale\s+jusqu'a\s*(\d{2,4})\s*kw", n)
    max_power = int(power_match.group(1)) if power_match else None
    if max_power is None or not (50 <= max_power <= 1000):
        raise ValueError(f"Fastned France page without plausible max power: {url}")

    connector_text = _first(r"Type de connecteurs\s+(.*?)\s+Puissance maximale", page_text)
    connector_types: list[str] = []
    for value in (connector_text or "").split(","):
        value = value.strip().upper()
        if value and value not in connector_types:
            connector_types.append(value)
    if not connector_types:
        raise ValueError(f"Fastned France page without connector types: {url}")

    parsed = urllib.parse.urlparse(url)
    slug = parsed.path.rstrip("/").split("/")[-1]
    lat, lon = coords
    return {
        "stationId": f"fastned:{slug}",
        "slug": slug,
        "name": title,
        "address": address,
        "country": "FR",
        "latitude": lat,
        "longitude": lon,
        "chargingPoints": charging_points,
        "maxPowerKw": max_power,
        "connectorTypes": connector_types,
        "stationPageUrl": url,
        "stationStandardEurPerKwh": standard,
        "stationGoldEurPerKwh": gold,
        "tariffProfileIds": ["fastned-app-direct", "fastned-standard", "fastned-gold"],
    }


def pricing_profiles(tariff: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "fastned-app-direct",
            "label": "Fastned app direct",
            "role": "operator_direct",
            "subscriptionRequired": False,
            "pricePerKwhEur": tariff["appDirectEurPerKwh"],
            "discountPercent": tariff["appDirectDiscountPercent"],
            "monthlyFeeEur": 0.0,
            "priceStatus": "calculated_from_official_10_percent_discount",
        },
        {
            "id": "fastned-standard",
            "label": "Fastned standard",
            "role": "operator_direct_ad_hoc",
            "subscriptionRequired": False,
            "pricePerKwhEur": tariff["standardEurPerKwh"],
            "monthlyFeeEur": 0.0,
        },
        {
            "id": "fastned-gold",
            "label": "Fastned Gold",
            "role": "operator_subscription",
            "subscriptionRequired": True,
            "subscriptionId": "fastned-gold",
            "pricePerKwhEur": tariff["goldEurPerKwh"],
            "discountPercent": tariff["goldDiscountPercent"],
            "monthlyFeeEur": tariff["goldMonthlyFeeEur"],
            "monthlyFeePromotionEnd": tariff["goldMonthlyFeePromotionEnd"],
            "vehicleLimitPerHousehold": tariff["goldVehicleLimitPerHousehold"],
        },
    ]


def make_payload(
    sitemap_url: str,
    sitemap_count: int,
    candidate_urls: list[str],
    locations: list[dict[str, Any]],
    tariff: dict[str, Any],
) -> dict[str, Any]:
    locations = sorted(locations, key=lambda item: (item["name"].lower(), item["stationId"]))
    if len(locations) < 50:
        raise ValueError(f"Fastned France official-location result unexpectedly small: {len(locations)}")
    ids = [item["stationId"] for item in locations]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Fastned stationId")
    if any(item["country"] != "FR" for item in locations):
        raise ValueError("non-France Fastned location leaked into national map")

    fingerprint_data = {
        "tariff": tariff,
        "locations": [
            {
                "stationId": x["stationId"],
                "latitude": x["latitude"],
                "longitude": x["longitude"],
                "chargingPoints": x["chargingPoints"],
                "maxPowerKw": x["maxPowerKw"],
                "connectorTypes": x["connectorTypes"],
                "standard": x["stationStandardEurPerKwh"],
                "gold": x["stationGoldEurPerKwh"],
            }
            for x in locations
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return {
        "schemaVersion": "1.0.0",
        "dataset": "fastned-direct-operated-stations-france",
        "generatedAt": now_iso(),
        "operator": "Fastned",
        "country": "FR",
        "scope": {
            "requiredOperator": "Fastned",
            "officialFastnedLocationPagesOnly": True,
            "onlyFastnedCpoLocations": True,
            "partnerOperatorLocationsIncluded": False,
            "liveStatusIncluded": False,
            "liveStatusAuthority": "TCC base Electroverse/Electra overlay",
            "stationTariffCrossCheckRequired": True,
            "nationalTariff": True,
            "freeAppDiscountIncluded": True,
            "subscriptionTariffIncluded": True,
            "subscriptionId": "fastned-gold",
            "fastnedDiscountsApplyAtPartnerOperators": False,
            "roamingTariffsIncluded": False,
        },
        "pricingProfiles": pricing_profiles(tariff),
        "counts": {
            "sitemapCount": sitemap_count,
            "candidateLocationPageCount": len(candidate_urls),
            "franceLocationCount": len(locations),
            "franceChargingPointCount": sum(x["chargingPoints"] for x in locations),
            "maxPowerCounts": dict(sorted(Counter(str(x["maxPowerKw"]) for x in locations).items(), key=lambda kv: int(kv[0]))),
        },
        "source": {
            "officialOnly": True,
            "sitemapUrl": sitemap_url,
            "locationPathPrefix": LOCATION_PATH_PREFIX,
            "tariffUrl": TARIFF_URL,
            "inventoryMethod": "crawl French-language Fastned location pages, then retain official addresses in France",
            "fingerprintSha256": fingerprint,
        },
        "matchPolicy": {
            "exactStationIdOrSlugFirst": True,
            "operatorMatchRequiredForFallback": True,
            "geoFallbackMaxDistanceMeters": 250,
            "ambiguousMatchesFailClosed": True,
        },
        "locations": locations,
    }


def live_build(workers: int = 18) -> dict[str, Any]:
    tariff = parse_country_tariff(text_from_html(fetch_text(TARIFF_URL)))
    sitemap_url, candidate_urls, sitemap_count = discover_location_urls()
    locations: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 24))) as pool:
        futures = {pool.submit(fetch_text, url): url for url in candidate_urls}
        for future in as_completed(futures):
            url = futures[future]
            station = parse_location_page(url, future.result(), tariff)
            if station is not None:
                locations.append(station)
    return make_payload(sitemap_url, sitemap_count, candidate_urls, locations, tariff)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=18)
    args = parser.parse_args()
    payload = live_build(args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out.suffix == ".gz":
        args.out.write_bytes(gzip.compress(rendered.encode("utf-8"), compresslevel=9, mtime=0))
    else:
        args.out.write_text(rendered, encoding="utf-8")
    counts = payload["counts"]
    print(
        f"Fastned France: {counts['franceLocationCount']} official stations / "
        f"{counts['franceChargingPointCount']} charging points / "
        f"{counts['candidateLocationPageCount']} location pages checked"
    )


if __name__ == "__main__":
    main()
