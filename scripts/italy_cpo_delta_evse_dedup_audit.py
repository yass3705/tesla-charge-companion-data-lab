#!/usr/bin/env python3
"""Audit Italy progress deltas for EVSE IDs credited more than once.

The audit replays checked-out branch files, not default-branch code search.
It supports legacy/modern Italy delta containers, suffixed runs, explicit EVSE
IDs and simple ranges. Candidate-only evidence is tracked separately from the
credited rankable ledger so merely recording a candidate cannot create a false
duplicate-credit failure.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from collections import defaultdict
from pathlib import Path

RUN_RE = re.compile(r"italy-cpo-progress-2026-09-run(\d+)([a-z]*)-delta\.json$", re.IGNORECASE)
STATUSES = {"treated", "partial", "setAside", "active", "supersededAlias"}
RANGE_RE = re.compile(r"^(.*?)(\d+)\.\.(?:(.*?))?(\d+)$")
# Keep every historical field that has represented *credited/rankable* EVSE
# mappings. In particular run84 uses coveredSubpopulationsAdded.
CREDITED_MAPPING_FIELDS = (
    "newExactMappings",
    "newCoveredSubpopulations",
    "coveredSubpopulationsAdded",
)
# Candidate-only fields must never enter the credited ledger. Run148 uses
# newExactCandidateSubpopulations.
CANDIDATE_MAPPING_FIELDS = (
    "newDeterministicCandidates",
    "newExactCandidateSubpopulations",
)


def _iter_party_container(shape: str, container):
    if container is None:
        return
    if isinstance(container, list):
        for upd in container:
            if not isinstance(upd, dict):
                raise SystemExit(f"{shape}: expected object update, got {type(upd).__name__}")
            yield upd
        return
    if isinstance(container, dict):
        if container.get("partyId"):
            yield container
            return
        for bucket, value in container.items():
            if bucket in STATUSES:
                if value is None:
                    continue
                if not isinstance(value, list):
                    raise SystemExit(f"{shape}.{bucket}: expected list, got {type(value).__name__}")
                for raw in value:
                    if not isinstance(raw, dict):
                        raise SystemExit(f"{shape}.{bucket}: expected object update")
                    upd = copy.deepcopy(raw)
                    upd.setdefault("status", bucket)
                    yield upd
                continue
            if isinstance(value, list) and any(isinstance(x, dict) and x.get("partyId") for x in value):
                raise SystemExit(f"{shape}: unsupported party-update bucket {bucket!r}")
            if isinstance(value, dict) and value.get("partyId"):
                raise SystemExit(f"{shape}: unsupported party-update bucket {bucket!r}")
        return
    raise SystemExit(f"{shape}: expected list/object container, got {type(container).__name__}")


def iter_updates(delta: dict):
    for shape in (
        "changes",
        "safeStatusTransitions",
        "classificationUpdatesWithoutStatusTransition",
        "classificationUpdates",
    ):
        yield from _iter_party_container(shape, delta.get(shape))


def expand_evse_pattern(pattern: str):
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
    for key in CREDITED_MAPPING_FIELDS + CANDIDATE_MAPPING_FIELDS:
        kind = "candidate" if key in CANDIDATE_MAPPING_FIELDS else "credited"
        for mapping in update.get(key) or []:
            if not isinstance(mapping, dict):
                raise SystemExit(f"{key}: expected mapping object")
            # Historical deltas use location; newer candidate/subpopulation
            # records may use station. Preserve either in the audit report.
            location = mapping.get("location") or mapping.get("station")
            for evse_id in mapping.get("evseIds") or []:
                yield evse_id, location, key, kind
            for evse_id in expand_evse_pattern(mapping.get("evsePattern")):
                yield evse_id, location, f"{key}.evsePattern", kind


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-dir", default="docs")
    ap.add_argument("--party-id", default=None)
    ap.add_argument("--allow-through-run", type=int, default=72)
    ap.add_argument("--candidate-id", action="append", default=[])
    ap.add_argument("--candidate-before-run", type=int, default=None,
                    help="Test candidate IDs only against credited mappings in runs strictly before this run.")
    ap.add_argument("--json-output", default=None)
    args = ap.parse_args()

    observed = defaultdict(list)
    credited = defaultdict(list)
    files = []
    for path in Path(args.docs_dir).glob("italy-cpo-progress-2026-09-run*-delta.json"):
        m = RUN_RE.search(path.name)
        if m:
            files.append((int(m.group(1)), m.group(2).lower(), path))
    files.sort(key=lambda x: (x[0], x[1]))

    for run, suffix, path in files:
        delta = json.loads(path.read_text(encoding="utf-8"))
        for update in iter_updates(delta):
            party_id = update.get("partyId")
            if args.party_id and party_id != args.party_id:
                continue
            for evse_id, location, source_field, kind in iter_mapping_ids(update):
                entry = {"run": run, "runSuffix": suffix or None, "path": str(path),
                         "partyId": party_id, "location": location,
                         "sourceField": source_field, "kind": kind}
                observed[evse_id].append(entry)
                if kind == "credited":
                    credited[evse_id].append(entry)

    duplicates = {eid: occ for eid, occ in credited.items() if len(occ) > 1}
    future_violations = {eid: occ for eid, occ in duplicates.items()
                         if max(x["run"] for x in occ) > args.allow_through_run}

    def historical_credited(eid: str):
        occ = credited.get(eid, [])
        if args.candidate_before_run is not None:
            occ = [x for x in occ if x["run"] < args.candidate_before_run]
        return occ

    candidate_checks = {
        eid: {"alreadyCredited": bool(historical_credited(eid)),
              "creditedOccurrences": historical_credited(eid),
              "allObservedOccurrences": observed.get(eid, [])}
        for eid in args.candidate_id
    }
    report = {
        "partyIdFilter": args.party_id,
        "creditedMappingFields": list(CREDITED_MAPPING_FIELDS),
        "candidateMappingFields": list(CANDIDATE_MAPPING_FIELDS),
        "uniqueEvseIdsObserved": len(observed),
        "uniqueCreditedEvseIdsObserved": len(credited),
        "duplicateCreditedEvseIds": len(duplicates),
        "historicalCreditedDuplicates": duplicates,
        "allowThroughRun": args.allow_through_run,
        "futureCreditedDuplicateViolations": future_violations,
        "candidateBeforeRun": args.candidate_before_run,
        "candidateChecks": candidate_checks,
        "candidateNovelIds": [eid for eid, check in candidate_checks.items() if not check["alreadyCredited"]],
        "candidateAlreadyCreditedIds": [eid for eid, check in candidate_checks.items() if check["alreadyCredited"]],
        "result": "fail" if future_violations else "pass_with_historical_duplicates_recorded",
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        Path(args.json_output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if future_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
