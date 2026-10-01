#!/usr/bin/env python3
"""Audit France CPO source-registry coverage without counting queue hints as reviews.

The script is intentionally conservative:
- a party ID is considered reviewed only when it appears as a dictionary `partyId`
  in a France regional audit, or is explicitly represented in canonical evidence
  (activeEvidenceStatus / aliasRegistry / setAside);
- `nextTargets`, `nextCoverageTargets` and prose-only queue mentions never count;
- the 253-party technical registry is kept separate from the historical 291-CPO
  accounting, so this script never mutates treated/set-aside/active counters.

Usage:
    python scripts/france_cpo_coverage_audit.py
    python scripts/france_cpo_coverage_audit.py --write docs/france-cpo-coverage-crosswalk.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REGISTRY = DOCS / "france-cpo-source-party-registry-2026-09-05.json"
CANONICAL = DOCS / "france-cpo-progress-2026-09.json"
AUDIT_GLOBS = (
    "france-regional-cpo-*.json",
    "france-cpo-aggressive-recheck-*.json",
    "france-cpo-yes55-*.json",
)
PARTY_RE = re.compile(r"FR\*[A-Z0-9]{3}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_dict_party_ids(value: Any) -> Iterable[str]:
    """Yield explicit partyId values from nested dictionaries/lists only."""
    if isinstance(value, dict):
        party_id = value.get("partyId")
        if isinstance(party_id, str) and PARTY_RE.fullmatch(party_id):
            yield party_id
        for child in value.values():
            yield from iter_dict_party_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dict_party_ids(child)


def extract_party_ids_from_strings(value: Any) -> set[str]:
    """Extract explicit EMI3 IDs from canonical evidence strings/keys."""
    found: set[str] = set()
    if isinstance(value, str):
        found.update(PARTY_RE.findall(value))
    elif isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str):
                found.update(PARTY_RE.findall(key))
            found.update(extract_party_ids_from_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.update(extract_party_ids_from_strings(child))
    return found


def canonical_explicit_evidence(canonical: dict[str, Any]) -> set[str]:
    """Only canonical sections that represent a decision/evidence state count."""
    sections = [
        canonical.get("activeEvidenceStatus", {}),
        canonical.get("aliasRegistry", []),
        canonical.get("setAside", []),
    ]
    found: set[str] = set()
    for section in sections:
        found.update(extract_party_ids_from_strings(section))
    return found


def audit_paths() -> list[Path]:
    paths: set[Path] = set()
    for pattern in AUDIT_GLOBS:
        paths.update(DOCS.glob(pattern))
    return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=Path, help="Write the JSON report to this path")
    args = parser.parse_args()

    registry = load_json(REGISTRY)
    canonical = load_json(CANONICAL)
    registered = [entry["partyId"] for entry in registry["partyIds"]]
    registered_set = set(registered)

    evidence_files: dict[str, set[str]] = defaultdict(set)
    explicitly_reviewed: set[str] = set()

    for path in audit_paths():
        try:
            payload = load_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        for party_id in iter_dict_party_ids(payload):
            if party_id in registered_set:
                explicitly_reviewed.add(party_id)
                evidence_files[party_id].add(str(path.relative_to(ROOT)))

    canonical_ids = canonical_explicit_evidence(canonical) & registered_set
    for party_id in canonical_ids:
        evidence_files[party_id].add(str(CANONICAL.relative_to(ROOT)))

    handled = explicitly_reviewed | canonical_ids
    missing = [party_id for party_id in registered if party_id not in handled]

    # Coverage and historical accounting are deliberately separate invariants.
    treated = int(canonical["treatedCpos"])
    set_aside = int(canonical["setAsideCpos"])
    active = int(canonical["activeRemainingCpos"])
    total = int(canonical["totalCpos"])
    arithmetic_ok = treated + set_aside + active == total

    report = {
        "schemaVersion": 1,
        "country": "FR",
        "registryPath": str(REGISTRY.relative_to(ROOT)),
        "canonicalPath": str(CANONICAL.relative_to(ROOT)),
        "registryPartyIds": len(registered),
        "explicitlyReviewedPartyIds": len(explicitly_reviewed),
        "canonicalEvidencePartyIds": len(canonical_ids),
        "handledPartyIds": len(handled),
        "missingPartyIds": missing,
        "coverageComplete": not missing,
        "historical291Accounting": {
            "treated": treated,
            "setAside": set_aside,
            "active": active,
            "total": total,
            "arithmeticOk": arithmetic_ok,
        },
        "rules": {
            "queueHintsDoNotCount": True,
            "technicalRegistryDoesNotMutateHistoricalCounters": True,
            "partyIdObjectOrCanonicalDecisionEvidenceRequired": True,
        },
        "evidenceFiles": {
            party_id: sorted(evidence_files[party_id]) for party_id in registered if party_id in evidence_files
        },
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        output = args.write if args.write.is_absolute() else ROOT / args.write
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if arithmetic_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
