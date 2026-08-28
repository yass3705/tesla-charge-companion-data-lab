#!/usr/bin/env python3
"""Build a persistent AFIR service-state snapshot from normalized dynamic feeds.

Provider semantics observed in live Mobilithek data:
- Qwello publishes a near-full snapshot: replace its state each run.
- eRound publishes small deltas: merge updates into the previous known state.

Never infer a state for an unseen eRound point. Unknown remains unknown until an
explicit source event is observed. This artifact is staging-only.
"""
from __future__ import annotations

import argparse
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

PROVIDER_MODE = {"qwello": "snapshot", "eround": "delta"}


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_gz(path: Path | None):
    if not path or not path.is_file():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_gz(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def key(row: dict):
    return f"{row.get('provider')}|{row.get('sourcePointId')}"


def compact_row(row: dict, observed_at: str, previous: dict | None = None):
    first = (previous or {}).get("stateFirstObservedAt") or observed_at
    return {
        "provider": row.get("provider"),
        "sourcePointId": row.get("sourcePointId"),
        "staticSiteId": row.get("staticSiteId"),
        "staticStationId": row.get("staticStationId"),
        "evseIds": row.get("evseIds") or [],
        "rawStatus": row.get("rawStatus"),
        "stationIsAvailable": row.get("stationIsAvailable"),
        "serviceState": row.get("serviceState") or "unknown",
        "sourceLastUpdated": row.get("lastUpdated"),
        "stateFirstObservedAt": first,
        "stateLastObservedAt": observed_at,
        "dynamicTariffUpdates": row.get("dynamicTariffUpdates") or [],
    }


def build(current: dict, previous: dict | None):
    now = utc_now()
    prev_points = (previous or {}).get("points") or []
    prev_by_provider = {}
    for row in prev_points:
        prev_by_provider.setdefault(row.get("provider"), {})[key(row)] = row

    current_by_provider = {}
    for row in current.get("points") or []:
        current_by_provider.setdefault(row.get("provider"), {})[key(row)] = row

    output_points = []
    provider_stats = {}
    static_summary = current.get("staticSummary") or {}

    for provider, mode in PROVIDER_MODE.items():
        prev = prev_by_provider.get(provider, {})
        cur = current_by_provider.get(provider, {})
        if mode == "snapshot":
            merged = {k: compact_row(v, now, prev.get(k)) for k, v in cur.items()}
        else:
            merged = dict(prev)
            for k, v in cur.items():
                merged[k] = compact_row(v, now, prev.get(k))
        rows = list(merged.values())
        output_points.extend(rows)
        known_static = (static_summary.get(provider) or {}).get("staticPoints") or 0
        state_counts = {}
        for row in rows:
            state_counts[row["serviceState"]] = state_counts.get(row["serviceState"], 0) + 1
        provider_stats[provider] = {
            "mode": mode,
            "currentEvents": len(cur),
            "previousKnownPoints": len(prev),
            "knownPointsAfterMerge": len(rows),
            "staticPoints": known_static,
            "knownCoveragePct": round(100 * len(rows) / max(1, known_static), 2),
            "serviceStateDistribution": state_counts,
        }

    result = {
        "schemaVersion": "0.1.0",
        "dataset": "germany-afir-dynamic-persistent-state",
        "generatedAt": now,
        "countryCode": "DE",
        "scope": {
            "stagedOnly": True,
            "publishesToTcc": False,
            "tariffsRankable": False,
            "unknownIsNeverAssumedOperational": True,
            "providerModes": PROVIDER_MODE,
        },
        "sourceDynamicGeneratedAt": current.get("generatedAt"),
        "previousStateGeneratedAt": (previous or {}).get("generatedAt"),
        "staticSummary": static_summary,
        "providerStats": provider_stats,
        "points": sorted(output_points, key=lambda x: (x.get("provider") or "", x.get("sourcePointId") or "")),
    }
    result["stats"] = {
        "knownPoints": len(result["points"]),
        "operational": sum(x.get("serviceState") == "operational" for x in result["points"]),
        "outOfService": sum(x.get("serviceState") == "out_of_service" for x in result["points"]),
        "unknown": sum(x.get("serviceState") == "unknown" for x in result["points"]),
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, default=Path("data/germany/afir_open_dynamic_normalized.json.gz"))
    parser.add_argument("--previous", type=Path, default=Path("data/germany/previous/afir_dynamic_state.json.gz"))
    parser.add_argument("--output", type=Path, default=Path("data/germany/afir_dynamic_state.json.gz"))
    args = parser.parse_args()
    current = load_gz(args.current)
    if current is None:
        raise SystemExit(f"missing current normalized dynamic artifact: {args.current}")
    previous = load_gz(args.previous)
    result = build(current, previous)
    save_gz(args.output, result)
    print("TCC_AFIR_DYNAMIC_STATE=" + json.dumps(result["stats"], sort_keys=True))
    for provider, stats in result["providerStats"].items():
        print("TCC_AFIR_DYNAMIC_STATE_PROVIDER=" + json.dumps({"provider": provider, **stats}, sort_keys=True))


if __name__ == "__main__":
    main()
