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


def normalize_ionity(payload: dict, *, artifact_sha256: str) -> dict:
    """Preserve connector pricing without asserting an absent physical EVSE ID."""
    country = payload.get("country")
    if country not in {"FR", "IT", "DE", "GB"} or payload.get("schemaVersion") != "1.0.0" or not isinstance(payload.get("locations"), list):
        raise ValueError("IONITY source schema invalid")
    if not isinstance(artifact_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ValueError("Pinned IONITY artifact SHA missing")
    source_id = f"{country}:ionity_direct"
    cpo_key = key(country, source_id, "cpo", "IONITY_CPO")
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": source_id, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("generatedAt"), "rawDataset": payload.get("dataset")},
              "countries": [{"code": country}],
              "cpos": [{"id": cpo_key, "country": country, "sourceOperatorId": "IONITY_CPO", "name": "IONITY"}],
              "stations": [], "evses": [], "connectors": [], "offers": []}
    seen_evse_keys: set[str] = set()
    for location in payload["locations"]:
        location_uuid = location.get("uuid")
        if location.get("country") != country or location.get("cpoIdentifier") != "IONITY_CPO" or not isinstance(location_uuid, str) or not location_uuid:
            raise ValueError("IONITY station identity or ownership invalid")
        station_key = key(country, source_id, "station", location_uuid)
        result["stations"].append({"id": station_key, "country": country, "cpoId": cpo_key,
                                   "sourceStationId": location_uuid, "name": location.get("name"),
                                   "address": location.get("address"), "postalCode": location.get("postalCode"),
                                   "city": location.get("city"), "latitude": location.get("latitude"),
                                   "longitude": location.get("longitude"), "rawSourceFields": location})
        if not isinstance(location.get("connectors"), list):
            raise ValueError("IONITY connector list missing")
        for connector in location["connectors"]:
            connector_uuid = connector.get("uuid")
            if not isinstance(connector_uuid, str) or not connector_uuid:
                raise ValueError("IONITY source connector UUID missing")
            source_evse = connector.get("sourceEvseId") or None
            # The source has no physical EVSE ID for many connectors. A technical
            # slot keeps the tree intact, but does not claim physical identity.
            slot_identity = source_evse or connector_uuid
            evse_key = key(country, source_id, "evse", [location_uuid, slot_identity])
            if evse_key not in seen_evse_keys:
                seen_evse_keys.add(evse_key)
                result["evses"].append({"id": evse_key, "country": country, "cpoId": cpo_key,
                                       "stationId": station_key, "sourceEvseId": source_evse,
                                       "officialEvseId": source_evse, "identityGranularity": "source_evse" if source_evse else "connector_slot"})
            connector_key = key(country, source_id, "connector", connector_uuid)
            result["connectors"].append({"id": connector_key, "evseId": evse_key,
                                         "sourceConnectorId": connector_uuid, "officialConnectorId": None,
                                         "plugType": connector.get("type"), "powerKw": connector.get("powerKw"),
                                         "rawSourceFields": connector})
            price_field = "pricePerKwhGbp" if country == "GB" else "pricePerKwhEur"
            if connector.get(price_field) is not None:
                offer_key = key(country, source_id, "offer", connector_uuid)
                result["offers"].append({"id": offer_key, "channel": "Direct",
                                         "scope": {"evseId": evse_key, "connectorId": connector_key},
                                         "sourceConnectorId": connector_uuid,
                                         "rawOffer": {price_field: connector[price_field]},
                                         "calculationStatus": "not_evaluated"})
    for name in ("stations", "evses", "connectors", "offers"):
        result[name].sort(key=lambda item: item["id"])
    validate(result)
    return result


