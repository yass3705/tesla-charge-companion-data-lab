#!/usr/bin/env python3
"""Losslessly consolidate Italy CPO progress deltas into the canonical JSON.

The script treats docs/italy-cpo-progress-2026-09.json as the inventory seed and
applies docs/italy-cpo-progress-2026-09-run*-delta.json in numeric run order.
For each classificationUpdates entry, fields are merged by partyId without
removing pre-existing metadata. historyAppend values are appended to the CPO
history and top-level history. Counts are recomputed from the resulting named
records. The script fails closed on duplicate partyIds or counter mismatch.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

RUN_RE = re.compile(r"italy-cpo-progress-2026-09-run(\d+)-delta\.json$")
STATUSES = {"treated", "partial", "setAside", "active", "supersededAlias"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(dst, src):
    if isinstance(dst, dict) and isinstance(src, dict):
        out = copy.deepcopy(dst)
        for key, value in src.items():
            if key in out and isinstance(out[key], dict) and isinstance(value, dict):
                out[key] = deep_merge(out[key], value)
            elif key == "historyAppend":
                continue
            else:
                out[key] = copy.deepcopy(value)
        return out
    return copy.deepcopy(src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical", default="docs/italy-cpo-progress-2026-09.json")
    ap.add_argument("--docs-dir", default="docs")
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    canonical_path = Path(args.canonical)
    canonical = load_json(canonical_path)
    cpos = canonical.get("cpos") or []
    by_id = {}
    order = []
    for cpo in cpos:
        pid = cpo.get("partyId")
        if not pid or pid in by_id:
            raise SystemExit(f"duplicate/missing canonical partyId: {pid!r}")
        by_id[pid] = copy.deepcopy(cpo)
        order.append(pid)

    delta_paths = []
    for p in Path(args.docs_dir).glob("italy-cpo-progress-2026-09-run*-delta.json"):
        m = RUN_RE.search(p.name)
        if m:
            delta_paths.append((int(m.group(1)), p))
    delta_paths.sort()

    top_history = list(canonical.get("history") or [])
    last_run = None
    for run, path in delta_paths:
        delta = load_json(path)
        last_run = run
        for upd in delta.get("classificationUpdates") or []:
            pid = upd.get("partyId")
            if not pid:
                raise SystemExit(f"{path}: classification update without partyId")
            if pid not in by_id:
                # New aliases/partyIds are permitted only when explicitly marked supersededAlias.
                if upd.get("status") != "supersededAlias":
                    raise SystemExit(f"{path}: unknown partyId {pid}; refusing inventory expansion")
                by_id[pid] = {}
                order.append(pid)
            merged = deep_merge(by_id[pid], upd)
            h = list(merged.get("history") or [])
            ha = upd.get("historyAppend")
            if isinstance(ha, str) and ha not in h:
                h.append(ha)
            elif isinstance(ha, list):
                for item in ha:
                    if item not in h:
                        h.append(item)
            if h:
                merged["history"] = h
            merged.pop("historyAppend", None)
            by_id[pid] = merged
        for item in delta.get("historyAppend") or []:
            if item not in top_history:
                top_history.append(item)

    out_cpos = [by_id[pid] for pid in order]
    seen = set()
    for cpo in out_cpos:
        pid = cpo.get("partyId")
        if pid in seen:
            raise SystemExit(f"duplicate partyId after merge: {pid}")
        seen.add(pid)
        if cpo.get("status") not in STATUSES:
            raise SystemExit(f"invalid/missing status for {pid}: {cpo.get('status')!r}")

    status_counts = {s: 0 for s in STATUSES}
    for cpo in out_cpos:
        status_counts[cpo["status"]] += 1
    canonical_total = sum(status_counts[s] for s in ("treated", "partial", "setAside", "active"))
    physical_total = canonical_total + status_counts["supersededAlias"]

    inventory_party_ids = int((canonical.get("inventorySource") or {}).get("partyIds", physical_total))
    if physical_total != inventory_party_ids:
        raise SystemExit(
            f"physical partyId mismatch: merged={physical_total} inventory={inventory_party_ids}"
        )

    canonical["cpos"] = out_cpos
    canonical["history"] = top_history
    canonical["counts"] = {
        "treated": status_counts["treated"],
        "partial": status_counts["partial"],
        "setAside": status_counts["setAside"],
        "active": status_counts["active"],
        "total": canonical_total,
        "supersededAlias": status_counts["supersededAlias"],
        "physicalPartyIds": physical_total,
    }
    canonical["consistency"] = {
        "statusSumCanonical": canonical_total,
        "matchesInventory": physical_total == inventory_party_ids,
        "duplicatePartyIds": len(out_cpos) - len(seen),
        "lastAppliedDeltaRun": last_run,
        "result": "pass",
    }

    output = Path(args.output) if args.output else canonical_path
    output.write_text(json.dumps(canonical, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(canonical["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
