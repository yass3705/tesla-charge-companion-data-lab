"""Preserve the archived national German site/EVSE inventory without pricing it.

The catalog's site maximum is not a connector power. AFIR and direct-CPO
staging tariffs remain in rawSourceFields until their exact scope is migrated.
"""
from __future__ import annotations

import math
import re

from v9_rebuild.canonical import SCHEMA_VERSION, key, validate

SOURCE_ID = "DE:bnetza_afir_archive"


def normalize_germany_catalog(payload: dict, *, artifact_sha256: str) -> dict:
    if (not isinstance(payload, dict) or payload.get("schemaVersion") != "0.6.0" or
            payload.get("dataset") != "germany-national-non-tesla-catalog-staging-direct-cpo" or
            payload.get("countryCode") != "DE" or not isinstance(payload.get("sites"), list) or
            not isinstance(payload.get("scope"), dict) or
            payload["scope"].get("bnetzaIsNationalBaseline") is not True or
            not isinstance(artifact_sha256, str) or
            not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256)):
        raise ValueError("German national archive envelope invalid")
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": SOURCE_ID, "artifactSha256": artifact_sha256,
                         "generatedAt": payload.get("generatedAt"),
                         "rawEnvelope": {k: v for k, v in payload.items() if k != "sites"}},
              "countries": [{"code": "DE"}], "cpos": [], "stations": [],
              "evses": [], "connectors": [], "offers": []}
    cpos, seen = {}, set()
    for row in payload["sites"]:
        if not isinstance(row, dict):
            raise ValueError("German national site invalid")
        sid, coords = row.get("id"), row.get("coordinates")
        if (row.get("countryCode") != "DE" or not isinstance(sid, str) or
                not sid.startswith("bnetza-site:") or sid in seen or not isinstance(coords, dict)):
            raise ValueError("German national station identity invalid")
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) or
               not math.isfinite(v) or abs(v) > maximum for v, maximum in [(lat, 90), (lon, 180)]):
            raise ValueError("German national coordinates invalid")
        identifiers = row.get("evseIds")
        if not isinstance(identifiers, list) or any(not isinstance(v, str) or not v.strip() for v in identifiers):
            raise ValueError("German national EVSE identities invalid")
        operator = row.get("operator")
        if operator is not None and not isinstance(operator, str):
            raise ValueError("German national operator invalid")
        seen.add(sid)
        cpo_id, station_id = key("DE", SOURCE_ID, "cpo", operator), key("DE", SOURCE_ID, "station", sid)
        cpos.setdefault(cpo_id, {"id": cpo_id, "country": "DE",
                                "sourceOperatorId": operator, "name": operator})
        result["stations"].append({"id": station_id, "country": "DE", "cpoId": cpo_id,
                                   "sourceStationId": sid, "name": None,
                                   "address": row.get("address"), "latitude": lat, "longitude": lon,
                                   "rawSourceFields": row})
        # No power, connector or tariff is propagated from the station to an EVSE.
        # A repeated ID in different source sites remains explicitly site-scoped.
        for eid in sorted(set(identifiers)):
            result["evses"].append({"id": key("DE", SOURCE_ID, "evse", [sid, eid]),
                                    "country": "DE", "cpoId": cpo_id, "stationId": station_id,
                                    "sourceEvseId": eid, "officialEvseId": eid,
                                    "identityGranularity": "source_evse"})
    result["cpos"] = sorted(cpos.values(), key=lambda r: r["id"])
    for section in ("stations", "evses"):
        result[section].sort(key=lambda r: r["id"])
    validate(result)
    return result
