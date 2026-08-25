#!/usr/bin/env python3
"""Remove explicitly modeled regional networks from the Freshmile CPO umbrella.

Freshmile's AFIREV CPO identity FR*FR1 is also used for stations belonging to
regional/territorial networks. The generic Freshmile-direct dataset must not
silently absorb those networks because TCC models their tariffs separately.

This post-processor is deliberately conservative: it only excludes identities
listed in config/freshmile_regional_network_exclusions.json. It does not infer
that a municipality, public authority, hotel, retailer or private site is a
regional network merely from its owner type.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_DATASET = Path("data/national/freshmile_direct_stations_france.json.gz")
DEFAULT_CONFIG = Path("config/freshmile_regional_network_exclusions.json")


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} does not contain a JSON object")
    return payload


def load_gzip_json(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} does not contain a JSON object")
    return payload


def write_gzip_json(path: Path, payload: dict[str, Any]) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def validate_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    networks = config.get("networks")
    if not isinstance(networks, list) or not networks:
        raise RuntimeError("regional exclusion config has no networks")
    seen: set[str] = set()
    for network in networks:
        if not isinstance(network, dict):
            raise RuntimeError("regional exclusion network must be an object")
        key = normalize(network.get("key"))
        if not key or key in seen:
            raise RuntimeError(f"invalid or duplicate regional network key: {key!r}")
        seen.add(key)
        source_object = str(network.get("sourceObject") or "").strip()
        if not source_object:
            raise RuntimeError(f"regional network {key} has no sourceObject")
        patterns = []
        for field in ("ownerPrefixes", "brandPrefixes", "namePrefixes"):
            values = network.get(field) or []
            if not isinstance(values, list):
                raise RuntimeError(f"regional network {key}: {field} must be a list")
            patterns.extend(normalize(value) for value in values if normalize(value))
        if not patterns:
            raise RuntimeError(f"regional network {key} has no match rule")
    return networks


def match_network(station: dict[str, Any], networks: list[dict[str, Any]]) -> str | None:
    values = {
        "ownerPrefixes": normalize(station.get("owner")),
        "brandPrefixes": normalize(station.get("brand")),
        "namePrefixes": normalize(station.get("name")),
    }
    for network in networks:
        for rule_field, station_value in values.items():
            if not station_value:
                continue
            for prefix in network.get(rule_field) or []:
                candidate = normalize(prefix)
                if candidate and station_value.startswith(candidate):
                    return str(network["key"])
    return None


def prune(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    networks = validate_config(config)
    stations = payload.get("stations")
    if not isinstance(stations, list):
        raise RuntimeError("Freshmile dataset has no stations array")

    before_stations = len(stations)
    before_points = sum(len(station.get("chargePoints") or []) for station in stations)
    removed_by_network: Counter[str] = Counter()
    removed_points_by_network: Counter[str] = Counter()
    removed_tariff_text_points = 0
    kept: list[dict[str, Any]] = []

    for station in stations:
        network_key = match_network(station, networks)
        if network_key is None:
            kept.append(station)
            continue
        points = station.get("chargePoints") or []
        removed_by_network[network_key] += 1
        removed_points_by_network[network_key] += len(points)
        removed_tariff_text_points += sum(
            1 for point in points
            if ((point.get("declaredTariff") or {}).get("raw"))
        )

    if not kept:
        raise RuntimeError("regional pruning removed every Freshmile station")

    payload["stations"] = kept
    scope = payload.setdefault("scope", {})
    scope["regionalNetworkExclusionPolicy"] = "explicit_modeled_networks_only"
    scope["regionalNetworkExclusionConfig"] = str(DEFAULT_CONFIG)
    scope["regionalNetworkCandidatesMayRemain"] = True
    scope["regionalNetworkSubscriptionsIncluded"] = False
    scope["regionalOrThirdPartyCpoIdentifiersIncluded"] = False

    audit = {
        "policy": config.get("policy"),
        "configuredNetworkCount": len(networks),
        "excludedStationCount": before_stations - len(kept),
        "excludedChargePointCount": before_points - sum(len(station.get("chargePoints") or []) for station in kept),
        "excludedStationsByNetwork": dict(sorted(removed_by_network.items())),
        "excludedChargePointsByNetwork": dict(sorted(removed_points_by_network.items())),
        "excludedChargePointsWithDeclaredTariffText": removed_tariff_text_points,
        "note": "Unmatched stations remain Freshmile CPO candidates; additional regional identities must be added explicitly before TCC direct-tariff publication if discovered.",
    }
    payload["regionalNetworkAudit"] = audit

    stats = payload.setdefault("stats", {})
    stats["umbrellaStationCountBeforeRegionalExclusion"] = before_stations
    stats["umbrellaChargePointCountBeforeRegionalExclusion"] = before_points
    stats["excludedRegionalStationCount"] = audit["excludedStationCount"]
    stats["excludedRegionalChargePointCount"] = audit["excludedChargePointCount"]
    stats["stationCount"] = len(kept)
    stats["chargePointCount"] = sum(len(station.get("chargePoints") or []) for station in kept)
    stats["chargePointCountWithDeclaredTariffText"] = sum(
        1 for station in kept for point in station.get("chargePoints") or []
        if ((point.get("declaredTariff") or {}).get("raw"))
    )
    stats["chargePointCountWithParsedTariffCandidate"] = sum(
        1 for station in kept for point in station.get("chargePoints") or []
        if str((point.get("declaredTariff") or {}).get("status") or "").startswith("parsed_candidate")
    )

    tcc = payload.setdefault("tccIntegration", {})
    tcc["regionalExclusionLayerReady"] = True
    tcc["directTariffLayerReady"] = False
    tcc["publishToStableAllowed"] = False
    tcc["nextGate"] = (
        "audit unmatched FR*FR1 network identities and cross-check EVSE tariffs against "
        "the Freshmile portal/public API before publishing rankable prices"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    payload = prune(load_gzip_json(args.dataset), load_json(args.config))
    write_gzip_json(args.dataset, payload)
    print(json.dumps({
        "dataset": str(args.dataset),
        "stationCount": payload["stats"]["stationCount"],
        "chargePointCount": payload["stats"]["chargePointCount"],
        "regionalNetworkAudit": payload["regionalNetworkAudit"],
        "tccIntegration": payload["tccIntegration"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
