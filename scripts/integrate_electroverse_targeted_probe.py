#!/usr/bin/env python3
"""Publish two uniquely verified live Electroverse locations to the pinned cache."""
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/electroverse/targeted-station-probe.json"
CACHE = ROOT / "data/electroverse/tariff_cache"
MAPPING = ROOT / "data/electroverse/irve_location_mapping.json"
NATIONAL = ROOT / "data/national/france-irve-static-v9/all.json.gz"
SOURCE_RUN = "https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/" + os.environ.get("GITHUB_RUN_ID", "local")
TARGETS = {"electra-bois-d-arcy": "FRELCP12954082", "lidl-dole": "FRLDLPLFR3233EVCP"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    report = read(REPORT)
    if report.get("errors") or {item["id"] for item in report.get("targets", [])} != set(TARGETS):
        raise ValueError("targeted probe is incomplete")
    with gzip.open(NATIONAL, "rt", encoding="utf-8") as stream:
        national = {row[0]: row for row in json.load(stream) if row[0] in TARGETS.values()}
    mapping = read(MAPPING)
    manifest = read(CACHE / "manifest.json")
    mapped_ids = {row["irveStationId"] for row in mapping["mappings"]}
    mapped_pks = {str(row["electroverseLocationPk"]) for row in mapping["mappings"]}
    changed = []
    for target in report["targets"]:
        sid = TARGETS[target["id"]]
        candidates = [row for row in target["nearby"] if row["distanceM"] <= 15]
        if len(candidates) != 1:
            raise ValueError(f"{sid}: not exactly one location within 15m")
        candidate = candidates[0]
        pk = str(candidate["pk"])
        if sid in mapped_ids or pk in mapped_pks or candidate.get("mapping"):
            raise ValueError(f"{sid}: mapping already exists")
        source = national[sid]
        if candidate["operator"].lower() not in ("electra", "lidl"):
            raise ValueError(f"{sid}: unexpected operator")
        if target["id"] == "electra-bois-d-arcy":
            if candidate["operator"].lower() != "electra" or candidate["name"] != "Bois-d'Arcy - E.Leclerc":
                raise ValueError("Electra station identity differs")
            configs = [row for row in source[8] if row[2] == "DC"]
        else:
            if candidate["operator"].lower() != "lidl":
                raise ValueError("Lidl station identity differs")
            configs = source[8]
        pdcs = sorted({pdc for config in configs for pdc in config[6]})
        evses = candidate["tariff"]["evses"]
        if target["id"] == "electra-bois-d-arcy":
            powers = sorted(connector["kilowatts"] for evse in evses for connector in evse["connectors"])
            if len(evses) != 19 or powers != [100] + [400] * 12 + [600] * 6:
                raise ValueError("Electra connector inventory differs")
        elif len(evses) != 2 or {evse["physicalReference"].replace("*", "") for evse in evses} != set(pdcs):
            raise ValueError("Lidl physical references differ from IRVE PDCs")
        if not all(connector.get("priceComponents") for evse in evses for connector in evse["connectors"]):
            raise ValueError(f"{sid}: missing Electroverse price component")
        mapping["mappings"].append({
            "irveStationId": sid, "irvePdcIds": pdcs, "electroverseLocationPk": pk,
            "matchMethod": "targeted_live_location_and_connector_verification_2026_10_06", "confidence": "high",
            "evidence": {"distanceM": candidate["distanceM"], "uniqueCandidateWithin100m": True,
                         "operatorVerified": True, "connectorInventoryVerified": True,
                         "sourceRun": SOURCE_RUN,
                         "rule": "Live Electroverse location <=15m; operator and connector inventory agree with current national/first-party station"},
            "irve": {"lat": source[3], "lon": source[4], "name": source[1],
                     "address": source[2], "operator": source[5], "brand": source[10]},
            "electroverse": {"lat": candidate["coordinates"]["latitude"],
                             "lon": candidate["coordinates"]["longitude"],
                             "name": candidate["name"], "address": candidate["address"],
                             "operator": candidate["operator"]},
        })
        tariff = {"chargingLocationPk": pk, "evses": evses}
        digest = hashlib.sha256(json.dumps(tariff, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        shard = hashlib.sha1(pk.encode()).digest()[0] % 128
        shard_path = CACHE / f"shard-{shard:03d}.json"
        shard_data = read(shard_path)
        if pk in shard_data["stations"]:
            raise ValueError(f"{sid}: tariff already cached")
        shard_data["stations"][pk] = {
            "electroverseLocationPk": pk, "irveStationId": sid, "irvePdcIds": pdcs,
            "matchConfidence": "high", "tariffHash": digest,
            "fetchedAt": report["generatedAt"], "fetchMode": "targeted_live",
            "pagedPages": None, "tariff": tariff,
        }
        shard_data["generatedAt"] = report["generatedAt"]
        write(shard_path, shard_data)
        for item in manifest["shards"]:
            if item["file"] == shard_path.name:
                item["count"] = len(shard_data["stations"])
                item["sizeBytes"] = shard_path.stat().st_size
        changed.append({"stationId": sid, "pk": pk, "shard": shard_path.name})
    mapping["mappings"].sort(key=lambda row: (row["irveStationId"], str(row["electroverseLocationPk"])))
    mapping["generatedAt"] = report["generatedAt"]
    mapping["counts"]["mappings"] = len(mapping["mappings"])
    mapping["counts"]["unmappedIrveStations"] = mapping["counts"]["irveStations"] - len(mapping["mappings"])
    write(MAPPING, mapping)
    manifest["generatedAt"] = report["generatedAt"]
    manifest["totalStations"] = sum(item["count"] for item in manifest["shards"])
    manifest["maxShardBytes"] = max(item["sizeBytes"] for item in manifest["shards"])
    manifest["lastTargetedRefresh"] = {"runAt": report["generatedAt"], "stations": list(TARGETS.values()), "sourceRun": SOURCE_RUN}
    write(CACHE / "manifest.json", manifest)
    print(json.dumps({"updated": changed, "cacheStations": manifest["totalStations"]}))


if __name__ == "__main__":
    main()
