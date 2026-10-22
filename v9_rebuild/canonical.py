#!/usr/bin/env python3
"""Canonical physical identity and offer linkage for pinned V9 source artifacts.

This module does not parse monetary components. The original offer remains intact
for the later tariff engine, and a missing offer never removes a physical EVSE.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CHANNELS = {"Direct", "Electra", "Electroverse"}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def key(country: str, source: str, kind: str, source_identity: Any) -> str:
    return "tcc:" + digest([country, source, kind, source_identity])


def _power(facility: Any) -> float | None:
    if not isinstance(facility, dict):
        return None
    value = facility.get("power")
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def normalize_swiss(payload: dict, *, artifact_sha256: str, source_id: str = "CH:swiss_integration") -> dict:
    if payload.get("schemaVersion") != 3 or payload.get("country") != "CH" or not isinstance(payload.get("evses"), list):
        raise ValueError("Swiss source schema invalid")
    if not isinstance(artifact_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ValueError("Pinned Swiss artifact SHA missing")
    cpos, stations, evses, connectors, offers = {}, {}, [], [], []
    for row in payload["evses"]:
        source_evse = row.get("evseId")
        operator = row.get("operatorId")
        source_station = row.get("chargingStationId")
        if not isinstance(source_evse, str) or not source_evse or not isinstance(operator, str) or not operator:
            raise ValueError("Swiss physical source identity missing")
        if not isinstance(source_station, str) or not source_station:
            raise ValueError("Swiss station source identity missing")
        cpo_key = key("CH", source_id, "cpo", operator)
        station_key = key("CH", source_id, "station", [operator, source_station])
        evse_key = key("CH", source_id, "evse", source_evse)
        cpos.setdefault(cpo_key, {"id": cpo_key, "country": "CH", "sourceOperatorId": operator, "name": row.get("operatorName")})
        candidate_station = {"id": station_key, "country": "CH", "cpoId": cpo_key, "sourceStationId": source_station,
                             "names": row.get("names"), "address": row.get("address"), "coordinates": row.get("coordinates")}
        previous_station = stations.setdefault(station_key, candidate_station)
        if previous_station["cpoId"] != cpo_key or previous_station["sourceStationId"] != source_station:
            raise ValueError("Swiss station ownership collision")
        evses.append({"id": evse_key, "country": "CH", "cpoId": cpo_key, "stationId": station_key,
                      "sourceEvseId": source_evse, "officialEvseId": source_evse,
                      "accessibility": row.get("accessibility"), "authenticationModes": row.get("authenticationModes"),
                      "paymentOptions": row.get("paymentOptions"), "isOpen24Hours": row.get("isOpen24Hours"),
                      "rawSourceFields": {name: value for name, value in row.items() if name != "directTariff"},
                      "rawRecordSha256": digest(row)})
        plugs = row.get("plugs") or []
        facilities = row.get("chargingFacilities") or []
        if not isinstance(plugs, list) or not isinstance(facilities, list):
            raise ValueError("Swiss connector source shape invalid")
        fingerprints = []
        for index in range(max(len(plugs), len(facilities))):
            plug = plugs[index] if index < len(plugs) else None
            facility = facilities[index] if index < len(facilities) else None
            fingerprints.append({"plugType": plug, "facility": facility})
        occurrences: Counter[str] = Counter()
        for connector in sorted(fingerprints, key=lambda item: digest(item)):
            fingerprint = digest(connector)
            occurrences[fingerprint] += 1
            connector_key = key("CH", source_id, "connector", [source_evse, fingerprint, occurrences[fingerprint]])
            connectors.append({"id": connector_key, "evseId": evse_key, "sourceConnectorId": None,
                               "officialConnectorId": None, "plugType": connector["plugType"],
                               "powerKw": _power(connector["facility"]), "rawFacility": connector["facility"]})
        tariff = row.get("directTariff") or {}
        status = tariff.get("status")
        overlays = tariff.get("overlays") or []
        if status == "priced" and not overlays:
            raise ValueError("Swiss priced EVSE lacks exact source offer")
        if status != "priced" and overlays:
            raise ValueError("Swiss unresolved EVSE carries priced offer")
        if status not in {"priced", "no_public_direct_tariff", "unresolved"}:
            raise ValueError("Swiss direct tariff status invalid")
        for index, overlay in enumerate(overlays):
            if overlay.get("sourceEvseId") != source_evse or not overlay.get("sourceFile"):
                raise ValueError("Swiss offer scope or provenance invalid")
            offer_key = key("CH", source_id, "offer", [source_evse, overlay["sourceFile"], overlay.get("sourceLabel"), index])
            offers.append({"id": offer_key, "channel": "Direct", "scope": {"evseId": evse_key, "connectorId": None},
                           "sourceFile": overlay["sourceFile"], "sourceEvseId": overlay["sourceEvseId"],
                           "sourceLabel": overlay.get("sourceLabel"), "rawOffer": overlay.get("data"),
                           "calculationStatus": "not_evaluated"})
    result = {"schemaVersion": SCHEMA_VERSION, "source": {"id": source_id, "artifactSha256": artifact_sha256,
              "generatedAt": payload.get("generatedAt"), "rawDataset": payload.get("dataset")},
              "countries": [{"code": "CH"}], "cpos": sorted(cpos.values(), key=lambda x: x["id"]),
              "stations": sorted(stations.values(), key=lambda x: x["id"]),
              "evses": sorted(evses, key=lambda x: x["id"]),
              "connectors": sorted(connectors, key=lambda x: x["id"]),
              "offers": sorted(offers, key=lambda x: x["id"])}
    validate(result)
    return result


def validate(data: dict) -> None:
    if data.get("schemaVersion") != SCHEMA_VERSION or not isinstance(data.get("source"), dict):
        raise ValueError("Canonical schema invalid")
    ids = {}
    for collection in ("cpos", "stations", "evses", "connectors", "offers"):
        rows = data.get(collection)
        if not isinstance(rows, list):
            raise ValueError(f"Canonical {collection} missing")
        keys = [row.get("id") for row in rows]
        if any(not key for key in keys) or len(keys) != len(set(keys)):
            raise ValueError(f"Canonical {collection} identity collision")
        ids[collection] = set(keys)
    for station in data["stations"]:
        if station.get("cpoId") not in ids["cpos"]:
            raise ValueError("Canonical station CPO relation invalid")
    for evse in data["evses"]:
        if evse.get("stationId") not in ids["stations"] or evse.get("cpoId") not in ids["cpos"]:
            raise ValueError("Canonical EVSE relation invalid")
        if evse.get("officialEvseId") != evse.get("sourceEvseId"):
            raise ValueError("Canonical official EVSE identity altered")
    for connector in data["connectors"]:
        if connector.get("evseId") not in ids["evses"]:
            raise ValueError("Canonical connector relation invalid")
        if connector.get("officialConnectorId") is not None:
            raise ValueError("Canonical Swiss connector has invented official ID")
    for offer in data["offers"]:
        scope = offer.get("scope") or {}
        if offer.get("channel") not in CHANNELS or scope.get("evseId") not in ids["evses"]:
            raise ValueError("Canonical offer scope invalid")
        if scope.get("connectorId") is not None and scope["connectorId"] not in ids["connectors"]:
            raise ValueError("Canonical connector offer scope invalid")
        if offer.get("calculationStatus") != "not_evaluated":
            raise ValueError("Canonical normalization may not infer a price")


def normalize_file(source: Path, output: Path) -> None:
    raw = source.read_bytes()
    payload = normalize_swiss(json.loads(raw), artifact_sha256=hashlib.sha256(raw).hexdigest())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
