#!/usr/bin/env python3
"""Fast/concurrent runner for the Allego France station tariff builder.

This runner intentionally reuses every parsing/pricing rule from
allego_station_tariffs.py. Only the HTTP inventory collection is concurrent.
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=base.DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=base.DEFAULT_REPORT)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--max-stations", type=int, default=0)
    args = parser.parse_args()

    sitemap, urls = base.discover_station_urls()
    if args.max_stations:
        urls = urls[: args.max_stations]

    stations = []
    failures = []
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

    # Static official station-page prices are authoritative. Browser fallback is
    # optional and remains conservative: the underlying builder only promotes
    # prices it can actually read from an official Allego page.
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
