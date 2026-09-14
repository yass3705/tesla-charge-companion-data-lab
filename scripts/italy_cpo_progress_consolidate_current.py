#!/usr/bin/env python3
"""Current Italy CPO canonical consolidator.

Compatibility wrapper around ``italy_cpo_progress_consolidate.py`` that replays
all delta shapes currently present in the Italy runtime ledger, including newer
party-scoped research records that the historical consolidator does not know.

Supported compatibility shapes in addition to the base consolidator:
- ``transitions``: status transitions with partyId/from/to
- ``parties``: partyId-keyed (or list-form) detailed updates
- ``updates``: partyId-keyed (or list-form) detailed updates
- ``investigations``: per-party or grouped research evidence
- ``partyIdGroup``: normalized to ``partyIds`` so grouped evidence is attached
  to every referenced canonical party without inventing a status transition

The underlying consolidator still performs inventory/count fail-closed checks
and retains raw evidence. Unsupported/malformed party-looking data fails closed
instead of being silently dropped.
"""
from __future__ import annotations

import copy

import italy_cpo_progress_consolidate as base


_original_iter_updates = base.iter_updates


def _normalize_group(update, *, shape):
    upd = copy.deepcopy(update)
    party_id_group = upd.pop("partyIdGroup", None)
    if party_id_group is not None:
        if upd.get("partyId") or upd.get("partyIds"):
            raise SystemExit(f"{shape}: ambiguous partyIdGroup with partyId/partyIds")
        if not isinstance(party_id_group, list) or not party_id_group or not all(
            isinstance(x, str) and x for x in party_id_group
        ):
            raise SystemExit(f"{shape}: malformed partyIdGroup")
        upd["partyIds"] = party_id_group
    return upd


def _iter_keyed_or_list(shape, container):
    if container is None or container == {} or container == []:
        return

    if isinstance(container, list):
        for raw in container:
            if not isinstance(raw, dict):
                raise SystemExit(f"{shape}: expected object update")
            upd = _normalize_group(raw, shape=shape)
            if not upd.get("partyId") and not upd.get("partyIds"):
                raise SystemExit(f"{shape}: update missing partyId/partyIds")
            yield shape, upd
        return

    if isinstance(container, dict):
        # Defensive compatibility: accept a single embedded party update.
        if container.get("partyId") or container.get("partyIds") or container.get("partyIdGroup"):
            upd = _normalize_group(container, shape=shape)
            yield shape, upd
            return

        # Normal keyed form: {"HER": {...}, "TSL": {...}}.
        for party_id, raw in container.items():
            if not isinstance(party_id, str) or not party_id:
                raise SystemExit(f"{shape}: invalid partyId key")
            if not isinstance(raw, dict):
                raise SystemExit(f"{shape}.{party_id}: expected object")
            upd = _normalize_group(raw, shape=f"{shape}.{party_id}")
            embedded = upd.get("partyId")
            if embedded and embedded != party_id:
                raise SystemExit(
                    f"{shape}.{party_id}: embedded partyId mismatch {embedded!r}"
                )
            if upd.get("partyIds"):
                raise SystemExit(f"{shape}.{party_id}: grouped update inside keyed party entry")
            upd["partyId"] = party_id
            yield shape, upd
        return

    raise SystemExit(f"{shape}: expected list/object container")


def _iter_investigations(container):
    if container is None or container == []:
        return
    if not isinstance(container, list):
        raise SystemExit("investigations: expected list")

    for raw in container:
        if not isinstance(raw, dict):
            raise SystemExit("investigations: expected object record")
        normalized = _normalize_group(raw, shape="investigations")
        party_id = normalized.get("partyId")
        party_ids = normalized.get("partyIds")
        if not party_id and not party_ids:
            raise SystemExit("investigations: record missing partyId/partyIds")

        # Preserve the full investigation as nested evidence while copying only
        # canonical-safe summary fields. This prevents a research-only field
        # such as `result=no_promotion` from overwriting canonical status/model.
        upd = {
            "investigationEvidenceLatest": copy.deepcopy(normalized),
        }
        for key in (
            "partyId",
            "partyIds",
            "priority",
            "blockage",
            "blocker",
            "resumeCondition",
            "confidence",
            "lastInvestigated",
        ):
            if key in normalized:
                upd[key] = copy.deepcopy(normalized[key])
        yield "investigations", upd


def iter_updates_current(delta):
    # Replay all historical shapes supported by the base consolidator first,
    # while fixing grouped `partyIdGroup` records found in newer `changes`.
    for shape, raw in _original_iter_updates(delta):
        yield shape, _normalize_group(raw, shape=shape)

    transitions = delta.get("transitions") or []
    if transitions:
        if not isinstance(transitions, list):
            raise SystemExit("transitions: expected list")
        for raw in transitions:
            if not isinstance(raw, dict) or not raw.get("partyId"):
                raise SystemExit("transitions: malformed party transition")
            upd = _normalize_group(raw, shape="transitions")
            if upd.get("to") in base.STATUSES:
                upd["status"] = upd["to"]
            yield "transitions", upd

    yield from _iter_keyed_or_list("parties", delta.get("parties"))
    yield from _iter_keyed_or_list("updates", delta.get("updates"))
    yield from _iter_investigations(delta.get("investigations"))


base.iter_updates = iter_updates_current

if __name__ == "__main__":
    base.main()
