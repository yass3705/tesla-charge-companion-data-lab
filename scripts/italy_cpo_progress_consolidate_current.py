#!/usr/bin/env python3
"""Current Italy CPO canonical consolidator.

Compatibility wrapper around ``italy_cpo_progress_consolidate.py`` that also
replays the delta shapes used by the newest Italy runtime runs:
- ``transitions``: status transitions with partyId/from/to
- ``parties``: partyId-keyed detailed updates

The underlying consolidator still performs the inventory/count fail-closed
checks and retains raw evidence. This wrapper exists so recent runtime deltas
are not silently skipped when rebuilding docs/italy-cpo-progress-2026-09.json.
"""
from __future__ import annotations

import copy

import italy_cpo_progress_consolidate as base


_original_iter_updates = base.iter_updates


def iter_updates_current(delta):
    # Replay all historical shapes supported by the base consolidator first.
    yield from _original_iter_updates(delta)

    transitions = delta.get("transitions") or []
    if transitions:
        if not isinstance(transitions, list):
            raise SystemExit("transitions: expected list")
        for raw in transitions:
            if not isinstance(raw, dict) or not raw.get("partyId"):
                raise SystemExit("transitions: malformed party transition")
            upd = copy.deepcopy(raw)
            if upd.get("to") in base.STATUSES:
                upd["status"] = upd["to"]
            yield "transitions", upd

    parties = delta.get("parties") or {}
    if parties:
        if not isinstance(parties, dict):
            raise SystemExit("parties: expected object keyed by partyId")
        for party_id, raw in parties.items():
            if not isinstance(party_id, str) or not party_id:
                raise SystemExit("parties: invalid partyId key")
            if not isinstance(raw, dict):
                raise SystemExit(f"parties.{party_id}: expected object")
            upd = copy.deepcopy(raw)
            embedded = upd.get("partyId")
            if embedded and embedded != party_id:
                raise SystemExit(
                    f"parties.{party_id}: embedded partyId mismatch {embedded!r}"
                )
            upd["partyId"] = party_id
            yield "parties", upd


base.iter_updates = iter_updates_current

if __name__ == "__main__":
    base.main()
