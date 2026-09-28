#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from belgium_nap_probe import find_location_list, build_canonical

BASE = "https://nap-be.eco-movement.com/datex2/v1/locations"
TOKEN = os.environ["BELGIUM_NAP_TOKEN"].strip()
PAGE_SIZE = 1000
SLEEP_SECONDS = 11
MAX_PAGES = 100

RAW_DIR = Path("artifacts/belgium-nap-raw-pages")
CANON_DIR = Path("data/belgium/pages")
MANIFEST = Path("data/belgium/nap-belgium-manifest.json")
REPORT = Path("reports/belgium-national-full-extraction-2026-09-28.json")
PROGRESS = Path("docs/belgium-cpo-progress-2026-09.json")
MISSING = Path("reports/belgium-missing-price-evses-2026-09-28.json")


def fetch_page(offset: int) -> tuple[Any, dict[str, str]]:
    qs = urllib.parse.urlencode({"limit": PAGE_SIZE, "offset": offset})
    req = urllib.request.Request(
        BASE + "?" + qs,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json",
            "User-Agent": "tesla-charge-companion-data-lab/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read())
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return payload, headers


def next_offset(link_header: str | None) -> int | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part or "rel=next" in part:
            m = re.search(r"[?&]offset=(\d+)", part)
            if m:
                return int(m.group(1))
    return None


def write_gzip_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))


def collect_page_stats(canonical: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], list[str], list[str]]:
    operators = defaultdict(lambda: {
        "sites": 0, "stations": 0, "evses": 0, "connectors": 0,
        "pricedEvses": 0, "adHocPricedEvses": 0, "missingPriceEvses": 0,
        "acEvses": 0, "dcEvses": 0,
        "priceComponents": Counter(), "currencies": Counter(), "rateIds": set(),
        "taxIncludedTrue": 0, "taxIncludedFalse": 0, "taxIncludedNull": 0,
    })
    missing = []
    loc_ids, st_ids, evse_ids = [], [], []

    totals = Counter()
    for loc in canonical.get("locations") or []:
        operator = str(loc.get("operator") or "UNKNOWN")
        operators[operator]["sites"] += 1
        totals["locations"] += 1
        if loc.get("id"):
            loc_ids.append(str(loc["id"]))

        for st in loc.get("stations") or []:
            operators[operator]["stations"] += 1
            totals["stations"] += 1
            if st.get("id"):
                st_ids.append(str(st["id"]))

            for evse in st.get("evses") or []:
                operators[operator]["evses"] += 1
                totals["evses"] += 1
                eid = str(evse.get("id") or "")
                if eid:
                    evse_ids.append(eid)
                ct = str(evse.get("currentType") or "").lower()
                if ct == "ac":
                    operators[operator]["acEvses"] += 1
                elif ct == "dc":
                    operators[operator]["dcEvses"] += 1

                conns = evse.get("connectors") or []
                operators[operator]["connectors"] += len(conns)
                totals["connectors"] += len(conns)

                prices = evse.get("prices") or []
                if prices:
                    totals["pricedEvses"] += 1
                    operators[operator]["pricedEvses"] += 1
                    if any(p.get("ratePolicy") == "adHoc" for p in prices):
                        totals["adHocPricedEvses"] += 1
                        operators[operator]["adHocPricedEvses"] += 1
                    for p in prices:
                        operators[operator]["priceComponents"][str(p.get("priceType") or "UNKNOWN")] += 1
                        if p.get("currency"):
                            operators[operator]["currencies"][str(p["currency"])] += 1
                        if p.get("rateId"):
                            operators[operator]["rateIds"].add(str(p["rateId"]))
                        ti = p.get("taxIncluded")
                        if ti is True:
                            operators[operator]["taxIncludedTrue"] += 1
                        elif ti is False:
                            operators[operator]["taxIncludedFalse"] += 1
                        else:
                            operators[operator]["taxIncludedNull"] += 1
                else:
                    totals["missingPriceEvses"] += 1
                    operators[operator]["missingPriceEvses"] += 1
                    missing.append({
                        "operator": operator,
                        "locationId": loc.get("id"),
                        "brand": loc.get("brand"),
                        "city": loc.get("city"),
                        "stationId": st.get("id"),
                        "evseId": evse.get("id"),
                        "externalIdentifiers": evse.get("externalIdentifiers") or [],
                        "powerW": evse.get("availableChargingPowerW") or [],
                        "currentType": evse.get("currentType"),
                    })

    return {"totals": dict(totals), "operators": operators}, missing, loc_ids, st_ids, evse_ids


