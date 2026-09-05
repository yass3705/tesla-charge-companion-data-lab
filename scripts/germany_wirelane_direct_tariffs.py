#!/usr/bin/env python3
"""Extract Wirelane Germany public direct-payment tariffs per EVSE.

Wirelane prices are EVSE-specific. The national catalogue stores separator-free
canonical EVSE IDs (e.g. DEWLNES000449); Wirelane's public direct portal expects
eMI3-starred IDs (DE*WLN*ES000449). This extractor queries every Wirelane EVSE
known in the staged BNetzA catalogue, preserves the raw tariff sentence, parses
common tariff components conservatively, and aggregates coverage per physical
site. It is staging-only and does not enable production ranking.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
BASE = "https://direct.wirelane.com/{evse}?_locale=de"
OPERATOR = "Wirelane Public 1 GmbH"


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_gz(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def textify(raw: bytes):
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " ")).strip()


def to_direct_evse(value):
    raw = str(value or "").strip().upper()
    if raw.startswith("DE*WLN*") and len(raw) > 7:
        return raw
    compact = re.sub(r"[^A-Z0-9]", "", raw)
    if compact.startswith("DEWLN") and len(compact) > 5:
        return "DE*WLN*" + compact[5:]
    return None


def canonical_evse(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper()) or None


def money_value(match):
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()
    if unit == "ct":
        value /= 100.0
    return round(value, 6)


def parse_tariff(text: str | None):
    if not text:
        return {
            "eurPerKwh": None,
            "startFeeEur": None,
            "minuteFeeEur": None,
            "afterMinutes": None,
            "capEur": None,
            "inactiveLocalTime": None,
            "taxIncluded": None,
        }
    kwh = money_value(re.search(r"([0-9]+(?:[,.][0-9]+)?)\s*(€|EUR|ct)\s*/?\s*kWh", text, re.I))
    start = None
    ms = re.search(r"(?:zzgl\.|\+)\s*([0-9]+(?:[,.][0-9]+)?)\s*€\s*(?:Startgebühr|Start)", text, re.I)
    if ms:
        start = round(float(ms.group(1).replace(",", ".")), 6)
    minute = money_value(re.search(r"([0-9]+(?:[,.][0-9]+)?)\s*(€|EUR|ct)\s*/?\s*Min", text, re.I))
    after = None
    ma = re.search(r"(?:ab|nach)\s*([0-9]+)\s*Min", text, re.I)
    if ma:
        after = int(ma.group(1))
    cap = None
    mc = re.search(r"max\.?\s*([0-9]+(?:[,.][0-9]+)?)\s*€", text, re.I)
    if mc:
        cap = round(float(mc.group(1).replace(",", ".")), 6)
    inactive = None
    mt = re.search(r"(?:außer|ausser)\s+zwischen\s*([0-2]?\d)(?::([0-5]\d))?\s*[-–]\s*([0-2]?\d)(?::([0-5]\d))?\s*Uhr", text, re.I)
    if mt:
        inactive = {
            "start": f"{int(mt.group(1)):02d}:{int(mt.group(2) or 0):02d}",
            "end": f"{int(mt.group(3)):02d}:{int(mt.group(4) or 0):02d}",
        }
    tax = True if re.search(r"\bbrutto\b", text, re.I) else None
    return {
        "eurPerKwh": kwh,
        "startFeeEur": start,
        "minuteFeeEur": minute,
        "afterMinutes": after,
        "capEur": cap,
        "inactiveLocalTime": inactive,
        "taxIncluded": tax,
    }


def fetch_one(evse: str, attempts: int = 3):
    url = BASE.format(evse=urllib.parse.quote(evse, safe=""))
    last_error = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                status = getattr(r, "status", 200)
            text = textify(raw)
            m = re.search(r"(?:max\.\s*[0-9.,]+\s*kW)\s+(.{1,900}?)\s+(?:Betreiber|Provider)\s+Wirelane\s+GmbH", text, re.I)
            tariff_text = m.group(1).strip() if m else None
            parsed = parse_tariff(tariff_text)
            page_evse_match = re.search(r"\bDE\*WLN\*[A-Z0-9]+\b", text, re.I)
            page_evse = page_evse_match.group(0).upper() if page_evse_match else None
            provider_ok = bool(re.search(r"(?:Betreiber|Provider)\s+Wirelane\s+GmbH", text, re.I))
            unavailable = bool(re.search(r"(?:zur Zeit nicht verfügbar|Status:)", text, re.I))
            complete = bool(page_evse == evse and provider_ok and tariff_text and parsed["eurPerKwh"] is not None)
            return {
                "evseId": evse,
                "canonicalEvseId": canonical_evse(evse),
                "pageEvseId": page_evse,
                "url": url,
                "httpStatus": status,
                "providerWirelane": provider_ok,
                "pageSaysUnavailable": unavailable,
                "tariffText": tariff_text,
                "parsed": parsed,
                "complete": complete,
                "bytes": len(raw),
                "attempts": attempt + 1,
            }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
    return {
        "evseId": evse,
        "canonicalEvseId": canonical_evse(evse),
        "url": url,
        "complete": False,
        "error": last_error,
        "attempts": attempts,
    }


def tariff_signature(row: dict):
    if not row.get("complete"):
        return None
    payload = {
        "eurPerKwh": row["parsed"].get("eurPerKwh"),
        "startFeeEur": row["parsed"].get("startFeeEur"),
        "minuteFeeEur": row["parsed"].get("minuteFeeEur"),
        "afterMinutes": row["parsed"].get("afterMinutes"),
        "capEur": row["parsed"].get("capEur"),
        "inactiveLocalTime": row["parsed"].get("inactiveLocalTime"),
        "taxIncluded": row["parsed"].get("taxIncluded"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=Path("data/germany/germany_non_tesla_catalog_staging_tariff_classified.json.gz"))
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--output", type=Path, default=Path("data/germany/wirelane_direct_tariffs.json.gz"))
    ap.add_argument("--manifest", type=Path, default=Path("data/germany/wirelane_direct_tariffs_manifest.json"))
    args = ap.parse_args()

    catalog = load_gz(args.catalog)
    if catalog.get("dataset") != "germany-national-non-tesla-catalog-staging-tariff-classified":
        raise RuntimeError(f"unexpected catalog dataset: {catalog.get('dataset')}")

    site_expected = {}
    evse_to_sites = defaultdict(set)
    operator_sites = 0
    for site in catalog.get("sites") or []:
        if site.get("operator") != OPERATOR:
            continue
        operator_sites += 1
        evses = sorted({to_direct_evse(e) for e in (site.get("evseIds") or []) if to_direct_evse(e)})
        site_expected[site["id"]] = {
            "siteId": site["id"],
            "address": site.get("address"),
            "evseIds": evses,
        }
        for evse in evses:
            evse_to_sites[evse].add(site["id"])

    duplicate_evse_assignments = {e: sorted(v) for e, v in evse_to_sites.items() if len(v) > 1}
    unique_evses = sorted(evse_to_sites)
    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(fetch_one, evse): evse for evse in unique_evses}
        for fut in as_completed(futures):
            row = fut.result()
            results[row["evseId"]] = row

    stats = Counter()
    price_distribution = Counter()
    raw_signatures = Counter()
    structured_signatures = Counter()
    for evse in unique_evses:
        row = results[evse]
        stats["evseExpected"] += 1
        if row.get("error"):
            stats["evseErrors"] += 1
            continue
        stats["evseReachable"] += 1
        if row.get("pageEvseId") == evse:
            stats["evseIdConfirmed"] += 1
        if row.get("providerWirelane"):
            stats["providerConfirmed"] += 1
        if row.get("tariffText"):
            stats["tariffTextFound"] += 1
            raw_signatures[row["tariffText"]] += 1
        if row.get("parsed", {}).get("eurPerKwh") is not None:
            stats["kwhParsed"] += 1
            price_distribution[row["parsed"]["eurPerKwh"]] += 1
        if row.get("pageSaysUnavailable"):
            stats["pageUnavailable"] += 1
        if row.get("complete"):
            stats["evseComplete"] += 1
            structured_signatures[tariff_signature(row)] += 1
        if (row.get("parsed") or {}).get("taxIncluded") is True:
            stats["taxIncludedExplicit"] += 1

    sites = []
    site_stats = Counter()
    for site_id in sorted(site_expected):
        meta = site_expected[site_id]
        evses = meta["evseIds"]
        rows = [results[e] for e in evses if e in results]
        complete_rows = [r for r in rows if r.get("complete")]
        full = bool(evses) and len(rows) == len(evses) and len(complete_rows) == len(evses)
        signatures = sorted({tariff_signature(r) for r in complete_rows if tariff_signature(r)})
        uniform = full and len(signatures) == 1
        mixed = full and len(signatures) > 1
        if not evses:
            site_stats["sitesWithoutWirelaneEvse"] += 1
        elif full:
            site_stats["sitesFullyCovered"] += 1
            if uniform:
                site_stats["sitesUniformTariff"] += 1
            elif mixed:
                site_stats["sitesMixedTariff"] += 1
        else:
            site_stats["sitesPartial"] += 1
        uniform_tariff = None
        if uniform:
            uniform_tariff = json.loads(signatures[0])
        sites.append({
            "siteId": site_id,
            "address": meta["address"],
            "expectedEvseCount": len(evses),
            "completeEvseCount": len(complete_rows),
            "fullyCovered": full,
            "uniformTariffAcrossEvse": uniform,
            "mixedTariffsAcrossEvse": mixed,
            "uniformTariff": uniform_tariff,
            "evseTariffs": rows,
        })

    output = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-wirelane-direct-tariffs",
        "generatedAt": utc_now(),
        "countryCode": "DE",
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "operatorOwnNetworkOnly": True,
            "tariffModel": "evse_specific",
            "catalogEvseFormat": "canonical_separator_free",
            "providerBoundaryEvseFormat": "eMI3_starred",
            "rawTariffTextPreserved": True,
            "productionRankable": False,
        },
        "operator": {
            "canonicalName": "Wirelane",
            "bnetzaExactOperators": [OPERATOR],
        },
        "source": {
            "type": "public-direct-payment-page",
            "urlTemplate": BASE,
        },
        "stats": {
            "operatorSites": operator_sites,
            "sitesWithExpectedEvse": sum(1 for v in site_expected.values() if v["evseIds"]),
            "uniqueEvse": len(unique_evses),
            "duplicateEvseAssignments": len(duplicate_evse_assignments),
            **dict(stats),
            **dict(site_stats),
        },
        "priceDistribution": [{"eurPerKwh": p, "evse": n} for p, n in price_distribution.most_common()],
        "topRawTariffSignatures": [{"tariffText": t, "evse": n} for t, n in raw_signatures.most_common(100)],
        "topStructuredTariffSignatures": [{"signature": json.loads(s), "evse": n} for s, n in structured_signatures.most_common(100)],
        "duplicateEvseAssignmentSample": list(duplicate_evse_assignments.items())[:50],
        "sites": sites,
    }
    save_gz(args.output, output)
    manifest = {
        "schemaVersion": output["schemaVersion"],
        "dataset": output["dataset"],
        "generatedAt": output["generatedAt"],
        "countryCode": "DE",
        "stagedOnly": True,
        "publishesToTcc": False,
        "file": args.output.name,
        "stats": output["stats"],
        "priceDistribution": output["priceDistribution"],
        "topStructuredTariffSignatures": output["topStructuredTariffSignatures"][:30],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_WIRELANE_DIRECT_TARIFFS=" + json.dumps({
        "stats": output["stats"],
        "priceDistribution": output["priceDistribution"][:20],
        "topStructured": output["topStructuredTariffSignatures"][:15],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
