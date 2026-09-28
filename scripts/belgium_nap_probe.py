#!/usr/bin/env python3
"""Probe the Belgium NAP DATEX II API without ever printing the bearer token.

Outputs:
- reports/belgium-nap-probe-summary.json
- reports/belgium-nap-locations-sample.json
- optional raw snapshot path supplied with --raw-output

The parser is intentionally defensive until the exact production payload shape
has been validated from the first authenticated run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

BASE_URL = "https://nap-be.eco-movement.com"
LOCATIONS_PATH = "/datex2/v1/locations"


def fetch_json(url: str, token: str, timeout: int = 120) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "tesla-charge-companion-data-lab/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        if "json" not in ctype.lower() and not body.lstrip().startswith((b"{", b"[")):
            raise RuntimeError(f"Unexpected content type: {ctype}")
        return json.loads(body)


def find_location_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []

    preferred = (
        "locations",
        "chargingLocations",
        "charging_locations",
        "data",
        "items",
        "results",
    )
    for key in preferred:
        value = payload.get(key)
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value[:10]):
            return value
        if isinstance(value, dict):
            nested = find_location_list(value)
            if nested:
                return nested

    # Last-resort recursive search for the largest list of dictionaries.
    candidates: list[list[dict[str, Any]]] = []
    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            dicts = [x for x in obj if isinstance(x, dict)]
            if dicts:
                candidates.append(dicts)
            for x in obj[:50]:
                walk(x)
    walk(payload)
    return max(candidates, key=len) if candidates else []


def iter_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_dicts(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from iter_dicts(x)


def count_named_nodes(payload: Any, names: set[str]) -> int:
    count = 0
    for d in iter_dicts(payload):
        for k, v in d.items():
            if k.lower() in names:
                if isinstance(v, list):
                    count += len(v)
                elif isinstance(v, dict):
                    count += 1
    return count


def collect_operator_candidates(payload: Any) -> list[dict[str, str]]:
    out = []
    seen = set()
    id_keys = {
        "operatorid", "operator_id", "cpoid", "cpo_id", "partyid", "party_id",
        "chargingstationoperatorid", "chargingstationoperator_id"
    }
    name_keys = {"operatorname", "operator_name", "cponame", "cpo_name", "name"}
    for d in iter_dicts(payload):
        lowered = {str(k).lower(): v for k, v in d.items()}
        ids = [(k, lowered[k]) for k in id_keys if k in lowered and isinstance(lowered[k], (str, int))]
        if not ids:
            continue
        ident = str(ids[0][1])
        name = ""
        for nk in name_keys:
            val = lowered.get(nk)
            if isinstance(val, str) and val.strip():
                name = val.strip()
                break
        key = (ident, name)
        if key not in seen:
            seen.add(key)
            out.append({"id": ident, "name": name})
    return out


def sanitize_sample(locations: list[dict[str, Any]], max_items: int = 3) -> list[dict[str, Any]]:
    # Payload is public infrastructure data; remove obviously auth-like fields anyway.
    forbidden = {"token", "authorization", "apikey", "api_key", "secret", "password"}
    def scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in obj.items() if str(k).lower() not in forbidden}
        if isinstance(obj, list):
            return [scrub(x) for x in obj[:20]]
        return obj
    return [scrub(x) for x in locations[:max_items]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-output", default="")
    ap.add_argument("--summary-output", default="reports/belgium-nap-probe-summary.json")
    ap.add_argument("--sample-output", default="reports/belgium-nap-locations-sample.json")
    args = ap.parse_args()

    token = os.environ.get("BELGIUM_NAP_TOKEN", "").strip()
    if not token:
        print("BELGIUM_NAP_TOKEN is required", file=sys.stderr)
        return 2

    payload = fetch_json(BASE_URL + LOCATIONS_PATH, token)
    locations = find_location_list(payload)
    operators = collect_operator_candidates(payload)

    top_level_type = type(payload).__name__
    top_level_keys = sorted(payload.keys()) if isinstance(payload, dict) else []

    summary = {
        "source": BASE_URL + LOCATIONS_PATH,
        "httpAuthenticated": True,
        "topLevelType": top_level_type,
        "topLevelKeys": top_level_keys,
        "locationCount": len(locations),
        "evseNodeCountHeuristic": count_named_nodes(payload, {"evses", "evse", "chargingpoints", "charging_points"}),
        "connectorNodeCountHeuristic": count_named_nodes(payload, {"connectors", "connector"}),
        "operatorCandidateCount": len(operators),
        "operatorCandidates": sorted(operators, key=lambda x: (x["name"], x["id"]))[:500],
        "note": "EVSE/connector/operator counts are heuristic until the exact Belgium NAP payload schema is validated from this first run."
    }

    Path(args.summary_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary_output).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.sample_output).write_text(json.dumps(sanitize_sample(locations), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.raw_output:
        Path(args.raw_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.raw_output).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
