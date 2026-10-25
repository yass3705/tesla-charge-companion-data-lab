"""Preserve archived Powerdot charger/connector identities and raw direct tariffs.

The archived IRVE PDC list is evidence attached to a charger, not an asserted
one-to-one connector mapping. Physical EVSE IDs remain unknown here.
"""
from __future__ import annotations

import math
import re

from v9_rebuild.canonical import SCHEMA_VERSION, key, validate


SOURCE_ID = "FR:powerdot_direct"


def normalize_powerdot(payload: dict, *, artifact_sha256: str,
                       source_id: str = SOURCE_ID) -> dict:
    if source_id not in {"FR:powerdot_direct", "BE:powerdot_direct"}:
        raise ValueError("Powerdot canonical country route invalid")
    route_country = source_id[:2]
    if (not isinstance(payload, dict) or not isinstance(payload.get("chargers"), list) or
            not isinstance(artifact_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256) or
            payload.get("source", {}).get("sourceType") != "direct_cpo_public_adhoc_api"):
        raise ValueError("Powerdot archive envelope invalid")
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": source_id, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("generatedAt"),
                         "rawMetadata": {"source": payload.get("source"),
                                         "irveSource": payload.get("irveSource"),
                                         "counts": payload.get("counts")}},
              "countries": [], "cpos": [], "stations": [], "evses": [],
              "connectors": [], "offers": []}
    cpos, stations, evses, countries = {}, {}, {}, set()
    for row in payload["chargers"]:
        if not isinstance(row, dict):
            raise ValueError("Powerdot charger row invalid")
        if row.get("ok") is not True:
            # Preserve technical failures in the immutable source archive;
            # they cannot create a physical station or an offer.
            continue
        location, charger = row.get("location"), row.get("charger")
        if not isinstance(location, dict) or not isinstance(charger, dict):
            raise ValueError("Powerdot successful charger payload invalid")
        country = location.get("countryCode")
        station_source = location.get("uid")
        charger_source = charger.get("chargerName")
        latitude, longitude = location.get("latitude"), location.get("longitude")
        if (country not in {"FR", "BE"} or not isinstance(station_source, str) or not station_source or
                not isinstance(charger_source, str) or not charger_source or
                not isinstance(latitude, (int, float)) or not math.isfinite(latitude) or abs(latitude) > 90 or
                not isinstance(longitude, (int, float)) or not math.isfinite(longitude) or abs(longitude) > 180 or
                not isinstance(charger.get("connectors"), list)):
            raise ValueError("Powerdot station identity, coordinates or connectors invalid")
        if country != route_country:
            continue
        countries.add(country)
        cpo_id = key(country, source_id, "cpo", "Power Dot France")
        station_id = key(country, source_id, "station", station_source)
        cpos.setdefault(cpo_id, {"id": cpo_id, "country": country,
                                 "sourceOperatorId": "Power Dot France", "name": "Power Dot France"})
        station = {"id": station_id, "country": country, "cpoId": cpo_id,
                   "sourceStationId": station_source, "name": location.get("name"),
                   "address": location.get("address"), "latitude": latitude,
                   "longitude": longitude, "rawSourceFields": location}
        previous = stations.setdefault(station_id, station)
        if (previous["country"], previous["latitude"], previous["longitude"]) != (country, latitude, longitude):
            raise ValueError("Powerdot station identity collision")
        for connector in charger["connectors"]:
            if not isinstance(connector, dict):
                raise ValueError("Powerdot connector record invalid")
            source_number, source_evse = connector.get("connectorNumber"), connector.get("evseNumber")
            if (not isinstance(source_number, int) or source_number < 1 or
                    not isinstance(source_evse, int) or source_evse < 1):
                raise ValueError("Powerdot connector or EVSE source number missing")
            evse_source = f"{charger_source}:{source_evse}"
            evse_id = key(country, source_id, "evse", [station_source, evse_source])
            evses.setdefault(evse_id, {"id": evse_id, "country": country, "cpoId": cpo_id,
                                     "stationId": station_id, "sourceEvseId": evse_source,
                                     "officialEvseId": None,
                                     "identityGranularity": "source_charger_evse_number",
                                     "rawSourceFields": {"chargerName": charger_source,
                                                         "evseNumber": source_evse,
                                                         "irvePdcIdsUnmapped": row.get("irvePdcIds")}})
            connector_id = key(country, source_id, "connector", [station_source, charger_source, source_number])
            power = connector.get("maxPowerKw")
            if power is not None and (not isinstance(power, (int, float)) or
                                      not math.isfinite(power) or power <= 0):
                raise ValueError("Powerdot connector power invalid")
            result["connectors"].append({"id": connector_id, "evseId": evse_id,
                                         "sourceConnectorId": connector.get("physicalReference"),
                                         "officialConnectorId": None, "plugType": None,
                                         "powerKw": power, "rawSourceFields": connector})
            tariff = connector.get("tariff")
            if tariff is not None:
                if not isinstance(tariff, dict):
                    raise ValueError("Powerdot raw connector tariff invalid")
                result["offers"].append({"id": key(country, source_id, "offer", [station_source, charger_source, source_number]),
                                         "channel": "Direct", "scope": {"evseId": evse_id,
                                                                            "connectorId": connector_id},
                                         "sourceTariffKey": tariff.get("id"),
                                         "rawOffer": tariff, "calculationStatus": "not_evaluated"})
    result["countries"] = [{"code": country} for country in sorted(countries)]
    result["cpos"] = sorted(cpos.values(), key=lambda row: row["id"])
    result["stations"] = sorted(stations.values(), key=lambda row: row["id"])
    result["evses"] = sorted(evses.values(), key=lambda row: row["id"])
    for section in ("connectors", "offers"):
        result[section].sort(key=lambda row: row["id"])
    validate(result)
    return result