def normalize_belib(payload: dict, *, artifact_sha256: str) -> dict:
    """Keep Belib's physical connector and service-class scope without pricing it."""
    if payload.get("schemaVersion") != "1.0.0" or payload.get("country") != "FR" or not isinstance(payload.get("stations"), list) or not isinstance(payload.get("directTariffProfiles"), list):
        raise ValueError("Belib source schema invalid")
    if not isinstance(artifact_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ValueError("Pinned Belib artifact SHA missing")
    source_id = "FR:belib_stations"
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": source_id, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("generatedAt"), "rawDataset": payload.get("dataset"),
                         "rawDirectTariffProfiles": payload["directTariffProfiles"]},
              "countries": [{"code": "FR"}], "cpos": [], "stations": [], "evses": [], "connectors": [], "offers": []}
    cpos, evses, connectors = {}, {}, {}
    profiles = {}
    for profile in payload["directTariffProfiles"]:
        if not isinstance(profile, dict) or not profile.get("profileId") or not profile.get("serviceClass"):
            raise ValueError("Belib profile identity invalid")
        if profile["profileId"] in profiles:
            raise ValueError("Belib profile collision")
        profiles[profile["profileId"]] = profile
    for station in payload["stations"]:
        source_station = station.get("stationId")
        operator = station.get("operatorSourceValue")
        if not isinstance(source_station, str) or not source_station or not isinstance(operator, str) or not operator:
            raise ValueError("Belib station or CPO identity missing")
        cpo_key = key("FR", source_id, "cpo", operator)
        station_key = key("FR", source_id, "station", source_station)
        cpos.setdefault(cpo_key, {"id": cpo_key, "country": "FR", "sourceOperatorId": operator, "name": operator})
        coordinates = station.get("coordinates") or {}
        result["stations"].append({"id": station_key, "country": "FR", "cpoId": cpo_key,
                                   "sourceStationId": source_station, "name": station.get("name"),
                                   "address": station.get("address"), "latitude": coordinates.get("latitude"),
                                   "longitude": coordinates.get("longitude"),
                                   "networkBrand": station.get("brandSourceValue"),
                                   "sourceOperatorLabel": station.get("operator"), "rawSourceFields": station})
        configurations = station.get("configurations")
        if not isinstance(configurations, list):
            raise ValueError("Belib configurations missing")
        for config in configurations:
            source_evses = config.get("evseIds")
            plug_types = config.get("connectorTypes")
            if not isinstance(source_evses, list) or not isinstance(plug_types, list) or not config.get("kind") or not config.get("serviceClass"):
                raise ValueError("Belib configuration schema invalid")
            for source_evse in source_evses:
                if not isinstance(source_evse, str) or not source_evse:
                    raise ValueError("Belib source EVSE missing")
                evse_key = key("FR", source_id, "evse", source_evse)
                previous = evses.setdefault(evse_key, {"id": evse_key, "country": "FR", "cpoId": cpo_key,
                                                   "stationId": station_key, "sourceEvseId": source_evse,
                                                   "officialEvseId": source_evse})
                if previous["stationId"] != station_key or previous["cpoId"] != cpo_key:
                    raise ValueError("Belib EVSE ownership collision")
                for plug_type in plug_types:
                    connector_key = key("FR", source_id, "connector", [source_evse, config["kind"], config.get("powerKw"), plug_type])
                    connectors.setdefault(connector_key, {"id": connector_key, "evseId": evse_key,
                                                         "sourceConnectorId": None, "officialConnectorId": None,
                                                         "plugType": plug_type, "powerKw": config.get("powerKw"),
                                                         "rawSourceFields": {"kind": config["kind"], "serviceClass": config["serviceClass"]}})
                    for profile in profiles.values():
                        if profile["serviceClass"] != config["serviceClass"]:
                            continue
                        offer_key = key("FR", source_id, "offer", [connector_key, profile["profileId"]])
                        result["offers"].append({"id": offer_key, "channel": "Direct",
                                                  "scope": {"evseId": evse_key, "connectorId": connector_key},
                                                  "sourceProfileId": profile["profileId"], "rawOffer": profile,
                                                  "calculationStatus": "not_evaluated"})
    result["cpos"] = sorted(cpos.values(), key=lambda row: row["id"])
    result["evses"] = sorted(evses.values(), key=lambda row: row["id"])
    result["connectors"] = sorted(connectors.values(), key=lambda row: row["id"])
    for section in ("stations", "offers"):
        result[section].sort(key=lambda row: row["id"])
    validate(result)
    return result


