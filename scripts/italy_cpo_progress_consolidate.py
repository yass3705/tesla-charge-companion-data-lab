#!/usr/bin/env python3
"""Losslessly consolidate Italy CPO progress deltas into the canonical JSON.

The canonical file is the inventory seed. Ordered run deltas are then replayed.
Historical `changes`, modern `classificationUpdates`, and the legacy
`safeStatusTransitions` / `classificationUpdatesWithoutStatusTransition`
shapes are supported. Every raw party-scoped update is retained in
`deltaEvidence`, so newer summary fields can supersede older values without
discarding the evidence that produced them. Non-CPO relationship records are
retained at top level.

Run labels may contain a suffix (for example run4b and run7b). They are ordered
as 4, 4b, 5 ... 7, 7b, 8 so no historical delta is silently skipped.

The script recomputes named status counts and fails closed on duplicate partyIds
or physical-inventory mismatch. It does not use GitHub code search for EVSE
deduplication; run `italy_cpo_delta_evse_dedup_audit.py` before promotion.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

RUN_RE = re.compile(r"italy-cpo-progress-2026-09-run(\d+)([a-z]*)-delta\.json$", re.IGNORECASE)
STATUSES = {"treated", "partial", "setAside", "active", "supersededAlias"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(dst, src):
    """Merge latest summary fields while raw update history is stored separately."""
    if isinstance(dst, dict) and isinstance(src, dict):
        out = copy.deepcopy(dst)
        for key, value in src.items():
            if key in {"historyAppend", "deltaEvidence"}:
                continue
            if key in out and isinstance(out[key], dict) and isinstance(value, dict):
                out[key] = deep_merge(out[key], value)
            else:
                out[key] = copy.deepcopy(value)
        return out
    return copy.deepcopy(src)


def iter_updates(delta):
    # Historical files used several shapes; all party-scoped forms must replay.
    for upd in delta.get("changes") or []:
        yield "changes", upd
    for upd in delta.get("safeStatusTransitions") or []:
        yield "safeStatusTransitions", upd
    for upd in delta.get("classificationUpdatesWithoutStatusTransition") or []:
        yield "classificationUpdatesWithoutStatusTransition", upd
    for upd in delta.get("classificationUpdates") or []:
        yield "classificationUpdates", upd


def normalize_party_update(update):
    upd = copy.deepcopy(update)
    if not upd.get("status"):
        if upd.get("statusTo"):
            upd["status"] = upd["statusTo"]
        elif upd.get("to") in STATUSES:
            upd["status"] = upd["to"]
    # `from`/`to` describe transition evidence, not canonical summary fields.
    upd.pop("from", None)
    upd.pop("to", None)
    return upd


def append_unique(seq, item):
    if item not in seq:
        seq.append(item)


def run_label(number: int, suffix: str) -> str:
    return f"{number}{suffix}" if suffix else str(number)


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
            number = int(m.group(1))
            suffix = m.group(2).lower()
            delta_paths.append((number, suffix, p))
    delta_paths.sort(key=lambda item: (item[0], item[1]))

    top_history = list(canonical.get("history") or [])
    non_cpo_evidence = list(canonical.get("nonCpoDeltaEvidence") or [])
    applied_run_labels = []

    for number, suffix, path in delta_paths:
        label = run_label(number, suffix)
        applied_run_labels.append(label)
        delta = load_json(path)
        for shape, raw_update in iter_updates(delta):
            pid = raw_update.get("partyId")
            if not pid:
                append_unique(non_cpo_evidence, {
                    "run": label,
                    "path": str(path),
                    "shape": shape,
                    "update": copy.deepcopy(raw_update),
                })
                continue

            upd = normalize_party_update(raw_update)
            if pid not in by_id:
                if upd.get("status") != "supersededAlias":
                    raise SystemExit(f"{path}: unknown partyId {pid}; refusing inventory expansion")
                by_id[pid] = {"partyId": pid}
                order.append(pid)

            prior_evidence = list(by_id[pid].get("deltaEvidence") or [])
            merged = deep_merge(by_id[pid], upd)
            evidence_entry = {
                "run": label,
                "path": str(path),
                "shape": shape,
                "update": copy.deepcopy(raw_update),
            }
            append_unique(prior_evidence, evidence_entry)
            merged["deltaEvidence"] = prior_evidence

            h = list(merged.get("history") or [])
            ha = upd.get("historyAppend")
            if isinstance(ha, str):
                append_unique(h, ha)
            elif isinstance(ha, list):
                for item in ha:
                    append_unique(h, item)
            if h:
                merged["history"] = h
            merged.pop("historyAppend", None)
            by_id[pid] = merged

        for key in ("history", "historyAppend"):
            items = delta.get(key) or []
            if isinstance(items, str):
                items = [items]
            for item in items:
                append_unique(top_history, item)

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
    canonical["nonCpoDeltaEvidence"] = non_cpo_evidence
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
        "lastAppliedDeltaRun": applied_run_labels[-1] if applied_run_labels else None,
        "appliedDeltaRuns": applied_run_labels,
        "result": "pass",
        "deltaShapesReplayed": [
            "changes",
            "safeStatusTransitions",
            "classificationUpdatesWithoutStatusTransition",
            "classificationUpdates",
        ],
        "rawDeltaEvidenceRetained": True,
        "evseDedupGuard": "scripts/italy_cpo_delta_evse_dedup_audit.py",
    }

    output = Path(args.output) if args.output else canonical_path
    output.write_text(json.dumps(canonical, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(canonical["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
