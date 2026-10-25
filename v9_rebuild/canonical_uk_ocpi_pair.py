"""Preserve archived UK OCPI locations and exact connector tariff references.

The Gridserve pair and Ubitricity single archive share the OCPI location shape.
No price interpretation or station-level tariff propagation happens here.
"""
from __future__ import annotations

import re

from v9_rebuild.canonical import SCHEMA_VERSION, key, validate


SOURCE_CONTRACTS = {
    "GB:gridserve_pcpr_direct": ("GRD", "GRIDSERVE PCPR Open Data API"),
    "GB:ubitricity_pcpr_direct": ("UBI", "operator_supplied_Eco_Movement_PCPR"),
}


def required(value, field):
    if not isinstance(value, str) or not value:
        raise ValueError(f"UK OCPI {field} missing")
    return value


def coordinates(raw):
    if not isinstance(raw, dict) or raw.get("latitude") is None or raw.get("longitude") is None:
        return None, None
    try:
        latitude, longitude = float(raw["latitude"]), float(raw["longitude"])
    except (TypeError, ValueError) as error:
        raise ValueError("UK OCPI coordinates invalid") from error
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("UK OCPI coordinates invalid")
    return latitude, longitude


def normalize_uk_ocpi_pair(payload: dict, *, artifact_sha256: str, source_id: str) -> dict:
    if source_id not in SOURCE_CONTRACTS or not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256):
        raise ValueError("UK OCPI route or source SHA invalid")
    party, source_name = SOURCE_CONTRACTS[source_id]
    if source_id == "GB:gridserve_pcpr_direct":
        if not isinstance(payload, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(payload.get("tariffArtifactSha256", ""))):
            raise ValueError("UK OCPI tariff archive SHA missing")
        locations_doc, tariffs_doc = payload.get("locations"), payload.get("tariffs")
        if (not isinstance(locations_doc, dict) or not isinstance(tariffs_doc, dict) or
                locations_doc.get("source") != source_name or tariffs_doc.get("source") != source_name or
                locations_doc.get("collectedAt") != tariffs_doc.get("collectedAt") or
                not isinstance(locations_doc.get("pages"), int) or locations_doc["pages"] < 1 or
                not isinstance(tariffs_doc.get("pages"), int) or tariffs_doc["pages"] < 1):
            raise ValueError("UK OCPI paired archive contract invalid")
        source = locations_doc
        raw_tariffs = tariffs_doc.get("tariffs")
    else:
        source = payload
        raw_tariffs = source.get("tariffs") if isinstance(source, dict) else None
        if not isinstance(source, dict) or source.get("source") != source_name:
            raise ValueError("UK OCPI single archive contract invalid")
    raw_locations = source.get("locations")
    if not isinstance(raw_locations, list) or not isinstance(raw_tariffs, list):
        raise ValueError("UK OCPI locations or tariffs missing")
    tariffs = {}
    for tariff in raw_tariffs:
        if not isinstance(tariff, dict) or tariff.get("country_code") != "GB" or tariff.get("party_id") != party:
            raise ValueError("UK OCPI tariff ownership invalid")
        native = required(tariff.get("id"), "tariff id")
        if native in tariffs:
            raise ValueError("UK OCPI tariff identity collision")
        tariffs[native] = tariff
    cpo_id = key("GB", source_id, "cpo", party)
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": source_id, "artifactSha256": artifact_sha256,
                         "generatedAt": source.get("collectedAt"),
                         "rawMetadata": {"archiveSource": source_name, "partyId": party,
                                         "tariffArtifactSha256": payload.get("tariffArtifactSha256") if source_id == "GB:gridserve_pcpr_direct" else artifact_sha256}},
              "countries": [{"code": "GB"}],
              "cpos": [{"id": cpo_id, "country": "GB", "sourceOperatorId": party, "name": party}],
              "stations": [], "evses": [], "connectors": [], "offers": [], "tariffCatalog": tariffs}
    for location in raw_locations:
        if (not isinstance(location, dict) or location.get("country_code") != "GB" or
                location.get("party_id") != party or not isinstance(location.get("evses"), list)):
            raise ValueError("UK OCPI location ownership or EVSE list invalid")
        native_station = required(location.get("id"), "location id")
        station_id = key("GB", source_id, "station", [party, native_station])
        latitude, longitude = coordinates(location.get("coordinates"))
        result["stations"].append({"id": station_id, "country": "GB", "cpoId": cpo_id,
                                   "sourceStationId": native_station, "name": location.get("name"),
                                   "address": location.get("address"), "city": location.get("city"),
                                   "postalCode": location.get("postal_code"),
                                   "latitude": latitude, "longitude": longitude,
                                   "rawSourceFields": location})
        for evse in location["evses"]:
            if not isinstance(evse, dict) or not isinstance(evse.get("connectors"), list):
                raise ValueError("UK OCPI EVSE or connectors invalid")
            uid = required(evse.get("uid"), "EVSE uid")
            official = evse.get("evse_id")
            if official is not None:
                official = required(official, "official EVSE id")
            evse_id = key("GB", source_id, "evse", [party, native_station, uid])
            result["evses"].append({"id": evse_id, "country": "GB", "cpoId": cpo_id,
                                    "stationId": station_id, "sourceUid": uid,
                                    "sourceEvseId": official or uid, "officialEvseId": official,
                                    "rawSourceFields": evse})
            for connector in evse["connectors"]:
                if not isinstance(connector, dict):
                    raise ValueError("UK OCPI connector invalid")
                native_connector = required(connector.get("id"), "connector id")
                connector_id = key("GB", source_id, "connector", [party, native_station, uid, native_connector])
                watts = connector.get("max_electric_power")
                if watts is not None and (not isinstance(watts, (int, float)) or isinstance(watts, bool) or watts < 0):
                    raise ValueError("UK OCPI connector power invalid")
                refs = connector.get("tariff_ids")
                if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
                    raise ValueError("UK OCPI connector tariff references invalid")
                unknown = sorted(set(refs) - tariffs.keys())
                result["connectors"].append({"id": connector_id, "evseId": evse_id,
                                             "sourceConnectorId": native_connector,
                                             "officialConnectorId": None,
                                             "plugType": connector.get("standard"),
                                             "powerKw": watts / 1000 if watts else None,
                                             "unresolvedTariffRefs": unknown,
                                             "rawSourceFields": connector})
                for tariff_id in sorted(set(refs) & tariffs.keys()):
                    result["offers"].append({"id": key("GB", source_id, "offer", [party, native_station, uid, native_connector, tariff_id]),
                                              "channel": "Direct", "scope": {"evseId": evse_id,
                                                                            "connectorId": connector_id},
                                              "sourceTariffKey": tariff_id, "rawOffer": tariffs[tariff_id],
                                              "calculationStatus": "not_evaluated"})
    for section in ("stations", "evses", "connectors", "offers"):
        result[section].sort(key=lambda row: row["id"])
    validate(result)
    return result
