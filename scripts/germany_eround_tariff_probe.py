#!/usr/bin/env python3
"""Inspect eRound AFIR static tariff structures missed by the current parser.

The normalizer currently recognizes DATEX electricEnergy -> energyRate ->
energyPrice structures. This QA probe compares that result with recursive raw
price/rate/tariff evidence and records the dominant paths for missed sites.
No price becomes rankable or is published to TCC here.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import germany_afir_static_normalize as afir

PROVIDER = "eround"
OFFER_ID = afir.OFFERS[PROVIDER]["offerId"]
PRICE_HINTS = ("price", "tariff", "rate", "currency", "cost")
MAX_EXAMPLES = 30


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def site_has_normalized_tariff(site: dict):
    if site.get("tariffs"):
        return True
    for station in site.get("stations") or []:
        if station.get("tariffs"):
            return True
        for point in station.get("points") or []:
            if point.get("tariffs"):
                return True
    return False


def scalar_preview(value: Any):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        out = {}
        for key, child in list(value.items())[:20]:
            if isinstance(child, (str, int, float, bool)) or child is None:
                out[key] = child
            elif isinstance(child, list):
                out[key] = {"type": "list", "length": len(child)}
            elif isinstance(child, dict):
                out[key] = {"type": "object", "keys": list(child.keys())[:15]}
        return out
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    return str(type(value).__name__)


def raw_tariff_evidence(obj: Any, path: str = "$", out: list | None = None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}"
            lk = key.lower()
            if any(hint in lk for hint in PRICE_HINTS):
                out.append({"path": child_path, "key": key, "preview": scalar_preview(value)})
            raw_tariff_evidence(value, child_path, out)
    elif isinstance(obj, list):
        for value in obj:
            raw_tariff_evidence(value, path + "[]", out)
    return out


def canonical_path(path: str):
    return path.replace("[]", "[*]")


def main():
    payload, transport = afir.fetch_offer(OFFER_ID)
    raw_sites, profile = afir.get_sites(payload)

    stats = Counter()
    all_raw_paths = Counter()
    missed_raw_paths = Counter()
    parsed_raw_paths = Counter()
    missed_examples = []
    parsed_examples = []

    for raw_site in raw_sites:
        normalized = afir.normalize_site(PROVIDER, OFFER_ID, raw_site)
        parsed = site_has_normalized_tariff(normalized)
        evidence = raw_tariff_evidence(raw_site)
        evidence_paths = sorted({canonical_path(x["path"]) for x in evidence})
        raw_has = bool(evidence)

        stats["sites"] += 1
        stats["normalizedTariffSites"] += int(parsed)
        stats["sitesWithAnyRawTariffHint"] += int(raw_has)
        if raw_has and not parsed:
            stats["rawHintButParserMissedSites"] += 1
        if parsed and not raw_has:
            stats["parserTariffWithoutRawHintSites"] += 1

        for path in evidence_paths:
            all_raw_paths[path] += 1
            (parsed_raw_paths if parsed else missed_raw_paths)[path] += 1

        compact = {
            "sourceSiteId": raw_site.get("idG"),
            "lastUpdated": raw_site.get("lastUpdated"),
            "name": afir.text_value(raw_site.get("name")),
            "normalizedStationCount": normalized.get("stationCount"),
            "normalizedChargePointCount": normalized.get("chargePointCount"),
            "normalizedEvseCount": len(normalized.get("evseIds") or []),
            "evidence": evidence[:40],
        }
        if raw_has and not parsed and len(missed_examples) < MAX_EXAMPLES:
            missed_examples.append(compact)
        if parsed and len(parsed_examples) < 8:
            parsed_examples.append(compact)

    report = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-eround-afir-tariff-structure-probe",
        "generatedAt": utc_now(),
        "countryCode": "DE",
        "provider": PROVIDER,
        "offerId": OFFER_ID,
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "tariffsRankable": False,
            "purpose": "Identify raw eRound price/rate structures missed by the existing AFIR tariff parser.",
        },
        "transport": transport,
        "profile": profile,
        "stats": dict(stats),
        "topRawTariffPaths": all_raw_paths.most_common(80),
        "topMissedTariffPaths": missed_raw_paths.most_common(80),
        "topParsedTariffPaths": parsed_raw_paths.most_common(80),
        "missedExamples": missed_examples,
        "parsedExamples": parsed_examples,
    }

    out = Path("data/germany/eround_tariff_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("TCC_EROUND_TARIFF_PROBE=" + json.dumps(report["stats"], sort_keys=True))
    print("TCC_EROUND_TARIFF_MISSED_PATHS=" + json.dumps(report["topMissedTariffPaths"][:25], ensure_ascii=False))
    for example in missed_examples[:5]:
        print("TCC_EROUND_TARIFF_MISSED_EXAMPLE=" + json.dumps(example, ensure_ascii=False)[:12000])


if __name__ == "__main__":
    main()
