#!/usr/bin/env python3
"""Verify eRound AFIR tariff coverage against actual raw price values.

DATEX objects may contain energyRate/ratePolicy/currency shells even when
energyPrice is an empty list. This probe separates those shells from actual
price entries and proves whether the existing normalizer misses any real price.
Staging/QA only: no tariff becomes rankable or is published to TCC.
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
MAX_EXAMPLES = 25


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


def canonical_path(path: str):
    return path.replace("[]", "[*]")


def collect_price_evidence(obj: Any, path: str = "$", out: list | None = None, policies: Counter | None = None):
    if out is None:
        out = []
    if policies is None:
        policies = Counter()
    if isinstance(obj, dict):
        policy = obj.get("ratePolicy")
        if policy is not None:
            if isinstance(policy, dict):
                policy = policy.get("value") or policy.get("extendedValueG") or json.dumps(policy, sort_keys=True)
            policies[str(policy)] += 1
        for key, value in obj.items():
            child_path = f"{path}.{key}"
            if key == "energyPrice":
                entries = afir.as_list(value)
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    amount = afir.safe_float(entry.get("value"))
                    cap = afir.safe_float(entry.get("priceCap"))
                    price_type = afir.enum_value(entry.get("priceType"))
                    # A DATEX energyPrice object is actionable evidence when it
                    # actually carries a numeric value/cap, not merely because
                    # the empty structural key exists.
                    if amount is not None or cap is not None:
                        out.append({
                            "path": canonical_path(child_path),
                            "value": amount,
                            "priceCap": cap,
                            "priceType": price_type,
                            "taxIncluded": entry.get("taxIncluded"),
                        })
            collect_price_evidence(value, child_path, out, policies)
    elif isinstance(obj, list):
        for value in obj:
            collect_price_evidence(value, path + "[]", out, policies)
    return out, policies


def main():
    payload, transport = afir.fetch_offer(OFFER_ID)
    raw_sites, profile = afir.get_sites(payload)

    stats = Counter()
    actual_price_paths = Counter()
    missed_actual_price_paths = Counter()
    empty_shell_policies = Counter()
    missed_actual_examples = []
    shell_examples = []

    for raw_site in raw_sites:
        normalized = afir.normalize_site(PROVIDER, OFFER_ID, raw_site)
        parsed = site_has_normalized_tariff(normalized)
        evidence, policies = collect_price_evidence(raw_site)
        has_actual_price = bool(evidence)

        stats["sites"] += 1
        stats["normalizedTariffSites"] += int(parsed)
        stats["sitesWithActualRawPrice"] += int(has_actual_price)
        stats["sitesWithNoActualRawPrice"] += int(not has_actual_price)
        stats["actualRawPriceButParserMissedSites"] += int(has_actual_price and not parsed)
        stats["parserTariffWithoutActualRawPriceSites"] += int(parsed and not has_actual_price)

        for item in evidence:
            actual_price_paths[item["path"]] += 1
            if not parsed:
                missed_actual_price_paths[item["path"]] += 1

        if not has_actual_price:
            empty_shell_policies.update(policies)
            if len(shell_examples) < 8:
                shell_examples.append({
                    "sourceSiteId": raw_site.get("idG"),
                    "name": afir.text_value(raw_site.get("name")),
                    "lastUpdated": raw_site.get("lastUpdated"),
                    "ratePolicies": dict(policies),
                    "stationCount": normalized.get("stationCount"),
                    "chargePointCount": normalized.get("chargePointCount"),
                })
        elif not parsed and len(missed_actual_examples) < MAX_EXAMPLES:
            missed_actual_examples.append({
                "sourceSiteId": raw_site.get("idG"),
                "name": afir.text_value(raw_site.get("name")),
                "lastUpdated": raw_site.get("lastUpdated"),
                "actualPriceEvidence": evidence[:40],
            })

    report = {
        "schemaVersion": "0.2.0",
        "dataset": "germany-eround-afir-tariff-structure-probe",
        "generatedAt": utc_now(),
        "countryCode": "DE",
        "provider": PROVIDER,
        "offerId": OFFER_ID,
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "tariffsRankable": False,
            "emptyEnergyPriceIsNotTariff": True,
            "purpose": "Verify normalized tariff coverage against non-empty numeric DATEX energyPrice objects.",
        },
        "transport": transport,
        "profile": profile,
        "stats": dict(stats),
        "actualPricePaths": actual_price_paths.most_common(50),
        "missedActualPricePaths": missed_actual_price_paths.most_common(50),
        "noPriceRatePolicyDistribution": dict(empty_shell_policies),
        "missedActualPriceExamples": missed_actual_examples,
        "emptyTariffShellExamples": shell_examples,
    }

    out = Path("data/germany/eround_tariff_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("TCC_EROUND_TARIFF_PROBE=" + json.dumps(report["stats"], sort_keys=True))
    print("TCC_EROUND_TARIFF_PRICE_PATHS=" + json.dumps(report["actualPricePaths"][:20], ensure_ascii=False))
    print("TCC_EROUND_TARIFF_NO_PRICE_POLICIES=" + json.dumps(report["noPriceRatePolicyDistribution"], ensure_ascii=False, sort_keys=True))
    for example in missed_actual_examples[:5]:
        print("TCC_EROUND_TARIFF_REAL_MISS=" + json.dumps(example, ensure_ascii=False)[:12000])


if __name__ == "__main__":
    main()
