"""Preserve the archived REVE national compact station topology without pricing it."""
from __future__ import annotations

import math
import re

from v9_rebuild.canonical import SCHEMA_VERSION, key, validate


SOURCE_ID = "ES:reve_static"
OFFICIAL_EVSE = re.compile(r"^ES\*[A-Z0-9]+\*E[A-Z0-9*._-]+$")


def normalize_spain_reve(payload: dict, *, artifact_sha256: str) -> dict:
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256 or ""):
        raise ValueError("REVE static source or SHA invalid")
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": SOURCE_ID, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("generatedAt")},
              "countries": [{"code": "ES"}], "cpos": [], "stations": [],
              "evses": [], "connectors": [], "offers": []}
    cpos = {}
    for row in rows:
        if (not isinstance(row, list) or len(row) != 12 or not isinstance(row[0], str) or not row[0] or
                not isinstance(row[5], str) or not row[5] or not isinstance(row[8], list)):
            raise ValueError("REVE compact station schema invalid")
        station_source, operator = row[0], row[5]
        if (not isinstance(row[3], (int, float)) or not isinstance(row[4], (int, float)) or
                not math.isfinite(row[3]) or not math.isfinite(row[4]) or
                abs(row[3]) > 90 or abs(row[4]) > 180):
            raise ValueError("REVE compact coordinates invalid")
        cpo_id = key("ES", SOURCE_ID, "cpo", operator)
        station_id = key("ES", SOURCE_ID, "station", station_source)
        cpos.setdefault(cpo_id, {"id": cpo_id, "country": "ES", "sourceOperatorId": operator,
                                 "name": operator})
        result["stations"].append({"id": station_id, "country": "ES", "cpoId": cpo_id,
                                   "sourceStationId": station_source, "name": row[1],
                                   "address": row[2], "latitude": row[3], "longitude": row[4],
                                   "networkBrand": row[11], "rawSourceFields": row})
        for compact in row[8]:
            if (not isinstance(compact, list) or len(compact) != 7 or
                    not isinstance(compact[0], str) or not compact[0] or
                    compact[2] not in {"AC", "DC"} or not isinstance(compact[5], list) or
                    not isinstance(compact[6], list)):
                raise ValueError("REVE compact EVSE/configuration schema invalid")
            source_evse = compact[0]
            power = compact[3]
            if power is not None and (not isinstance(power, (int, float)) or
                                      not math.isfinite(power) or power < 0):
                raise ValueError("REVE compact connector power invalid")
            evse_id = key("ES", SOURCE_ID, "evse", [station_source, source_evse])
            connector_id = key("ES", SOURCE_ID, "connector", [station_source, source_evse, "compact-kind-power"])
            result["evses"].append({"id": evse_id, "country": "ES", "cpoId": cpo_id,
                                    "stationId": station_id, "sourceEvseId": source_evse,
                                    "officialEvseId": source_evse if OFFICIAL_EVSE.fullmatch(source_evse) else None,
                                    "rawSourceFields": compact})
            result["connectors"].append({"id": connector_id, "evseId": evse_id,
                                         "sourceConnectorId": None, "officialConnectorId": None,
                                         "plugType": None, "kind": compact[2],
                                         "powerKw": power if power and power > 0 else None,
                                         "rawSourceFields": compact})
    result["cpos"] = sorted(cpos.values(), key=lambda item: item["id"])
    for section in ("stations", "evses", "connectors"):
        result[section].sort(key=lambda item: item["id"])
    validate(result)
    return result
