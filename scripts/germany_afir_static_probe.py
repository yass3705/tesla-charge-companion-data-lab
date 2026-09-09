#!/usr/bin/env python3
"""Explore live anonymous German AFIR/DATEX II static payload structures.

This is deliberately a schema/quality probe, not the production normalizer.
It downloads selected public noauth feeds, inventories nested paths and emits
small representative samples so we can implement a parser from observed data.
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENDPOINT = "https://mobilithek.info/mdp-api/mdp-conn-server/v1/publication/{offer_id}/file/noauth"
USER_AGENT = "Tesla-Charge-Companion-data-lab/1.0 (+https://github.com/yass3705/tesla-charge-companion-data-lab)"

OFFERS = {
    "chargecloud-static": {"offerId": "978597062404620288", "license": "CC0"},
    "eround-static": {"offerId": "961625658278940672", "license": "CC0"},
    "qwello-static": {"offerId": "972963216296222720", "license": "CC0"},
}

INTEREST = re.compile(
    r"evse|operator|organisation|organization|station|refill|charging|connector|plug|power|voltage|current|"
    r"price|tariff|cost|fee|currency|status|available|access|payment|address|coordinate|latitude|longitude|idg$|lastupdated",
    re.I,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_json(offer_id: str) -> tuple[dict, dict]:
    url = ENDPOINT.format(offer_id=offer_id)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, */*",
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            headers = dict(response.headers.items())
            if "gzip" in response.headers.get("Content-Encoding", "").lower():
                raw = gzip.GzipFile(fileobj=response).read()
            else:
                raw = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}: {exc.read(1000)!r}") from exc
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected payload type {type(payload).__name__}")
    return payload, {
        "url": url,
        "bytes": len(raw),
        "contentType": headers.get("Content-Type"),
        "contentEncoding": headers.get("Content-Encoding"),
    }


def path_walk(value: Any, path: str = "$", depth: int = 0):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, child, depth + 1
            yield from path_walk(child, child_path, depth + 1)
    elif isinstance(value, list):
        for child in value:
            child_path = f"{path}[]"
            yield child_path, child, depth + 1
            yield from path_walk(child, child_path, depth + 1)


def scalar_preview(value: Any):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:300]
    return None


def compact(value: Any, depth: int = 0):
    if depth >= 6:
        return "<depth-limit>"
    if isinstance(value, dict):
        return {str(k): compact(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return [compact(v, depth + 1) for v in value[:5]]
    if isinstance(value, str):
        return value[:500]
    return value


def root_sites(payload: dict) -> list[dict]:
    publication = payload.get("payload", {}).get("aegiEnergyInfrastructureTablePublication", {})
    tables = publication.get("energyInfrastructureTable") or []
    sites: list[dict] = []
    for table in tables if isinstance(tables, list) else [tables]:
        if not isinstance(table, dict):
            continue
        raw_sites = table.get("energyInfrastructureSite") or []
        for site in raw_sites if isinstance(raw_sites, list) else [raw_sites]:
            if isinstance(site, dict):
                sites.append(site)
    return sites


def field_examples(payload: dict, limit_per_path: int = 4):
    seen = defaultdict(list)
    for path, value, _depth in path_walk(payload):
        key = path.rsplit(".", 1)[-1]
        if not INTEREST.search(key):
            continue
        scalar = scalar_preview(value)
        if scalar is None and not isinstance(value, (dict, list)):
            continue
        if scalar is not None:
            sample = scalar
        elif isinstance(value, list):
            sample = {"type": "list", "length": len(value)}
        else:
            sample = {"type": "object", "keys": list(value.keys())[:25]}
        bucket = seen[path]
        if sample not in bucket and len(bucket) < limit_per_path:
            bucket.append(sample)
    return dict(sorted(seen.items()))


def key_inventory(payload: dict):
    counts = Counter()
    path_counts = Counter()
    type_counts = Counter()
    for path, value, _depth in path_walk(payload):
        key = path.rsplit(".", 1)[-1]
        if key == "[]":
            continue
        counts[key] += 1
        path_counts[path] += 1
        type_counts[f"{path}:{type(value).__name__}"] += 1
    interesting = {
        key: count for key, count in counts.most_common()
        if INTEREST.search(key)
    }
    return {
        "interestingKeys": interesting,
        "topPaths": path_counts.most_common(120),
        "interestingTypes": [item for item in type_counts.most_common() if INTEREST.search(item[0])][:160],
    }


def site_summary(site: dict) -> dict:
    result = {
        "idG": site.get("idG"),
        "lastUpdated": site.get("lastUpdated"),
        "topLevelKeys": list(site.keys()),
    }
    for key in ("name", "typeOfSite", "accessibility", "operatingHours", "locationReference", "energyInfrastructureStation"):
        if key in site:
            result[key] = compact(site.get(key))
    # Include any provider-specific station/refill structures we have not guessed.
    for key, value in site.items():
        if key in result:
            continue
        if INTEREST.search(key):
            result[key] = compact(value)
    return result


def analyze(label: str, meta: dict) -> dict:
    payload, transport = fetch_json(meta["offerId"])
    sites = root_sites(payload)
    if not sites:
        raise RuntimeError(f"{label}: no energyInfrastructureSite entries")
    inventory = key_inventory(payload)
    examples = field_examples(payload)
    publication = payload.get("payload", {}).get("aegiEnergyInfrastructureTablePublication", {})
    return {
        "label": label,
        "offerId": meta["offerId"],
        "license": meta["license"],
        "transport": transport,
        "profile": {
            "modelBaseVersionG": payload.get("payload", {}).get("modelBaseVersionG"),
            "versionG": payload.get("payload", {}).get("versionG"),
            "profileNameG": payload.get("payload", {}).get("profileNameG"),
            "profileVersionG": payload.get("payload", {}).get("profileVersionG"),
            "publicationTime": publication.get("publicationTime"),
            "publicationCreator": compact(publication.get("publicationCreator")),
        },
        "counts": {
            "sites": len(sites),
            "sitesWithStationKey": sum("energyInfrastructureStation" in s for s in sites),
            "sitesWithCoordinatesToken": sum("coordinate" in json.dumps(s, ensure_ascii=False).lower() for s in sites),
            "sitesWithEvseToken": sum("evse" in json.dumps(s, ensure_ascii=False).lower() for s in sites),
            "sitesWithPriceToken": sum(any(t in json.dumps(s, ensure_ascii=False).lower() for t in ("price", "tariff", "cost")) for s in sites),
        },
        "inventory": inventory,
        "fieldExamples": examples,
        "sampleSites": [site_summary(s) for s in sites[:3]],
    }


def main() -> None:
    analyses = {}
    errors = {}
    for label, meta in OFFERS.items():
        try:
            analyses[label] = analyze(label, meta)
        except Exception as exc:
            errors[label] = repr(exc)
    report = {
        "schemaVersion": 1,
        "dataset": "germany-afir-static-schema-probe",
        "generatedAt": now(),
        "offers": analyses,
        "errors": errors,
    }
    out = Path("data/germany/afir_static_schema_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for label, result in analyses.items():
        print("TCC_AFIR_PROFILE=" + json.dumps({
            "label": label,
            **result["profile"],
            **result["counts"],
            "bytes": result["transport"]["bytes"],
        }, ensure_ascii=False, sort_keys=True))
        interesting = result["inventory"]["interestingKeys"]
        print("TCC_AFIR_KEYS=" + json.dumps({"label": label, "keys": interesting}, ensure_ascii=False, sort_keys=True))
        selected_examples = {
            path: values for path, values in result["fieldExamples"].items()
            if any(token in path.lower() for token in ("evse", "operator", "station", "refill", "connector", "power", "price", "tariff", "status", "available"))
        }
        print("TCC_AFIR_EXAMPLES=" + json.dumps({"label": label, "examples": dict(list(selected_examples.items())[:80])}, ensure_ascii=False, sort_keys=True))
    if errors:
        print("TCC_AFIR_ERRORS=" + json.dumps(errors, ensure_ascii=False, sort_keys=True))
    if len(analyses) < 3:
        raise SystemExit("not all anonymous AFIR schema probes succeeded")


if __name__ == "__main__":
    main()
