#!/usr/bin/env python3
"""Losslessly consolidate Italy CPO progress deltas into the canonical JSON.

Usage:
  python scripts/consolidate_italy_cpo_progress.py \
    --canonical docs/italy-cpo-progress-2026-09.json \
    --docs-dir docs \
    --write

The script is intentionally fail-closed: it validates partyIds, transition sources,
canonical counts, alias semantics, and inventory totals before writing.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

RUN_RE = re.compile(r"italy-cpo-progress-2026-09-run(?P<num>\d+)(?P<suffix>[a-z]*)-delta\.json$")


def deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for k, v in src.items():
        if k in {"partyId", "from", "to"}:
            continue
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        elif isinstance(v, list) and isinstance(dst.get(k), list):
            # Preserve order while avoiding exact duplicate scalar/dict entries.
            for item in v:
                if item not in dst[k]:
                    dst[k].append(copy.deepcopy(item))
        else:
            dst[k] = copy.deepcopy(v)
    return dst


def run_key(path: Path) -> tuple[int, str]:
    m = RUN_RE.search(path.name)
    if not m:
        raise ValueError(path)
    return int(m.group("num")), m.group("suffix") or ""


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical", type=Path, required=True)
    ap.add_argument("--docs-dir", type=Path, required=True)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    canonical = load_json(args.canonical)
    original_inventory = canonical.get("inventorySource", {})
    cpos = canonical.get("cpos", [])
    by_id = {row["partyId"]: row for row in cpos}
    if len(by_id) != len(cpos):
        raise SystemExit("duplicate partyId in base canonical")

    deltas = sorted(args.docs_dir.glob("italy-cpo-progress-2026-09-run*-delta.json"), key=run_key)
    if not deltas:
        raise SystemExit("no deltas found")

    applied: list[str] = []
    history = list(canonical.get("history", []))

    for path in deltas:
        delta = load_json(path)
        for tr in delta.get("safeStatusTransitions", []):
            pid = tr["partyId"]
            if pid not in by_id:
                raise SystemExit(f"{path.name}: unknown transition partyId {pid}")
            row = by_id[pid]
            current = row.get("status")
            expected = tr.get("from")
            target = tr.get("to")
            if expected is not None and current != expected:
                # Idempotency: a previously consolidated target is acceptable.
                if current != target:
                    raise SystemExit(f"{path.name}: {pid} status {current!r} != expected {expected!r}")
            row["status"] = target
            deep_merge(row, tr)

        for upd in delta.get("classificationUpdatesWithoutStatusTransition", []):
            pid = upd["partyId"]
            if pid not in by_id:
                raise SystemExit(f"{path.name}: unknown classification partyId {pid}")
            deep_merge(by_id[pid], upd)

        for upd in delta.get("cpoUpdates", []):
            pid = upd["partyId"]
            if pid not in by_id:
                raise SystemExit(f"{path.name}: unknown cpoUpdates partyId {pid}")
            deep_merge(by_id[pid], upd)

        group = delta.get("canonicalGroupUpdate")
        if group:
            pid = group["partyId"]
            if pid not in by_id:
                raise SystemExit(f"{path.name}: unknown canonical group partyId {pid}")
            deep_merge(by_id[pid], group)

        for alias in delta.get("aliasDecisions", []):
            for pid in alias.get("partyIds", []):
                if pid in by_id:
                    by_id[pid].setdefault("aliasDecisions", []).append(copy.deepcopy(alias))

        for line in delta.get("history", []):
            if line not in history:
                history.append(line)
        applied.append(path.name)

    # Canonical current-CPO denominator excludes rows explicitly superseded as aliases.
    status_counts: dict[str, int] = {}
    for row in cpos:
        st = row.get("status", "active")
        status_counts[st] = status_counts.get(st, 0) + 1

    inventory_party_ids = int(original_inventory.get("partyIds", len(cpos)))
    if len(cpos) != inventory_party_ids:
        raise SystemExit(f"inventory rows {len(cpos)} != inventory partyIds {inventory_party_ids}")
    if sum(status_counts.values()) != inventory_party_ids:
        raise SystemExit("status count does not cover physical inventory")

    alias_count = status_counts.get("supersededAlias", 0)
    total_canonical = inventory_party_ids - alias_count
    current_sum = sum(status_counts.get(k, 0) for k in ("treated", "partial", "setAside", "active"))
    if current_sum != total_canonical:
        raise SystemExit(f"current canonical status sum {current_sum} != {total_canonical}")

    # Atlante invariants.
    ate = by_id.get("ATE")
    if not ate or ate.get("status") != "setAside":
        raise SystemExit("Atlante must remain setAside")

    canonical["generatedAt"] = max(
        [canonical.get("generatedAt", "")] + [load_json(p).get("generatedAt", "") for p in deltas]
    )
    canonical["counts"] = {
        "treated": status_counts.get("treated", 0),
        "partial": status_counts.get("partial", 0),
        "setAside": status_counts.get("setAside", 0),
        "active": status_counts.get("active", 0),
        "supersededAlias": alias_count,
        "totalCanonicalCpos": total_canonical,
        "inventoryPartyIds": inventory_party_ids,
    }
    canonical["consistency"] = {
        "canonicalStatusSumExcludingAliases": current_sum,
        "canonicalStatusSumIncludingSupersededAliasRows": sum(status_counts.values()),
        "matchesInventoryPartyIds": sum(status_counts.values()) == inventory_party_ids,
        "duplicatePartyIds": len(cpos) - len(by_id),
        "artifactPartyIds": inventory_party_ids,
        "artifactEvse": original_inventory.get("observedEvse"),
        "atlanteRemainsSetAside": True,
        "canonicalPhysicalSnapshotStillStale": False,
        "deltasApplied": applied,
    }
    canonical["history"] = history

    rendered = json.dumps(canonical, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if args.write:
        args.canonical.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
