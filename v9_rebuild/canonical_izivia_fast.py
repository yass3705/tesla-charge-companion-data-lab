"""Preserve archived IZIVIA FAST map rows at exact national station identity.

The map groups socket types and stall counts, not physical EVSE identifiers.
Those groups stay in rawSourceFields. The separate direct tariff archive is not
assigned to any EVSE or connector here.
"""
from __future__ import annotations

import math
import re

from v9_rebuild.canonical import SCHEMA_VERSION, key, validate

SOURCE_ID = "FR:izivia_fast_map"
NATIONAL_SOURCE = "FR:irve_static"


def normalize_izivia_fast_map(payload: dict, *, artifact_sha256: str) -> dict:
    if (not isinstance(payload, dict) or payload.get("schemaVersion") != 1 or
            payload.get("country") != "FR" or
            payload.get("mode") != "exact_station_official_map_connector_correction" or
            not isinstance(payload.get("stations"), list) or
            not isinstance(artifact_sha256, str) or
            not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256)):
        raise ValueError("IZIVIA FAST map envelope invalid")
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": SOURCE_ID, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("sourceSnapshotAt"),
                         "rawPolicy": payload.get("policy")},
              "countries": [{"code": "FR"}], "cpos": [], "stations": [],
              "evses": [], "connectors": [], "offers": []}
    cpo_id = key("FR", SOURCE_ID, "cpo", "IZIVIA")
    result["cpos"].append({"id": cpo_id, "country": "FR", "sourceOperatorId": "IZIVIA", "name": "IZIVIA"})
    seen_stations = set()
    for row in payload["stations"]:
        if not isinstance(row, dict):
            raise ValueError("IZIVIA FAST station row invalid")
        source_station, lat, lon = row.get("sourceStationId"), row.get("latitude"), row.get("longitude")
        if (not isinstance(source_station, str) or not source_station or source_station in seen_stations or
                row.get("countryCode") != "FR" or row.get("canonicalId") != "FR:national:" + source_station or
                not isinstance(lat, (int, float)) or isinstance(lat, bool) or not math.isfinite(lat) or abs(lat) > 90 or
                not isinstance(lon, (int, float)) or isinstance(lon, bool) or not math.isfinite(lon) or abs(lon) > 180 or
                not isinstance(row.get("evses"), list)):
            raise ValueError("IZIVIA FAST exact station identity or coordinates invalid")
        seen_stations.add(source_station)
        seen_groups = set()
        for group in row["evses"]:
            if (not isinstance(group, dict) or not isinstance(group.get("id"), str) or
                    not group["id"] or group["id"] in seen_groups or
                    not isinstance(group.get("stalls"), int) or isinstance(group["stalls"], bool) or group["stalls"] < 1 or
                    not isinstance(group.get("connectors"), list)):
                raise ValueError("IZIVIA FAST map socket group invalid")
            seen_groups.add(group["id"])
            seen_connectors = set()
            for connector in group["connectors"]:
                cid, kind, power = connector.get("id"), connector.get("kind"), connector.get("powerKw")
                if (not isinstance(cid, str) or not cid or cid in seen_connectors or
                        kind not in {"AC", "DC"} or not isinstance(power, (int, float)) or isinstance(power, bool) or
                        not math.isfinite(power) or power <= 0):
                    raise ValueError("IZIVIA FAST map connector group invalid")
                seen_connectors.add(cid)
        # Exact national station identity is proven by the archived station ID.
        # Map groups remain raw: no official EVSE/connector is inferred.
        station_id = key("FR", NATIONAL_SOURCE, "station", source_station)
        result["stations"].append({"id": station_id, "country": "FR", "cpoId": cpo_id,
                                   "sourceStationId": source_station, "name": row.get("name"),
                                   "address": row.get("address"), "latitude": lat, "longitude": lon,
                                   "networkBrand": row.get("networkBrand"), "rawSourceFields": row})
    result["stations"].sort(key=lambda row: row["id"])
    validate(result)
    return result
