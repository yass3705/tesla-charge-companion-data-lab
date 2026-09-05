#!/usr/bin/env python3
"""Build a fail-closed inventory of Italian CPOs not yet covered by a published V9 treatment.

The script reads the latest Italy V9 consolidated candidate and groups the PUN-backed
EVSE inventory by partyId/operator label. It does not infer tariff applicability.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

TREATED_PARTY_IDS = {
    "ACE": "ACEA classified fail-closed",
    "F2X": "Free To X direct candidate published",
    "REP": "Repower direct candidate published",
    "REV": "Repower direct candidate published",
}

TREATED_LABEL_TOKENS = {
    "EWIVA": "Ewiva POS candidate published",
    "NEOGY": "Neogy candidate published",
    "ALPERIA": "Alperia EasyCharge candidate published",
    "REPOWER": "Repower direct candidate published",
    "FREE TO X": "Free To X direct candidate published",
}

PAUSED_LABEL_TOKENS = {"ATLANTE": "paused_by_user"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(path.read_text(encoding="utf-8"))


def iter_evses(doc):
    if isinstance(doc, dict):
        for key in ("evses", "stations", "items", "data"):
            value = doc.get(key)
            if isinstance(value, list):
                if key == "stations":
                    for station in value:
                        if not isinstance(station, dict):
                            continue
                        station_evses = station.get("evses") or station.get("EVSEs") or []
                        if isinstance(station_evses, list):
                            for evse in station_evses:
                                if isinstance(evse, dict):
                                    merged = dict(evse)
                                    merged.setdefault("stationId", station.get("stationId") or station.get("id"))
                                    merged.setdefault("operator", station.get("operator"))
                                    yield merged
                    return
                for row in value:
                    if isinstance(row, dict):
                        yield row
                return
    if isinstance(doc, list):
        for row in doc:
            if isinstance(row, dict):
                yield row


def label_for(e):
    for key in ("operator", "operatorName", "cpo", "cpoName", "network", "provider"):
        value = e.get(key)
        if isinstance(value, dict):
            value = value.get("name") or value.get("legalName")
        if value:
            return str(value).strip()
    return "UNKNOWN"


def party_for(e):
    value = e.get("partyId") or e.get("party_id")
    if value:
        return str(value).strip().upper()
    evse_id = str(e.get("evseId") or e.get("evse_id") or "").strip().upper()
    if evse_id.startswith("IT*"):
        parts = evse_id.split("*")
        if len(parts) > 1:
            return parts[1]
    return "UNKNOWN"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    doc = load(Path(args.input))

    groups = defaultdict(lambda: {"evse": 0, "stations": set(), "labels": Counter()})
    total = 0
    for e in iter_evses(doc):
        total += 1
        party = party_for(e)
        label = label_for(e)
        g = groups[party]
        g["evse"] += 1
        sid = e.get("stationId") or e.get("station_id") or e.get("locationId") or e.get("location_id")
        if sid:
            g["stations"].add(str(sid))
        g["labels"][label] += 1

    rows = []
    for party, g in groups.items():
        labels = dict(g["labels"].most_common())
        label_text = " | ".join(labels).upper()
        status = "remaining"
        reason = None
        if party in TREATED_PARTY_IDS:
            status = "treated"
            reason = TREATED_PARTY_IDS[party]
        else:
            for token, why in TREATED_LABEL_TOKENS.items():
                if token in label_text:
                    status = "treated"
                    reason = why
                    break
            if status == "remaining":
                for token, why in PAUSED_LABEL_TOKENS.items():
                    if token in label_text:
                        status = "paused"
                        reason = why
                        break
        rows.append({
            "partyId": party,
            "evse": g["evse"],
            "stations": len(g["stations"]),
            "operatorLabels": labels,
            "status": status,
            "reason": reason,
        })

    rows.sort(key=lambda x: (-x["evse"], x["partyId"]))
    payload = {
        "schemaVersion": 1,
        "dataset": "italy-v9-remaining-cpo-inventory",
        "generatedAt": now_iso(),
        "sourceDataset": doc.get("dataset") if isinstance(doc, dict) else None,
        "totalObservedEvse": total,
        "counts": {
            "partyIds": len(rows),
            "remainingPartyIds": sum(r["status"] == "remaining" for r in rows),
            "treatedPartyIds": sum(r["status"] == "treated" for r in rows),
            "pausedPartyIds": sum(r["status"] == "paused" for r in rows),
            "remainingEvse": sum(r["evse"] for r in rows if r["status"] == "remaining"),
        },
        "cpos": rows,
        "policy": {
            "tariffPriority": ["network_wide_predefined", "station_or_evse_specific"],
            "tariffClassification": "not_inferred_by_inventory_script",
            "atlantePaused": True,
            "failClosed": True,
        },
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
