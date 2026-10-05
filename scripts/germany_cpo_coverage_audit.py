#!/usr/bin/env python3
"""Produce a reproducible German CPO-prefix tariff coverage audit.

A CPO key is the canonical five-character EVSE party prefix (country code plus
three-character party id, with separators removed), e.g. DEQRM. The audit is
strict: a prefix is complete only when every national-catalog site represented
by that prefix has a validated staging preferred tariff. A prefix is partial
when at least one but not all represented sites have such evidence, or when the
explicit research registry records an active partial investigation. Explicitly
blocked prefixes are tracked separately with the evidence needed to unblock.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_gz(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cpo_prefix(evse_id: str) -> str | None:
    x = re.sub(r"[^A-Za-z0-9]", "", str(evse_id or "")).upper()
    if len(x) < 5 or not x.startswith("DE"):
        return None
    return x[:5]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--catalog",
        type=Path,
        default=Path("data/germany/germany_non_tesla_catalog_staging_direct_cpo.json.gz"),
    )
    ap.add_argument(
        "--registry",
        type=Path,
        default=Path("config/germany_cpo_research_registry.json"),
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("data/germany/germany_cpo_coverage_audit.json"),
    )
    args = ap.parse_args()

    catalog = load_gz(args.catalog)
    registry = load_json(args.registry)
    if catalog.get("dataset") != "germany-national-non-tesla-catalog-staging-direct-cpo":
        raise RuntimeError("unexpected Germany direct-CPO staging catalog")
    if registry.get("countryCode") != "DE":
        raise RuntimeError("unexpected research registry country")

    by_prefix: dict[str, dict] = defaultdict(
        lambda: {
            "siteIds": set(),
            "pricedSiteIds": set(),
            "evseIds": set(),
            "operators": Counter(),
            "preferredSourceTypes": Counter(),
            "directProviders": Counter(),
        }
    )

    for site in catalog.get("sites") or []:
        prefixes = {p for p in (cpo_prefix(x) for x in (site.get("evseIds") or [])) if p}
        if not prefixes:
            continue
        pricing = site.get("pricing") or {}
        preferred = pricing.get("stagingPreferredTariff")
        direct = pricing.get("directCpo")
        for prefix in prefixes:
            row = by_prefix[prefix]
            row["siteIds"].add(site.get("id"))
            row["operators"][site.get("operator") or "<unknown>"] += 1
            for evse_id in site.get("evseIds") or []:
                if cpo_prefix(evse_id) == prefix:
                    row["evseIds"].add(re.sub(r"[^A-Za-z0-9]", "", str(evse_id)).upper())
            if preferred is not None:
                row["pricedSiteIds"].add(site.get("id"))
                row["preferredSourceTypes"][preferred.get("sourceType") or "<unknown>"] += 1
            if direct is not None:
                row["directProviders"][direct.get("provider") or "<unknown>"] += 1

    registry_entries = registry.get("entries") or {}
    missing_registry_prefixes = sorted(set(registry_entries) - set(by_prefix))
    if missing_registry_prefixes:
        raise RuntimeError(f"research registry contains prefixes absent from current catalog: {missing_registry_prefixes}")

    rows = []
    counts = Counter()
    for prefix in sorted(by_prefix):
        src = by_prefix[prefix]
        site_count = len(src["siteIds"])
        priced_count = len(src["pricedSiteIds"])
        if site_count <= 0:
            raise RuntimeError(f"empty CPO prefix group: {prefix}")

        auto_status = "remaining"
        if priced_count == site_count:
            auto_status = "complete"
        elif priced_count > 0:
            auto_status = "partial"

        reg = registry_entries.get(prefix)
        status = auto_status
        status_source = "catalog_exact_tariff_coverage"
        reason = None
        needed = None
        evidence_paths = []
        if reg:
            reg_status = reg.get("status")
            if reg_status not in {"partial", "blocked"}:
                raise RuntimeError(f"unsupported registry status for {prefix}: {reg_status}")
            if auto_status != "remaining":
                raise RuntimeError(
                    f"stale manual registry entry for {prefix}: catalog now reports {auto_status}; remove/update registry"
                )
            status = reg_status
            status_source = "research_registry"
            reason = reg.get("reason")
            needed = reg.get("neededToComplete")
            evidence_paths = reg.get("evidencePaths") or []

        counts[status] += 1
        rows.append(
            {
                "prefix": prefix,
                "status": status,
                "statusSource": status_source,
                "representedSites": site_count,
                "representedEvses": len(src["evseIds"]),
                "sitesWithValidatedPreferredTariff": priced_count,
                "coveragePct": round(priced_count * 100.0 / site_count, 2),
                "topOperators": [
                    {"operator": op, "sites": n} for op, n in src["operators"].most_common(5)
                ],
                "preferredSourceTypes": dict(src["preferredSourceTypes"]),
                "directProviders": dict(src["directProviders"]),
                "reason": reason,
                "neededToComplete": needed,
                "evidencePaths": evidence_paths,
            }
        )

    total = len(rows)
    complete = counts["complete"]
    partial = counts["partial"]
    blocked = counts["blocked"]
    remaining = counts["remaining"]
    treated = complete + partial + blocked
    if treated + remaining != total:
        raise RuntimeError("CPO audit count invariant failed")

    out = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-cpo-prefix-tariff-coverage-audit",
        "countryCode": "DE",
        "generatedAt": utc_now(),
        "sourceCatalog": {
            "dataset": catalog.get("dataset"),
            "schemaVersion": catalog.get("schemaVersion"),
            "generatedAt": catalog.get("generatedAt"),
        },
        "definition": {
            "cpoKey": "canonical EVSE party prefix: DE + 3-character party id",
            "complete": "all represented catalog sites have a validated staging preferred tariff",
            "partial": "some represented sites have validated tariff evidence, or an explicit active research entry exists",
            "blocked": "explicit research entry documents why exact CPO/station tariff evidence is unavailable",
            "remaining": "no validated tariff coverage and no explicit partial/blocked research classification",
            "treated": "complete + partial + blocked",
        },
        "counts": {
            "treated": treated,
            "total": total,
            "complete": complete,
            "partial": partial,
            "blocked": blocked,
            "remaining": remaining,
        },
        "blocked": [r for r in rows if r["status"] == "blocked"],
        "partial": [r for r in rows if r["status"] == "partial"],
        "complete": [r for r in rows if r["status"] == "complete"],
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TCC_GERMANY_CPO_COVERAGE_AUDIT=" + json.dumps(out["counts"], sort_keys=True))
    print("TCC_GERMANY_CPO_BLOCKED=" + json.dumps(out["blocked"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
