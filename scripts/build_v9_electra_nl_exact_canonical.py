#!/usr/bin/env python3
"""Preserve archived NL Electra Direct offers on proven DOT-NL connectors.

This is a replay of the archived exact crosswalk. Tariff components remain raw:
the source archive records omitted congestion components, so no price is
calculated or promoted by this builder.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v9_rebuild.canonical import key, normalize_netherlands_dotnl, validate


SOURCE_ID = "NL:electra_direct_exact"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalize(national: dict, overlay: dict, *, national_sha: str, overlay_sha: str) -> dict:
    if (national.get("schemaVersion") != "1.0.0" or not isinstance(national.get("stations"), list) or
            overlay.get("schemaVersion") != 1 or overlay.get("dataset") != "nl-electra-direct-payg-exact-overlay" or
            overlay.get("country") != "NL" or overlay.get("partyId") != "ELD" or
            not isinstance(overlay.get("tariffs"), dict) or not isinstance(overlay.get("matches"), list) or
            overlay.get("policy", {}).get("exactEvseAndUniqueConnectorMatchOnly") is not True or
            overlay.get("policy", {}).get("directCpoOnly") is not True):
        raise ValueError("Archived Electra NL identity or proof policy invalid")
    stations = {}
    for station in national["stations"]:
        if station.get("countryCode") == "NL" and station.get("partyId") == "ELD":
            stations.setdefault(station.get("stationId"), []).append(station)
    selected, matches, seen = {}, [], set()
    for row in overlay["matches"]:
        identity = tuple(row.get(name) for name in ("stationId", "evseId", "connectorId", "tariffKey"))
        if (not all(isinstance(value, str) and value for value in identity) or identity in seen or
                row.get("match") != "exact_evse_unique_connector" or identity[3] not in overlay["tariffs"]):
            raise ValueError("Archived Electra NL match invalid or duplicate")
        seen.add(identity)
        station_rows = stations.get(identity[0], [])
        if len(station_rows) != 1:
            raise ValueError("Archived Electra NL station is not unique")
        station = station_rows[0]
        evses = [evse for evse in station["evses"] if evse.get("evseId") == identity[1]]
        if len(evses) != 1:
            raise ValueError("Archived Electra NL EVSE is not unique")
        connectors = [connector for connector in evses[0]["connectors"]
                      if connector.get("id") == identity[2]]
        if len(connectors) != 1 or identity[3] not in (connectors[0].get("tariffKeys") or []):
            raise ValueError("Archived Electra NL connector/tariff link is not exact")
        selected[identity[0]] = station
        matches.append((row, station, evses[0], connectors[0]))
    if not matches:
        raise ValueError("Archived Electra NL exact proof has no links")
    # Reuse the existing national normalizer on only the proven stations. Its
    # IDs are identical to the full national dataset's IDs by construction.
    subset = {"schemaVersion": "1.0.0", "stations": list(selected.values()), "tariffs": {},
              "dataset": national.get("dataset"), "generatedAt": national.get("generatedAt")}
    result = normalize_netherlands_dotnl(subset, artifact_sha256=national_sha)
    result["source"] = {"id": SOURCE_ID, "artifactSha256": sha((national_sha + overlay_sha).encode()),
                        "rawDataset": overlay["dataset"], "nationalSha256": national_sha,
                        "overlaySha256": overlay_sha, "generatedAt": overlay.get("generatedAt")}
    by_connector = {(row["evseId"], row["sourceConnectorId"]): row for row in result["connectors"]}
    for row, station, evse, connector in matches:
        evse_id = key("NL", "NL:dotnl_static", "evse",
                      [station["stationId"], evse["uid"], evse["evseId"]])
        target = by_connector.get((evse_id, connector["id"]))
        if target is None:
            raise ValueError("Normalized Electra NL connector lost")
        tariff_key = row["tariffKey"]
        tariff = overlay["tariffs"][tariff_key]
        if (tariff.get("tariffKey") != tariff_key or tariff.get("countryCode") != "NL" or
                tariff.get("partyId") != "ELD"):
            raise ValueError("Archived Electra NL tariff identity invalid")
        result["offers"].append({"id": key("NL", SOURCE_ID, "offer", list(row.get(name) for name in
                               ("stationId", "evseId", "connectorId", "tariffKey"))),
                                 "channel": "Direct", "scope": {"evseId": evse_id, "connectorId": target["id"]},
                                 "sourceTariffKey": tariff_key, "sourceConnectorId": row.get("sourceConnectorId"),
                                 "proof": "archived_exact_evse_unique_connector",
                                 "rawOffer": tariff, "calculationStatus": "not_evaluated"})
    result["offers"].sort(key=lambda offer: offer["id"])
    validate(result)
    return result


def build(national_path: Path, overlay_path: Path, output: Path) -> dict:
    output = output.resolve()
    root = Path(__file__).resolve().parents[1]
    if output == root or root in output.parents:
        raise ValueError("Canonical output must stay outside checkout")
    national_raw, overlay_raw = national_path.read_bytes(), overlay_path.read_bytes()
    national = json.loads(gzip.decompress(national_raw))
    overlay = json.loads(overlay_raw)
    result = normalize(national, overlay, national_sha=sha(national_raw), overlay_sha=sha(overlay_raw))
    raw = (json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("Existing Electra NL canonical artifact differs")
    if not output.exists():
        output.write_bytes(raw)
    return {"source": SOURCE_ID, "path": str(output), "sha256": sha(raw),
            "offers": len(result["offers"]), "stations": len(result["stations"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--national", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.national, args.overlay, args.out), ensure_ascii=False))
