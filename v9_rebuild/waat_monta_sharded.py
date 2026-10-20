#!/usr/bin/env python3
"""Execute and merge the four preserved WAAT/Monta browser shards off checkout."""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from v9_rebuild.electroverse import ROOT
from v9_rebuild.cwd_script import METHODS, validate_output as validate_inventory

SHARD_COUNT = 4
INPUT = Path("data/national/waat_direct_stations_france.json.gz")
OUTPUT = Path("data/national/waat_monta_direct_tariffs_france.json.gz")
REPORT = Path("data/reports/waat_monta_national_tariffs_report.json")
PROVENANCE = Path("data/reports/waat_monta_shards_provenance.json")


def read_gzip(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("WAAT/Monta gzip payload is not an object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shard_path(index: int) -> Path:
    return Path(f"data/shards/waat_monta_shard_{index}.json.gz")


def inventory_stations(out: Path) -> list[dict]:
    inventory = read_gzip(out / INPUT)
    if (inventory.get("dataset") != "waat-direct-stations-france"
            or inventory.get("scope", {}).get("operatorPrefix") != "FR*WA2"
            or not isinstance(inventory.get("stations"), list)):
        raise ValueError("WAAT/Monta source inventory invalid")
    return [station for station in inventory["stations"]
            if isinstance(station.get("coordinates"), list) and len(station["coordinates"]) >= 2]


def validate_shards(out: Path) -> tuple[list[dict], list[dict]]:
    source = inventory_stations(out)
    shards = []
    seen = set()
    for index in range(SHARD_COUNT):
        shard = read_gzip(out / shard_path(index))
        expected = source[index::SHARD_COUNT]
        rows = shard.get("stations")
        if (shard.get("schemaVersion") != "2.0.0"
                or shard.get("dataset") != "waat-monta-direct-tariffs-shard"
                or shard.get("operator") != "WAAT" or shard.get("country") != "FR"
                or shard.get("shardIndex") != index or shard.get("shardCount") != SHARD_COUNT
                or shard.get("sourceInventoryStations") != len(source)
                or not isinstance(rows, list) or len(rows) != len(expected)
                or [row.get("stationIdNormalized") for row in rows] != [row.get("stationIdNormalized") for row in expected]):
            raise ValueError(f"WAAT/Monta shard {index} incomplete or wrong source")
        for row in rows:
            sid = row.get("stationIdNormalized")
            if not sid or sid in seen or row.get("mapHttpStatus") != 200 or row.get("mapError"):
                raise ValueError(f"WAAT/Monta shard {index} map or station identity invalid")
            seen.add(sid)
            for config in row.get("integrationConfigs") or []:
                if config.get("rankable") and (config.get("kind") not in {"AC", "DC"}
                                                or not isinstance(config.get("directEurPerKwh"), (int, float))
                                                or config["directEurPerKwh"] <= 0
                                                or config.get("blockingReason")):
                    raise ValueError("WAAT/Monta rankable configuration incomplete")
        shards.append(shard)
    return source, shards


def merge(out: Path) -> None:
    source, shards = validate_shards(out)
    stations = sorted((row for shard in shards for row in shard["stations"]), key=lambda row: row["stationIdNormalized"])
    groups = {group["montaGroupId"]: group for station in stations for group in station.get("montaGroups") or []}
    rankable_groups = {group["montaGroupId"]: group for station in stations for group in station.get("rankableGroups") or [] if group.get("rankable")}
    safe_configs = [config for station in stations for config in station.get("integrationConfigs") or [] if config.get("rankable")]
    unresolved_configs = [config for station in stations for config in station.get("integrationConfigs") or [] if not config.get("rankable")]
    distribution = collections.Counter(f"{float(group['directEurPerKwh']):.3f}" for group in rankable_groups.values())
    counts = {"inventoryStations": len(source), "queriedStations": len(stations),
              "mapHttp200": sum(row.get("mapHttpStatus") == 200 for row in stations), "mapErrors": 0,
              "stationsWithMontaGroup": sum(bool(row.get("montaGroups")) for row in stations),
              "rankableStations": sum(bool(row.get("rankableDirect")) for row in stations),
              "unresolvedStations": sum(not row.get("rankableDirect") for row in stations),
              "uniqueMontaGroups": len(groups), "rankableMontaGroups": len(rankable_groups),
              "rankablePhysicalConfigs": len(safe_configs), "unresolvedPhysicalConfigs": len(unresolved_configs),
              "priceRangeGroups": sum(group.get("blockingReason") == "price_range" for group in groups.values()),
              "dynamicGroups": sum(group.get("blockingReason") == "dynamic_pricing" for group in groups.values()),
              "zeroPriceGroups": sum(group.get("blockingReason") == "zero_price_not_auto_ranked" for group in groups.values()),
              "ambiguousConnectorGroups": sum(group.get("blockingReason") == "ambiguous_connector_kind" for group in groups.values())}
    now = datetime.now(timezone.utc).isoformat()
    payload = {"schemaVersion": "2.0.0", "dataset": "waat-monta-direct-tariffs-france", "operator": "WAAT", "country": "FR",
               "generatedAt": now,
               "source": {"type": "monta-public-web-map-guest-browser-sharded", "mapUrl": "https://maps.monta.app/", "apiBase": "https://api.monta.app",
                          "note": "Four independent browser guest sessions; authorization is never persisted."},
               "scope": {"directCpoOnly": True, "operatorPrefix": "FR*WA2", "roamingIncluded": False,
                         "stationSpecificPricing": True, "unresolvedCasesNeverRankable": True,
                         "zeroPriceAutoRanked": False, "dynamicPricingAutoRanked": False,
                         "rangePricingAutoRanked": False, "ambiguousConnectorGroupsAutoRanked": False},
               "counts": counts, "tariffDistribution": dict(sorted(distribution.items())), "stations": stations}
    examples = [{"stationId": row["stationIdNormalized"], "name": row.get("stationName"),
                 "address": row.get("address"), "configs": [config for config in row.get("integrationConfigs") or [] if config.get("rankable")]}
                for row in stations if any(config.get("rankable") for config in row.get("integrationConfigs") or [])][:20]
    report = {"generatedAt": now, "counts": counts, "tariffDistribution": payload["tariffDistribution"], "examples": examples}
    (out / OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    (out / REPORT).parent.mkdir(parents=True, exist_ok=True)
    (out / OUTPUT).write_bytes(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), mtime=0))
    (out / REPORT).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    provenance = {"inventorySha256": sha(out / INPUT), "shardSha256": {str(index): sha(out / shard_path(index)) for index in range(SHARD_COUNT)},
                  "outputSha256": sha(out / OUTPUT)}
    (out / PROVENANCE).write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


def validate_output(out: Path) -> dict:
    source, shards = validate_shards(out)
    payload = read_gzip(out / OUTPUT)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    provenance = json.loads((out / PROVENANCE).read_text(encoding="utf-8"))
    expected_ids = sorted(row["stationIdNormalized"] for shard in shards for row in shard["stations"])
    if (payload.get("dataset") != "waat-monta-direct-tariffs-france"
            or payload.get("country") != "FR" or payload.get("operator") != "WAAT"
            or payload.get("scope", {}).get("roamingIncluded") is not False
            or [row.get("stationIdNormalized") for row in payload.get("stations") or []] != expected_ids
            or payload.get("counts", {}).get("inventoryStations") != len(source)
            or payload.get("counts", {}).get("queriedStations") != len(source)
            or report.get("counts") != payload.get("counts")
            or provenance.get("inventorySha256") != sha(out / INPUT)
            or provenance.get("shardSha256") != {str(index): sha(out / shard_path(index)) for index in range(SHARD_COUNT)}
            or provenance.get("outputSha256") != sha(out / OUTPUT)):
        raise ValueError("WAAT/Monta complete national artifact invalid")
    return payload


def run(out: Path, inventory_state: Path, *, fixture_map: Path | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("WAAT/Monta output must be outside checkout")
    validate_inventory(inventory_state, "waat_inventory")
    (out / INPUT).parent.mkdir(parents=True, exist_ok=True)
    incoming = inventory_state / METHODS["waat_inventory"][1]
    if (out / INPUT).is_file() and sha(out / INPUT) != sha(incoming):
        for relative in [*(shard_path(index) for index in range(SHARD_COUNT)), OUTPUT, REPORT, PROVENANCE]:
            (out / relative).unlink(missing_ok=True)
    shutil.copy2(incoming, out / INPUT)
    for index in range(SHARD_COUNT):
        target = out / shard_path(index)
        if target.is_file():
            try:
                validate_shards_partial(out, index)
                continue
            except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                target.unlink()
        env = os.environ.copy()
        env.update({"WAAT_SHARD_COUNT": str(SHARD_COUNT), "WAAT_SHARD_INDEX": str(index), "WAAT_CONCURRENCY": "2"})
        if fixture_map is not None:
            env["WAAT_OFFLINE_FIXTURE"] = str(fixture_map)
        result = runner(["node", str(ROOT / "scripts/waat_monta_shard.mjs")], cwd=out, env=env,
                        capture_output=True, text=True, timeout=1800, check=False)
        if result.returncode:
            raise RuntimeError(f"Historical WAAT/Monta shard {index} failed")
        validate_shards_partial(out, index)
    merge(out)
    validate_output(out)


def validate_shards_partial(out: Path, index: int) -> None:
    source = inventory_stations(out)
    shard = read_gzip(out / shard_path(index))
    expected = source[index::SHARD_COUNT]
    rows = shard.get("stations")
    if (shard.get("shardIndex") != index or shard.get("shardCount") != SHARD_COUNT
            or shard.get("sourceInventoryStations") != len(source)
            or not isinstance(rows, list) or len(rows) != len(expected)
            or [row.get("stationIdNormalized") for row in rows] != [row.get("stationIdNormalized") for row in expected]
            or any(row.get("mapHttpStatus") != 200 or row.get("mapError") for row in rows)):
        raise ValueError(f"WAAT/Monta shard {index} partial state invalid")


def validate_checkpoint(out: Path) -> None:
    inventory_stations(out)
    for index in range(SHARD_COUNT):
        if (out / shard_path(index)).is_file():
            validate_shards_partial(out, index)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.inventory)


if __name__ == "__main__":
    main()