def normalize_atlante_italy(payload: dict, *, artifact_sha256: str) -> dict:
    """Preserve Atlante's exact OCPI EVSE/connector tariff scope, unevaluated."""
    if not isinstance(payload.get("locations"), list) or not isinstance(payload.get("metadata"), dict):
        raise ValueError("Atlante Italy source schema invalid")
    if payload["metadata"].get("country") != "IT":
        raise ValueError("Atlante Italy country invalid")
    if not isinstance(artifact_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ValueError("Pinned Atlante Italy artifact SHA missing")
    source_id = "IT:atlante_direct"
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": source_id, "artifactSha256": artifact_sha256,
                         "generatedAt": payload["metadata"].get("completedAt"),
                         "rawMetadata": payload["metadata"]},
              "countries": [{"code": "IT"}], "cpos": [], "stations": [],
              "evses": [], "connectors": [], "offers": []}
    cpos, evses = {}, {}
    for location in payload["locations"]:
        source_station = location.get("locationId")
        party = location.get("partyId")
        if location.get("countryCode") != "IT" or not isinstance(source_station, str) or not source_station or not isinstance(party, str) or not party:
            raise ValueError("Atlante Italy station identity invalid")
        station_key = key("IT", source_id, "station", [party, source_station])
        cpo_key = key("IT", source_id, "cpo", party)
        cpos.setdefault(cpo_key, {"id": cpo_key, "country": "IT", "sourceOperatorId": party,
                                   "name": location.get("operatorName", "").strip() or party})
        coordinates = location.get("coordinates")
        match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", coordinates or "")
        latitude, longitude = (float(match[1]), float(match[2])) if match else (None, None)
        if latitude is not None and (abs(latitude) > 90 or abs(longitude) > 180):
            raise ValueError("Atlante Italy coordinates invalid")
        result["stations"].append({"id": station_key, "country": "IT", "cpoId": cpo_key,
                                   "sourceStationId": source_station, "sourceLocationUuid": location.get("id"),
                                   "name": location.get("name"), "address": location.get("address"),
                                   "city": location.get("city"), "postalCode": location.get("postalCode"),
                                   "latitude": latitude, "longitude": longitude,
                                   "rawSourceFields": location})
        if not isinstance(location.get("connectors"), list):
            raise ValueError("Atlante Italy connector list missing")
        for connector in location["connectors"]:
            source_evse, source_connector = connector.get("evseId"), connector.get("connectorId")
            if not isinstance(source_evse, str) or not source_evse or not isinstance(source_connector, str) or not source_connector:
                raise ValueError("Atlante Italy EVSE or connector identity missing")
            evse_key = key("IT", source_id, "evse", source_evse)
            previous = evses.setdefault(evse_key, {"id": evse_key, "country": "IT", "cpoId": cpo_key,
                                                   "stationId": station_key, "sourceEvseId": source_evse,
                                                   "officialEvseId": source_evse})
            if previous["stationId"] != station_key or previous["cpoId"] != cpo_key:
                raise ValueError("Atlante Italy EVSE ownership collision")
            connector_key = key("IT", source_id, "connector", [source_evse, source_connector])
            result["connectors"].append({"id": connector_key, "evseId": evse_key,
                                         "sourceConnectorId": source_connector, "officialConnectorId": None,
                                         "plugType": connector.get("connectorType"), "powerKw": connector.get("powerKw"),
                                         "rawSourceFields": connector})
            tariffs = connector.get("tariffs") or []
            if not isinstance(tariffs, list):
                raise ValueError("Atlante Italy tariff list invalid")
            for index, tariff in enumerate(tariffs):
                identifiers = tariff.get("identifiers") or {}
                if identifiers.get("evseId") != source_evse or identifiers.get("connectorId") != source_connector:
                    raise ValueError("Atlante Italy tariff connector scope invalid")
                result["offers"].append({"id": key("IT", source_id, "offer", [source_evse, source_connector, index]),
                                          "channel": "Direct", "scope": {"evseId": evse_key, "connectorId": connector_key},
                                          "rawOffer": tariff, "calculationStatus": "not_evaluated"})
    result["cpos"] = sorted(cpos.values(), key=lambda row: row["id"])
    result["evses"] = sorted(evses.values(), key=lambda row: row["id"])
    for section in ("stations", "connectors", "offers"):
        result[section].sort(key=lambda row: row["id"])
    validate(result)
    return result


