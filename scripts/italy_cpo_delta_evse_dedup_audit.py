#!/usr/bin/env python3
"""Audit Italy progress deltas for EVSE IDs credited more than once.

Reads checked-out branch files directly instead of GitHub code search, because
code search may index only the default branch. Supports legacy `changes` and
modern `classificationUpdates`, explicit `evseIds`, and simple `evsePattern`
ranges used by Italy progress deltas.

The optional --candidate-id argument is a pre-promotion guard: every supplied
EVSE ID is checked against the full ordered ledger and reported as already-seen
or new. This avoids using repository search absence as proof of novelty.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

RUN_RE = re.compile(r"italy-cpo-progress-2026-09-run(\d+)-delta\.json$")
RANGE_RE = re.compile(r"^(.*?)(\d+)\.\.(?:(.*?))?(\d+)$")


def iter_updates(delta: dict):
    yield from delta.get("changes") or []
    yield from delta.get("classificationUpdates") or []


def expand_evse_pattern(pattern: str):
    """Expand simple numeric ranges such as IT*EMO*E2011*1..6.

    If the right side repeats the prefix, e.g. A1..A6, it is also accepted.
    Unknown pattern shapes are deliberately ignored rather than guessed.
    """
    if not pattern:
        return []
    m = RANGE_RE.match(pattern)
    if not m:
        return []
    left_prefix, start_s, right_prefix, end_s = m.groups()
    if right_prefix and right_prefix != left_prefix:
        return []
    start, end = int(start_s), int(end_s)
    if end < start or end - start > 10000:
        return []
    return [f"{left_prefix}{i}" for i in range(start, end + 1)]


def iter_mapping_ids(update: dict):
    for key in ("newExactMappings", "newCoveredSubpopulations"):
        for mapping in update.get(key) or []:
            location = mapping.get("location")
            for evse_id in mapping.get("evseIds") or []:
                yield evse_id, location, key
            for evse_id in expand_evse_pattern(mapping.get("evsePattern")):
                yield evse_id, location, f"{key}.evsePattern"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-dir", default="docs")
    ap.add_argument("--party-id", default=None)
    ap.add_argument("--allow-through-run", type=int, default=72)
    ap.add_argument("--candidate-id", action="append", default=[])
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
            for evse_id, location, source_field in iter_mapping_ids(update):
                occurrences[evse_id].append({
                    "run": run,
                    "path": str(path),
                    "partyId": party_id,
                    "location": location,
                    "sourceField": source_field,
                })

    duplicates = {eid: occ for eid, occ in occurrences.items() if len(occ) > 1}
    future_violations = {
        eid: occ for eid, occ in duplicates.items()
        if max(x["run"] for x in occ) > args.allow_through_run
    }
    candidate_checks = {
        eid: {
            "alreadySeen": eid in occurrences,
            "occurrences": occurrences.get(eid, []),
        }
        for eid in args.candidate_id
    }
    report = {
        "partyIdFilter": args.party_id,
        "uniqueEvseIdsObserved": len(occurrences),
        "duplicateEvseIds": len(duplicates),
        "historicalDuplicates": duplicates,
        "allowThroughRun": args.allow_through_run,
        "futureViolations": future_violations,
        "candidateChecks": candidate_checks,
        "candidateNovelIds": [
            eid for eid, check in candidate_checks.items() if not check["alreadySeen"]
        ],
        "candidateAlreadySeenIds": [
            eid for eid, check in candidate_checks.items() if check["alreadySeen"]
        ],
        "result": "fail" if future_violations else "pass_with_historical_duplicates_recorded",
    }

    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        Path(args.json_output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if future_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