def merge_operator(dst: dict[str, Any], src: dict[str, Any]) -> None:
    numeric = [
        "sites","stations","evses","connectors","pricedEvses","adHocPricedEvses",
        "missingPriceEvses","acEvses","dcEvses","taxIncludedTrue","taxIncludedFalse","taxIncludedNull"
    ]
    for k in numeric:
        dst[k] += src[k]
    dst["priceComponents"].update(src["priceComponents"])
    dst["currencies"].update(src["currencies"])
    dst["rateIds"].update(src["rateIds"])


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CANON_DIR.mkdir(parents=True, exist_ok=True)

    # Clear only files generated by this extractor.
    for p in RAW_DIR.glob("page-*.json.gz"):
        p.unlink()
    for p in CANON_DIR.glob("nap-belgium-*.json.gz"):
        p.unlink()

    page_records = []
    all_missing: list[dict[str, Any]] = []
    loc_counter, st_counter, evse_counter = Counter(), Counter(), Counter()
    global_totals = Counter()
    global_ops = defaultdict(lambda: {
        "sites": 0, "stations": 0, "evses": 0, "connectors": 0,
        "pricedEvses": 0, "adHocPricedEvses": 0, "missingPriceEvses": 0,
        "acEvses": 0, "dcEvses": 0,
        "priceComponents": Counter(), "currencies": Counter(), "rateIds": set(),
        "taxIncludedTrue": 0, "taxIncludedFalse": 0, "taxIncludedNull": 0,
    })

    offset = 0
    seen_offsets = set()
    for page_index in range(MAX_PAGES):
        if offset in seen_offsets:
            raise RuntimeError(f"Pagination loop detected at offset {offset}")
        seen_offsets.add(offset)

        if page_index:
            time.sleep(SLEEP_SECONDS)

        payload, headers = fetch_page(offset)
        _, locations = find_location_list(payload)
        canonical = build_canonical(payload, locations)

        raw_path = RAW_DIR / f"page-{offset:06d}.json.gz"
        canon_path = CANON_DIR / f"nap-belgium-{offset:06d}.json.gz"
        write_gzip_json(raw_path, payload)
        write_gzip_json(canon_path, canonical)

        stats, missing, lids, sids, eids = collect_page_stats(canonical)
        all_missing.extend(missing)
        for x in lids: loc_counter[x] += 1
        for x in sids: st_counter[x] += 1
        for x in eids: evse_counter[x] += 1
        global_totals.update(stats["totals"])
        for name, src in stats["operators"].items():
            merge_operator(global_ops[name], src)

        link = headers.get("link")
        nxt = next_offset(link)
        page_records.append({
            "pageIndex": page_index,
            "offset": offset,
            "locationCount": len(locations),
            "canonicalPath": str(canon_path),
            "rawArtifactPath": str(raw_path),
            "firstLocationId": locations[0].get("idG") if locations else None,
            "lastLocationId": locations[-1].get("idG") if locations else None,
            "nextOffset": nxt,
            "linkHeader": link,
        })

        print(json.dumps({
            "page": page_index,
            "offset": offset,
            "locations": len(locations),
            "nextOffset": nxt,
            "runningLocations": global_totals["locations"],
            "runningEvses": global_totals["evses"],
        }))

        if nxt is None:
            break
        offset = nxt
    else:
        raise RuntimeError(f"Reached MAX_PAGES={MAX_PAGES} before pagination ended")

    operators_out = {}
    cpos = []
    for name in sorted(global_ops):
        s = global_ops[name]
        evses = s["evses"]
        priced = s["pricedEvses"]
        coverage = round(priced / evses * 100, 2) if evses else 0.0
        state = "complete" if evses and s["missingPriceEvses"] == 0 else "partial"
        operators_out[name] = {
            "sites": s["sites"], "stations": s["stations"], "evses": evses,
            "connectors": s["connectors"], "pricedEvses": priced,
            "adHocPricedEvses": s["adHocPricedEvses"],
            "missingPriceEvses": s["missingPriceEvses"],
            "priceCoveragePct": coverage,
            "acEvses": s["acEvses"], "dcEvses": s["dcEvses"],
            "priceComponents": dict(s["priceComponents"].most_common()),
            "currencies": dict(s["currencies"].most_common()),
            "distinctRateIds": len(s["rateIds"]),
            "taxIncluded": {
                "trueComponents": s["taxIncludedTrue"],
                "falseComponents": s["taxIncludedFalse"],
                "nullComponents": s["taxIncludedNull"],
            },
            "state": state,
        }
        cpos.append({
            "name": name, "state": state, "sites": s["sites"], "evses": evses,
            "pricedEvses": priced, "missingPriceEvses": s["missingPriceEvses"],
            "priceCoveragePct": coverage, "firstPassDone": True,
            "source": "Belgium NAP DATEX II paginated /datex2/v1/locations",
        })

    dup_locs = sorted(k for k,v in loc_counter.items() if k and v > 1)
    dup_stations = sorted(k for k,v in st_counter.items() if k and v > 1)
    dup_evses = sorted(k for k,v in evse_counter.items() if k and v > 1)

    manifest = {
        "country": "BE",
        "source": BASE,
        "pageSize": PAGE_SIZE,
        "pageCount": len(page_records),
        "pages": page_records,
        "totals": dict(global_totals),
        "operatorCount": len(operators_out),
        "canonicalFormat": "gzip-compressed JSON, one source page per file",
        "canonicalDirectory": str(CANON_DIR),
    }
    report = {
        "country": "BE",
        "asOf": "2026-09-28",
        "phase": "national-full-extraction",
        "source": BASE,
        "pagination": {
            "pageSize": PAGE_SIZE,
            "pageCount": len(page_records),
            "pages": [{"offset":x["offset"],"locationCount":x["locationCount"],"nextOffset":x["nextOffset"]} for x in page_records],
        },
        "totals": {
            **dict(global_totals),
            "operators": len(operators_out),
            "priceCoveragePct": round(global_totals["pricedEvses"] / global_totals["evses"] * 100, 2) if global_totals["evses"] else 0.0,
        },
        "operators": operators_out,
        "integrity": {
            "duplicateLocationIdsAcrossPages": dup_locs,
            "duplicateStationIdsAcrossPages": dup_stations,
            "duplicateEvseIdsAcrossPages": dup_evses,
            "paginationEndedNormally": bool(page_records) and page_records[-1]["nextOffset"] is None,
        },
        "missingPriceEvses": all_missing,
    }
    progress = {
        "country": "BE",
        "asOf": "2026-09-28",
        "canonicalSource": str(MANIFEST),
        "firstPass": {
            "done": True,
            "scope": "all pages exposed by the Belgium NAP selected-CPO dataset",
            "pageCount": len(page_records),
            "operatorsSeen": len(cpos),
            "locations": global_totals["locations"],
            "evses": global_totals["evses"],
            "connectors": global_totals["connectors"],
        },
        "counts": {
            "complete": sum(1 for x in cpos if x["state"]=="complete"),
            "partial": sum(1 for x in cpos if x["state"]=="partial"),
            "blocked": 0,
            "total": len(cpos),
        },
        "cpos": sorted(cpos, key=lambda x:(-x["sites"], x["name"])),
        "rules": [
            "All source pages are extracted before second-pass gap filling.",
            "No tariff is invented or extrapolated.",
            "complete means every EVSE for that CPO in the extracted NAP pages has at least one tariff component.",
            "This Eco-Movement dataset explicitly covers selected CPOs, not necessarily every Belgian CPO.",
        ],
    }

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    PROGRESS.write_text(json.dumps(progress, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    MISSING.write_text(json.dumps({"count":len(all_missing),"items":all_missing}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

    print(json.dumps({
        "pageCount": len(page_records),
        "totals": report["totals"],
        "progressCounts": progress["counts"],
        "duplicates": {
            "locations": len(dup_locs), "stations": len(dup_stations), "evses": len(dup_evses)
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
