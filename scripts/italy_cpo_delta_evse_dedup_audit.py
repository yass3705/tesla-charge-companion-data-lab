#!/usr/bin/env python3
"""Audit Italy progress deltas for EVSE IDs credited more than once.

This intentionally reads the checked-out branch files directly instead of using
GitHub code search, because code search may index only the default branch and can
therefore miss research-branch deltas. It understands both legacy `changes` and
newer `classificationUpdates` shapes and extracts IDs from `newExactMappings`
and `newCoveredSubpopulations`.

Exit status is non-zero when duplicate EVSE credits are found unless every
repeated occurrence is in or before --allow-through-run. This makes the script
usable as a guard for future deltas after historical defects have been recorded.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

RUN_RE = re.compile(r"italy-cpo-progress-2026-09-run(\d+)-delta\.json$")


def iter_updates(delta: dict):
    yield from delta.get("changes") or []
    yield from delta.get("classificationUpdates") or []


def iter_mapping_ids(update: dict):
    for key in ("newExactMappings", "newCoveredSubpopulations"):
        for mapping in update.get(key) or []:
            for evse_id in mapping.get("evseIds") or []:
                yield evse_id, mapping.get("location")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-dir", default="docs")
    ap.add_argument("--party-id", default=None)
    ap.add_argument("--allow-through-run", type=int, default=72)
    ap.add_argument("--json-output", default=None)
    args = ap.parse_args()

    occurrences = defaultdict(list)
    files = []
    for path in Path(args.docs_dir).glob("italy-cpo-progress-2026-09-run*-delta.json"):
        m = RUN_RE.search(path.name)
        if m:
            files.append((int(m.group(1)), path))
    files.sort()

    for run, path in files:
        delta = json.loads(path.read_text(encoding="utf-8"))
        for update in iter_updates(delta):
            party_id = update.get("partyId")
            if args.party_id and party_id != args.party_id:
                continue
            for evse_id, location in iter_mapping_ids(update):
                occurrences[evse_id].append({
                    "run": run,
                    "path": str(path),
                    "partyId": party_id,
                    "location": location,
                })

    duplicates = {eid: occ for eid, occ in occurrences.items() if len(occ) > 1}
    future_violations = {
        eid: occ for eid, occ in duplicates.items()
        if max(x["run"] for x in occ) > args.allow_through_run
    }
    report = {
        "partyIdFilter": args.party_id,
        "uniqueEvseIdsObserved": len(occurrences),
        "duplicateEvseIds": len(duplicates),
        "historicalDuplicates": duplicates,
        "allowThroughRun": args.allow_through_run,
        "futureViolations": future_violations,
        "result": "fail" if future_violations else "pass_with_historical_duplicates_recorded",
    }

    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        Path(args.json_output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if future_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
