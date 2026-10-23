"""Preserve the archived EVGO Morocco station and connector identities."""
from __future__ import annotations

import math
import re

from v9_rebuild.canonical import SCHEMA_VERSION, key, validate


SOURCE_ID = "MA:evgo"


def normalize_morocco_evgo(payload: dict, *, artifact_sha256: str) -> dict:
    if (not isinstance(payload, dict) or payload.get("schema_version") != 4 or
            not isinstance(payload.get("stations"), list) or
            not isinstance(artifact_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256)):
        raise ValueError("EVGO Morocco archive envelope invalid")
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": SOURCE_ID, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("source_generated_at"),
                         "rawMetadata": {"sourceReport": payload.get("source_report"),
                                         "sourceHost": payload.get("source_host"),
                                         "sourceApiVersion": payload.get("source_api_version"),
                                         "policy": payload.get("policy")}},
              "countries": [{"code": "MA"}], "cpos": [], "stations": [],
              "evses": [], "connectors": [], "offers": []}
    cpos = {}
    for station in payload["stations"]:
        if not isinstance(station, dict) or not isinstance(station.get("evses"), list):
            raise ValueError("EVGO Morocco station schema invalid")
        native_station = station.get("locationId")
        operator = station.get("operator_cpo_candidate") or "EVGO"
        lat, lon = station.get("latitude"), station.get("longitude")
        if (native_station is None or not isinstance(operator, str) or
                not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or
                not math.isfinite(lat) or not math.isfinite(lon) or
                abs(lat) > 90 or abs(lon) > 180):
            raise ValueError("EVGO Morocco station identity or coordinates invalid")
        cpo_id = key("MA", SOURCE_ID, "cpo", operator)
        station_id = key("MA", SOURCE_ID, "station", str(native_station))
        cpos.setdefault(cpo_id, {"id": cpo_id, "country": "MA", "name": operator,
                                 "sourceOperatorId": operator})
        result["stations"].append({"id": station_id, "country": "MA", "cpoId": cpo_id,
                                   "sourceStationId": str(native_station), "name": station.get("name"),
                                   "address": station.get("address"), "latitude": lat,
                                   "longitude": lon, "networkBrand": station.get("site_brand"),
                                   "rawSourceFields": station})
        for evse in station["evses"]:
            native_evse = evse.get("id") if isinstance(evse, dict) else None
            if native_evse is None or not isinstance(evse.get("connectors"), list):
                raise ValueError("EVGO Morocco EVSE identity or connectors invalid")
            evse_id = key("MA", SOURCE_ID, "evse", [str(native_station), str(native_evse)])
            result["evses"].append({"id": evse_id, "country": "MA", "cpoId": cpo_id,
                                    "stationId": station_id, "sourceEvseId": str(native_evse),
                                    "officialEvseId": None, "rawSourceFields": evse})
            # Native maxPower is absent in this archived report. A model-derived
            # candidate is evidence metadata, never connector power.
            for connector in evse["connectors"]:
                native_connector = connector.get("id") if isinstance(connector, dict) else None
                if native_connector is None:
                    raise ValueError("EVGO Morocco connector identity missing")
                connector_id = key("MA", SOURCE_ID, "connector",
                                   [str(native_station), str(native_evse), str(native_connector)])
                result["connectors"].append({"id": connector_id, "evseId": evse_id,
                                             "sourceConnectorId": str(native_connector),
                                             "officialConnectorId": None,
                                             "plugType": connector.get("name"),
                                             "kind": str(evse.get("currentType") or "").upper() or None,
                                             "powerKw": None, "rawSourceFields": connector})
    result["cpos"] = sorted(cpos.values(), key=lambda item: item["id"])
    for section in ("stations", "evses", "connectors"):
        result[section].sort(key=lambda item: item["id"])
    validate(result)
    return result
