#!/usr/bin/env python3
"""Fast Allego France station/EVSE direct-tariff builder.

Inventory comes from Allego official station pages. Exact direct prices come from
Allego's public DXP backend used by app.allego.eu. The public-client APIM key is
captured at runtime from the public SPA and is never written to disk or logs.
Country defaults remain diagnostics only and are never rankable.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import allego_station_tariffs as base

DXP_API = "https://p-dxp-api-acg8edbwd7g2eheg.a01.azurefd.net/api/dxp/poi/chargepoints/"
DXP_SPA = "https://app.allego.eu/price/FRALLEGO8001301"


def fetch_parse(url: str):
    try:
        raw = base.fetch_text(url, attempts=2, timeout=18)
        return base.parse_station_page(url, raw), None
    except Exception as exc:
        return None, {"url": url, "error": f"{type(exc).__name__}: {exc}"}


def fetch_sitemap(url: str):
    try:
        raw = base.fetch_text(url, attempts=2, timeout=18)
        kind, locs = base.sitemap_locs(raw)
        return url, kind, locs, None
    except Exception as exc:
        return url, None, [], {"url": url, "error": f"{type(exc).__name__}: {exc}"}


def discover_station_urls_fast(workers: int) -> tuple[str, list[str], list[dict[str, str]]]:
    root_url = ""
    root_kind = ""
    root_locs: list[str] = []
    errors: list[dict[str, str]] = []
    for candidate in base.SITEMAPS:
        url, kind, locs, error = fetch_sitemap(candidate)
        if error is None:
            root_url, root_kind, root_locs = url, kind or "", locs
            break
        errors.append(error)
    if not root_url:
        raise RuntimeError("no Allego sitemap available")

    pages: set[str] = set()
    if root_kind != "sitemapindex":
        for loc in root_locs:
            canonical = base.station_url(loc)
            if canonical:
                pages.add(canonical)
    else:
        pending = list(dict.fromkeys(root_locs))
        seen = {root_url}
        while pending:
            wave = [u for u in pending if u not in seen]
            pending = []
            if not wave:
                break
            seen.update(wave)
            if len(seen) > 250:
                raise RuntimeError("Allego sitemap recursion unexpectedly large")
            with ThreadPoolExecutor(max_workers=max(2, min(workers, 24))) as pool:
                futures = [pool.submit(fetch_sitemap, url) for url in wave]
                for fut in as_completed(futures):
                    url, kind, locs, error = fut.result()
                    if error:
                        errors.append(error)
                        continue
                    if kind == "sitemapindex":
                        pending.extend(locs)
                    else:
                        for loc in locs:
                            canonical = base.station_url(loc)
                            if canonical:
                                pages.add(canonical)
    if len(pages) < 100:
        raise RuntimeError(f"Allego station sitemap unexpectedly small: {len(pages)}")
    print(f"discovered {len(pages)} Allego station pages; sitemap_errors={len(errors)}")
    return root_url, sorted(pages), errors


def capture_public_apim_key() -> str:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--user-agent={base.UA}")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(35)
    key = None
    try:
        driver.get(DXP_SPA)
        time.sleep(7)
        for item in driver.get_log("performance"):
            try:
                msg = json.loads(item["message"])["message"]
            except Exception:
                continue
            if msg.get("method") != "Network.requestWillBeSent":
                continue
            request = msg.get("params", {}).get("request", {})
            if "p-dxp-api-" not in request.get("url", ""):
                continue
            for name, value in (request.get("headers") or {}).items():
                if name.lower() == "ocp-apim-subscription-key" and value:
                    key = str(value)
                    break
            if key:
                break
    finally:
        driver.quit()
    if not key:
        raise RuntimeError("Allego public DXP client key was not observed")
    print(
        "captured Allego public DXP client configuration safely: "
        f"len={len(key)} sha256={hashlib.sha256(key.encode()).hexdigest()}"
    )
    return key


def primary_chargepoint_id(evse_id: str) -> str:
    evse_id = evse_id.upper().strip()
    if re.fullmatch(r"FRALLEGO[0-9]+", evse_id) and len(evse_id) > 9:
        return evse_id[:-1]
    return evse_id


def call_dxp(chargepoint_id: str, key: str) -> dict:
    req = urllib.request.Request(
        DXP_API + chargepoint_id,
        headers={
            "User-Agent": base.UA,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://app.allego.eu",
            "Referer": "https://app.allego.eu/",
            "Ocp-Apim-Subscription-Key": key,
        },
    )
    last_error = ""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=18) as response:
                body = response.read().decode("utf-8", "replace")
                obj = json.loads(body)
                return {"status": int(response.status), "object": obj, "error": ""}
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"status": 404, "object": None, "error": "HTTP 404"}
            last_error = f"HTTP {exc.code}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt == 0:
            time.sleep(0.35)
    return {"status": 0, "object": None, "error": last_error or "request failed"}


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings_in(child)


def parse_dxp_result(chargepoint_id: str, result: dict) -> dict:
    obj = result.get("object") if isinstance(result, dict) else None
    prices = obj.get("prices") if isinstance(obj, dict) and isinstance(obj.get("prices"), dict) else {}
    direct_text = str(prices.get("priceInfoDirectPayment") or "")
    texts = [direct_text] if direct_text else []
    if not texts and isinstance(obj, dict):
        texts = [s for s in strings_in(prices or obj) if ("kwh" in s.lower() or "eur" in s.lower())]
    joined = " | ".join(texts)

    rates = sorted(
        {
            round(float(raw.replace(",", ".")), 6)
            for raw in re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:EUR|€)\s*/?\s*kWh", joined, re.I)
            if 0.05 <= float(raw.replace(",", ".")) <= 2.0
        }
    )
    fees = []
    for raw, unit in re.findall(
        r"(\d+(?:[.,]\d+)?)\s*(?:EUR|€)\s*/\s*(minute|min|heure|hour)", joined, re.I
    ):
        value = float(raw.replace(",", "."))
        if 0 <= value <= 2.0:
            fees.append({"eur": round(value, 6), "unit": unit.lower()})

    return {
        "resolvedChargePointId": chargepoint_id if result.get("status") == 200 else None,
        "status": int(result.get("status") or 0),
        "directRatesEurPerKwh": rates,
        "directEurPerKwh": rates[0] if len(rates) == 1 else None,
        "feeCandidates": fees,
        "brand": obj.get("brand") if isinstance(obj, dict) else None,
        "isOwnNetwork": obj.get("isOwnNetwork") if isinstance(obj, dict) else None,
        "subscriberDiscountApplicable": obj.get("subscriberDiscountApplicable") if isinstance(obj, dict) else None,
        "maxPowerKw": obj.get("maxPowerKw") if isinstance(obj, dict) else None,
        "error": result.get("error") or "",
    }


def fetch_dxp_for_evses(evse_ids: list[str], key: str, workers: int) -> dict[str, dict]:
    primary_ids = sorted({primary_chargepoint_id(evse_id) for evse_id in evse_ids})
    raw: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(2, min(workers, 20))) as pool:
        futures = {pool.submit(call_dxp, cid, key): cid for cid in primary_ids}
        for idx, fut in enumerate(as_completed(futures), 1):
            cid = futures[fut]
            raw[cid] = fut.result()
            if idx % 250 == 0:
                ok = sum(1 for item in raw.values() if item.get("status") == 200)
                print(f"DXP primary {idx}/{len(primary_ids)}; resolved={ok}")

    fallback_ids = sorted(
        {
            evse_id
            for evse_id in evse_ids
            if raw.get(primary_chargepoint_id(evse_id), {}).get("status") != 200
            and evse_id != primary_chargepoint_id(evse_id)
        }
    )
    if fallback_ids:
        with ThreadPoolExecutor(max_workers=max(2, min(workers, 20))) as pool:
            futures = {pool.submit(call_dxp, cid, key): cid for cid in fallback_ids}
            for idx, fut in enumerate(as_completed(futures), 1):
                cid = futures[fut]
                raw[cid] = fut.result()
                if idx % 250 == 0:
                    print(f"DXP fallback {idx}/{len(fallback_ids)}")

    resolved: dict[str, dict] = {}
    for evse_id in evse_ids:
        primary = primary_chargepoint_id(evse_id)
        chosen = primary
        result = raw.get(primary, {"status": 0, "object": None, "error": "missing primary result"})
        if result.get("status") != 200 and evse_id != primary:
            fallback = raw.get(evse_id)
            if fallback and fallback.get("status") == 200:
                chosen, result = evse_id, fallback
        resolved[evse_id] = parse_dxp_result(chosen, result)
    return resolved


def apply_dxp_to_station(station: dict, dxp_by_evse: dict[str, dict]) -> None:
    per_evse: dict[str, dict[str, float]] = {}
    evidence: list[str] = []
    for evse in station.get("evses", []):
        evse_id = evse["evseId"]
        info = dxp_by_evse.get(evse_id) or {}
        evse["dxpChargePointId"] = info.get("resolvedChargePointId")
        evse["directEurPerKwh"] = info.get("directEurPerKwh")
        evse["dxpDirectRatesEurPerKwh"] = info.get("directRatesEurPerKwh") or []
        evse["dxpFeeCandidates"] = info.get("feeCandidates") or []
        evse["subscriberDiscountApplicable"] = info.get("subscriberDiscountApplicable")
        if info.get("maxPowerKw") is not None:
            evse["dxpMaxPowerKw"] = info.get("maxPowerKw")
        if info.get("directEurPerKwh") is not None:
            per_evse[evse_id] = {"direct": float(info["directEurPerKwh"])}
            evidence.append(f"https://app.allego.eu/price/{evse_id}")
        elif info.get("status") != 200:
            station.setdefault("warnings", []).append(
                f"dxp_lookup_failed:{evse_id}:{info.get('status') or 0}"
            )
        elif len(info.get("directRatesEurPerKwh") or []) > 1:
            station.setdefault("warnings", []).append(f"dxp_ambiguous_price:{evse_id}")
        else:
            station.setdefault("warnings", []).append(f"dxp_missing_price:{evse_id}")

    station["exactDirectPricesByKind"] = {}
    station["exactNamedOffers"] = {}
    station["exactOffersByEvse"] = per_evse
    station["priceEvidenceUrls"] = sorted(set(evidence))
    exact_evse = len(per_evse)
    total_evse = len(station.get("evses", []))
    if exact_evse == total_evse and total_evse:
        status = "exact_official_evse"
    elif exact_evse:
        status = "exact_official_station_partial"
    else:
        status = "lookup_required"
    station["pricingStatus"] = status
    station["rankableDirect"] = exact_evse > 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=base.DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=base.DEFAULT_REPORT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--max-stations", type=int, default=0)
    args = parser.parse_args()

    sitemap, urls, sitemap_failures = discover_station_urls_fast(args.workers)
    if args.max_stations:
        urls = urls[: args.max_stations]

    stations = []
    failures = list(sitemap_failures)
    with ThreadPoolExecutor(max_workers=max(2, min(args.workers, 24))) as pool:
        futures = {pool.submit(fetch_parse, url): url for url in urls}
        for idx, fut in enumerate(as_completed(futures), 1):
            station, failure = fut.result()
            if station:
                stations.append(station)
            if failure:
                failures.append(failure)
            if idx % 250 == 0:
                print(f"scanned {idx}/{len(urls)} station pages; France={len(stations)} failures={len(failures)}")

    if len(stations) < 50 and not args.max_stations:
        raise RuntimeError(f"Allego France inventory unexpectedly small: {len(stations)}")

    evse_ids = sorted({e["evseId"] for station in stations for e in station.get("evses", [])})
    if len(evse_ids) < 500 and not args.max_stations:
        raise RuntimeError(f"Allego France EVSE inventory unexpectedly small: {len(evse_ids)}")

    key = capture_public_apim_key()
    dxp_by_evse = fetch_dxp_for_evses(evse_ids, key, args.workers)
    for station in stations:
        apply_dxp_to_station(station, dxp_by_evse)

    data_gouv_ids, data_gouv_meta = base.fetch_data_gouv_ids()
    payload = base.make_payload(stations, sitemap, data_gouv_ids, data_gouv_meta)
    priced_evses = sum(1 for info in dxp_by_evse.values() if info.get("directEurPerKwh") is not None)
    resolved_evses = sum(1 for info in dxp_by_evse.values() if info.get("status") == 200)
    ambiguous_evses = sum(1 for info in dxp_by_evse.values() if len(info.get("directRatesEurPerKwh") or []) > 1)
    payload["sources"]["dxpApi"] = DXP_API + "<chargePointId>"
    payload["sources"]["dxpPublicClient"] = "https://app.allego.eu/price/<FRALLEGO_EVSE_ID>"
    payload["scope"]["exactDirectPricesFromDxp"] = True
    payload["counts"].update(
        {
            "dxpResolvedEvseCount": resolved_evses,
            "dxpPricedEvseCount": priced_evses,
            "dxpAmbiguousEvseCount": ambiguous_evses,
            "dxpPricedEvsePct": round(100 * priced_evses / len(evse_ids), 2) if evse_ids else 0,
        }
    )

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
        "fullyPricedStationCount": sum(1 for s in stations if s["pricingStatus"] == "exact_official_evse"),
        "blockedStationCount": sum(1 for s in stations if not s["rankableDirect"]),
        "blockedStations": [
            {"name": s["name"], "url": s["stationPageUrl"], "evseIds": [e["evseId"] for e in s["evses"]]}
            for s in stations if not s["rankableDirect"]
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    print(
        f"Allego France: {len(stations)} stations / {payload['counts']['franceEvseCount']} EVSE / "
        f"DXP resolved={resolved_evses} priced={priced_evses} ambiguous={ambiguous_evses} / "
        f"rankable stations={report['publicationReadyStationCount']} blocked={report['blockedStationCount']} / "
        f"sha256={digest}"
    )


if __name__ == "__main__":
    main()