def normalize_zephyre_exact(payload: dict, *, artifact_sha256: str) -> dict:
    """Represent archived ePowerDirect charge points without inferring a site or plug ID."""
    if not isinstance(payload.get("records"), list) or not isinstance(payload.get("source"), dict):
        raise ValueError("Zephyre exact archive schema invalid")
    if not isinstance(artifact_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ValueError("Pinned Zephyre artifact SHA missing")
    source_id, country = "FR:zephyre_epowerdirect_exact", "FR"
    cpo_key = key(country, source_id, "cpo", "FRZP1")
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": source_id, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("finalizedAt") or payload.get("observedAt"),
                         "rawSource": payload["source"]},
              "countries": [{"code": country}],
              "cpos": [{"id": cpo_key, "country": country, "sourceOperatorId": "FRZP1", "name": "Zéphyre"}],
              "stations": [], "evses": [], "connectors": [], "offers": []}
    for row in payload["records"]:
        source_evse, source_point = row.get("evseId"), row.get("name")
        if not isinstance(source_evse, str) or not source_evse.startswith("FR*ZP1*") or not isinstance(source_point, str) or not source_point:
            raise ValueError("Zephyre exact EVSE or charge point missing")
        address = row.get("address")
        if not isinstance(address, dict) or address.get("country") != country:
            raise ValueError("Zephyre charge point country invalid")
        try:
            latitude, longitude = float(address["latitude"]), float(address["longitude"])
        except (KeyError, TypeError, ValueError):
            latitude, longitude = None, None
        if latitude is not None and (abs(latitude) > 90 or abs(longitude) > 180):
            raise ValueError("Zephyre charge point coordinates invalid")
        station_key = key(country, source_id, "station", source_point)
        evse_key = key(country, source_id, "evse", source_evse)
        # The source identifies a charge point, not its physical parent station.
        # Keep a technical one-point group; no physical station ID is asserted.
        result["stations"].append({"id": station_key, "country": country, "cpoId": cpo_key,
                                   "sourceStationId": None, "sourceChargePointName": source_point,
                                   "name": source_point, "address": address.get("street"), "city": address.get("city"),
                                   "latitude": latitude, "longitude": longitude,
                                   "groupingGranularity": "source_charge_point", "rawSourceFields": row})
        result["evses"].append({"id": evse_key, "country": country, "cpoId": cpo_key,
                                "stationId": station_key, "sourceEvseId": source_evse,
                                "officialEvseId": source_evse, "accessibility": row.get("accessibilityLabel"),
                                "rawSourceFields": row})
        # plugType describes the charge point; the source provides no connector ID.
        connector_key = key(country, source_id, "connector", [source_evse, row.get("plugType")])
        result["connectors"].append({"id": connector_key, "evseId": evse_key,
                                     "sourceConnectorId": None, "officialConnectorId": None,
                                     "plugType": row.get("plugType"), "powerKw": _power({"power": row.get("maxChargingPower")}),
                                     "identityGranularity": "evse_plug_type"})
        tariff = row.get("tariff")
        if tariff is not None:
            if not isinstance(tariff, dict):
                raise ValueError("Zephyre tariff schema invalid")
            result["offers"].append({"id": key(country, source_id, "offer", source_evse), "channel": "Direct",
                                      "scope": {"evseId": evse_key, "connectorId": connector_key},
                                      "sourceEvseId": source_evse, "rawOffer": tariff,
                                      "calculationStatus": "not_evaluated"})
    for section in ("stations", "evses", "connectors", "offers"):
        result[section].sort(key=lambda row: row["id"])
    validate(result)
    return result


