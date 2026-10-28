"""Preserve archived Allego France EVSE identities and raw direct offers.

The archive has EVSE-level power/kind, but no connector identity. No connector,
official connector ID, tariff calculation or station-wide price is inferred.
"""
from __future__ import annotations

import math
import re

from v9_rebuild.canonical import SCHEMA_VERSION, key, validate

SOURCE_ID = "FR:allego_direct"


def normalize_allego_fr(payload: dict, *, artifact_sha256: str) -> dict:
    if (not isinstance(payload, dict) or payload.get("country") != "FR" or
            payload.get("operator") != "Allego" or
            not isinstance(payload.get("stations"), list) or
            not isinstance(artifact_sha256, str) or
            not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256)):
        raise ValueError("Allego France archive envelope invalid")
    cpo_id = key("FR", SOURCE_ID, "cpo", "Allego")
    out = {"schemaVersion": SCHEMA_VERSION,
           "source": {"id": SOURCE_ID, "artifactSha256": artifact_sha256,
                      "generatedAt": payload.get("generatedAt"),
                      "rawDataset": payload.get("dataset")},
           "countries": [{"code": "FR"}],
           "cpos": [{"id": cpo_id, "country": "FR", "sourceOperatorId": "Allego", "name": "Allego"}],
           "stations": [], "evses": [], "connectors": [], "offers": []}
    seen_stations, seen_evses = set(), set()
    for station in payload["stations"]:
        if not isinstance(station, dict):
            raise ValueError("Allego station row invalid")
        source_station, coords = station.get("stationId"), station.get("coordinates")
        if (not isinstance(source_station, str) or not source_station or source_station in seen_stations or
                not isinstance(coords, list) or len(coords) != 2 or
                any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
                    for v in coords) or abs(coords[0]) > 90 or abs(coords[1]) > 180 or
                not isinstance(station.get("evses"), list)):
            raise ValueError("Allego station identity or coordinates invalid")
        seen_stations.add(source_station)
        station_id = key("FR", SOURCE_ID, "station", source_station)
        out["stations"].append({"id": station_id, "country": "FR", "cpoId": cpo_id,
                                "sourceStationId": source_station, "name": station.get("name"),
                                "address": station.get("address"), "latitude": coords[0],
                                "longitude": coords[1], "networkBrand": "Allego",
                                "rawSourceFields": {k: v for k, v in station.items() if k != "evses"}})
        for evse in station["evses"]:
            if not isinstance(evse, dict):
                raise ValueError("Allego EVSE row invalid")
            source_evse = evse.get("evseId")
            if (not isinstance(source_evse, str) or not source_evse or source_evse in seen_evses or
                    evse.get("stationId") != source_station):
                raise ValueError("Allego EVSE identity collision or station mismatch")
            seen_evses.add(source_evse)
            evse_id = key("FR", SOURCE_ID, "evse", source_evse)
            out["evses"].append({"id": evse_id, "country": "FR", "cpoId": cpo_id,
                                 "stationId": station_id, "sourceEvseId": source_evse,
                                 "officialEvseId": source_evse,
                                 "identityGranularity": "archived_irve_evse",
                                 "rawSourceFields": evse})
            if evse.get("priceTextPresent") is True or evse.get("directEurPerKwh") is not None:
                out["offers"].append({"id": key("FR", SOURCE_ID, "offer", source_evse),
                                      "channel": "Direct", "scope": {"evseId": evse_id, "connectorId": None},
                                      "rawOffer": {"directEurPerKwh": evse.get("directEurPerKwh"),
                                                   "feePolicy": evse.get("feePolicy"),
                                                   "conditionalOffers": evse.get("conditionalOffers"),
                                                   "rankableDirectInArchive": evse.get("rankableDirect"),
                                                   "sourceEvseId": source_evse},
                                      "calculationStatus": "not_evaluated"})
    for name in ("stations", "evses", "offers"):
        out[name].sort(key=lambda row: row["id"])
    validate(out)
    return out
