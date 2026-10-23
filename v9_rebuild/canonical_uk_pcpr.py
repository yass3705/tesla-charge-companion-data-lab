"""Canonical preservation of the three archived UK CPO direct PCPR feeds."""
from __future__ import annotations

import re

from v9_rebuild.canonical import SCHEMA_VERSION, key, validate


SOURCES = {
    "GB:blink_pcpr_direct": "blink-uk-pcpr-direct",
    "GB:allego_pcpr_direct": "allego-uk-pcpr-direct",
    "GB:source_ev_pcpr_direct": "source-ev-uk-pcpr-direct",
}


def _required(value, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"UK PCPR {name} missing")
    return value


def _coordinates(raw):
    if not isinstance(raw, dict):
        return None, None
    try:
        lat, lon = float(raw["latitude"]), float(raw["longitude"])
    except (KeyError, TypeError, ValueError):
        return None, None
    if abs(lat) > 90 or abs(lon) > 180:
        raise ValueError("UK PCPR coordinates invalid")
    return lat, lon


def normalize_uk_pcpr(payload: dict, *, artifact_sha256: str, source_id: str) -> dict:
    if source_id not in SOURCES or not isinstance(artifact_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256):
        raise ValueError("UK PCPR source or SHA invalid")
    if (payload.get("country") != "GB" or
            payload.get("integrationStatus") != "cpo_direct_exact_connector_vat_inclusive_staged" or
            not isinstance(payload.get("sources"), list) or len(payload["sources"]) != 1):
        raise ValueError("UK PCPR archive envelope invalid")
    source = payload["sources"][0]
    if (source.get("id") != SOURCES[source_id] or source.get("country") != "GB" or
            source.get("pricingScope") != "cpo_direct_pcpr" or
            not isinstance(source.get("locations"), list) or not isinstance(source.get("tariffs"), list)):
        raise ValueError("UK PCPR archive source contract invalid")
    tariffs = {}
    for tariff in source["tariffs"]:
        tariff_id = _required(tariff.get("id"), "tariff id")
        if tariff_id in tariffs or tariff.get("country_code") != "GB":
            raise ValueError("UK PCPR tariff identity invalid")
        tariffs[tariff_id] = tariff
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": source_id, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("collectedAt"), "rawMetadata": {
                             "archiveSourceId": source["id"], "pricingScope": source["pricingScope"]}},
              "countries": [{"code": "GB"}], "cpos": [], "stations": [], "evses": [],
              "connectors": [], "offers": [], "tariffCatalog": tariffs}
    cpos = {}
    for location in source["locations"]:
        if location.get("country_code") != "GB" or not isinstance(location.get("evses"), list):
            raise ValueError("UK PCPR location country or EVSE list invalid")
        location_id = _required(location.get("id"), "location id")
        party = _required(location.get("party_id"), "party id")
        cpo_id = key("GB", source_id, "cpo", party)
        operator = location.get("operator") or {}
        cpos.setdefault(cpo_id, {"id": cpo_id, "country": "GB", "sourceOperatorId": party,
                                 "name": operator.get("name") or source.get("name") or party})
        station_id = key("GB", source_id, "station", [party, location_id])
        lat, lon = _coordinates(location.get("coordinates"))
        result["stations"].append({"id": station_id, "country": "GB", "cpoId": cpo_id,
                                   "sourceStationId": location_id, "name": location.get("name"),
                                   "address": location.get("address"), "city": location.get("city"),
                                   "postalCode": location.get("postal_code"), "latitude": lat,
                                   "longitude": lon, "rawSourceFields": location})
        for evse in location["evses"]:
            uid = _required(evse.get("uid"), "EVSE uid")
            official = _required(evse.get("evse_id"), "EVSE id")
            evse_id = key("GB", source_id, "evse", [party, location_id, uid])
            result["evses"].append({"id": evse_id, "country": "GB", "cpoId": cpo_id,
                                    "stationId": station_id, "sourceEvseId": official,
                                    "officialEvseId": official, "sourceUid": uid,
                                    "rawSourceFields": evse})
            if not isinstance(evse.get("connectors"), list):
                raise ValueError("UK PCPR connector list invalid")
            for connector in evse["connectors"]:
                native = _required(connector.get("id"), "connector id")
                connector_id = key("GB", source_id, "connector", [party, location_id, uid, native])
                watts = connector.get("max_electric_power")
                if watts is not None and (not isinstance(watts, (int, float)) or watts < 0):
                    raise ValueError("UK PCPR connector power invalid")
                refs = connector.get("tariff_ids") or []
                if (not isinstance(refs, list) or not all(isinstance(ref, str) and ref in tariffs for ref in refs) or
                        sorted(refs) != sorted(connector.get("sourceTariffIds") or [])):
                    raise ValueError("UK PCPR tariff reference invalid")
                result["connectors"].append({"id": connector_id, "evseId": evse_id,
                                             "sourceConnectorId": native, "officialConnectorId": None,
                                             "plugType": connector.get("standard"),
                                             "powerKw": watts / 1000 if watts else None,
                                             "rawSourceFields": connector})
                for tariff_id in refs:
                    result["offers"].append({"id": key("GB", source_id, "offer", [party, location_id, uid, native, tariff_id]),
                                              "channel": "Direct", "scope": {"evseId": evse_id,
                                                                            "connectorId": connector_id},
                                              "sourceTariffKey": tariff_id, "rawOffer": tariffs[tariff_id],
                                              "calculationStatus": "not_evaluated"})
    result["cpos"] = sorted(cpos.values(), key=lambda row: row["id"])
    for section in ("stations", "evses", "connectors", "offers"):
        result[section].sort(key=lambda row: row["id"])
    validate(result)
    return result