def normalize_driveco_evse(payload: dict, *, artifact_sha256: str) -> dict:
    """Keep archived Driveco and partner EVSE; never turn partial fee data into a price."""
    if payload.get("schemaVersion") != "1.0.0" or not isinstance(payload.get("resolved"), list) or not isinstance(payload.get("unresolved"), list):
        raise ValueError("Driveco EVSE archive schema invalid")
    if not isinstance(artifact_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ValueError("Pinned Driveco artifact SHA missing")
    country, source_id = "FR", "FR:driveco_evse_tariffs"
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": source_id, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("generatedAt"), "rawPolicy": payload.get("policy"),
                         "rawSource": payload.get("source")},
              "countries": [{"code": country}], "cpos": [], "stations": [],
              "evses": [], "connectors": [], "offers": []}
    cpos, stations = {}, {}
    for priced, rows in ((True, payload["resolved"]), (False, payload["unresolved"])):
        for row in rows:
            source_evse, source_station, operator = row.get("evseId"), row.get("stationId"), row.get("operator")
            if not all(isinstance(value, str) and value for value in (source_evse, source_station, operator)):
                raise ValueError("Driveco physical identity missing")
            network_class = row.get("networkClass")
            if network_class not in {"driveco_network", "partner_network"}:
                raise ValueError("Driveco network class invalid")
            cpo_key = key(country, source_id, "cpo", operator)
            station_key = key(country, source_id, "station", [operator, source_station])
            evse_key = key(country, source_id, "evse", source_evse)
            cpos.setdefault(cpo_key, {"id": cpo_key, "country": country,
                                      "sourceOperatorId": operator, "name": operator})
            candidate = {"id": station_key, "country": country, "cpoId": cpo_key,
                         "sourceStationId": source_station, "name": row.get("stationName"),
                         "address": row.get("address"), "city": row.get("city"),
                         "postalCode": row.get("postalCode"), "networkClass": network_class,
                         "groupingGranularity": "source_station"}
            previous = stations.setdefault(station_key, candidate)
            if previous["cpoId"] != cpo_key or previous["sourceStationId"] != source_station or previous["networkClass"] != network_class:
                raise ValueError("Driveco station ownership collision")
            result["evses"].append({"id": evse_key, "country": country, "cpoId": cpo_key,
                                    "stationId": station_key, "sourceEvseId": source_evse,
                                    "officialEvseId": source_evse, "rawSourceFields": row})
            # The archive records power per EVSE, but no physical connector ID or type.
            connector_key = key(country, source_id, "connector", source_evse)
            result["connectors"].append({"id": connector_key, "evseId": evse_key,
                                         "sourceConnectorId": None, "officialConnectorId": None,
                                         "plugType": None, "powerKw": _power({"power": row.get("powerKw")}),
                                         "identityGranularity": "evse_unspecified_connector"})
            if priced:
                tariff = row.get("tariff")
                if not isinstance(tariff, dict) or not isinstance(row.get("feeSemantics"), dict):
                    raise ValueError("Driveco resolved tariff or fee semantics missing")
                result["offers"].append({"id": key(country, source_id, "offer", source_evse),
                                          "channel": "Direct", "scope": {"evseId": evse_key, "connectorId": None},
                                          "sourceEvseId": source_evse,
                                          "rawOffer": {"tariff": tariff, "feeSemantics": row["feeSemantics"]},
                                          "calculationStatus": "not_evaluated"})
    result["cpos"] = sorted(cpos.values(), key=lambda row: row["id"])
    result["stations"] = sorted(stations.values(), key=lambda row: row["id"])
    for section in ("evses", "connectors", "offers"):
        result[section].sort(key=lambda row: row["id"])
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
    stations_by_id = {row["id"]: row for row in data["stations"]}
    connectors_by_id = {row["id"]: row for row in data["connectors"]}
    for evse in data["evses"]:
        if evse.get("stationId") not in ids["stations"] or evse.get("cpoId") not in ids["cpos"]:
            raise ValueError("Canonical EVSE relation invalid")
        station = stations_by_id[evse["stationId"]]
        if evse["cpoId"] != station["cpoId"] or evse.get("country") != station.get("country"):
            raise ValueError("Canonical EVSE ownership invalid")
        if evse.get("officialEvseId") != evse.get("sourceEvseId"):
            raise ValueError("Canonical official EVSE identity altered")
    for connector in data["connectors"]:
        if connector.get("evseId") not in ids["evses"]:
            raise ValueError("Canonical connector relation invalid")
        official_connector = connector.get("officialConnectorId")
        if official_connector is not None and (not isinstance(official_connector, str) or
                                               not official_connector or
                                               official_connector != connector.get("sourceConnectorId")):
            raise ValueError("Canonical official connector identity altered")
    for offer in data["offers"]:
        scope = offer.get("scope") or {}
        if offer.get("channel") not in CHANNELS or scope.get("evseId") not in ids["evses"]:
            raise ValueError("Canonical offer scope invalid")
        if scope.get("connectorId") is not None and scope["connectorId"] not in ids["connectors"]:
            raise ValueError("Canonical connector offer scope invalid")
        if scope.get("connectorId") is not None and connectors_by_id[scope["connectorId"]]["evseId"] != scope["evseId"]:
            raise ValueError("Canonical connector offer ownership invalid")
        if offer.get("calculationStatus") != "not_evaluated":
            raise ValueError("Canonical normalization may not infer a price")


def normalize_file(source: Path, output: Path) -> None:
    raw = source.read_bytes()
    payload = normalize_swiss(json.loads(raw), artifact_sha256=hashlib.sha256(raw).hexdigest())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
