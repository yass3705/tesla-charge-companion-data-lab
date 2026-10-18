#!/usr/bin/env python3
"""Fast/concurrent runner for the Allego France station tariff builder.

This runner reuses every parsing/pricing rule from allego_station_tariffs.py.
Only sitemap discovery and HTTP station inventory collection are concurrent.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import allego_station_tariffs as base


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
        # Process sitemap-index levels in waves. Most Allego installs only need
        # one wave; nested indexes remain supported without serial network I/O.
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=base.DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=base.DEFAULT_REPORT)
    parser.add_argument("--browser", action="store_true")
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

    driver = base.build_browser() if args.browser else None
    try:
        for idx, station in enumerate(stations, 1):
            base.enrich_exact(station, driver)
            if idx % 25 == 0:
                print(f"priced {idx}/{len(stations)} Allego France stations")
    finally:
        if driver is not None:
            driver.quit()

    data_gouv_ids, data_gouv_meta = base.fetch_data_gouv_ids()
    payload = base.make_payload(stations, sitemap, data_gouv_ids, data_gouv_meta)
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
        f"{report['publicationReadyStationCount']} rankable / blocked={report['blockedStationCount']} / sha256={digest}"
    )


if __name__ == "__main__":
    main()
