"""Preserve the pinned Bump IRVE points and the historically compiled EVSE offers.

The IRVE point is an official EVSE identity. It does not establish an individual
connector ID or type, so prices remain unevaluated until Production proves the
connector relation and replays the archived full-session oracle.
"""
from __future__ import annotations

import math
import re

from v9_rebuild.canonical import SCHEMA_VERSION, key, validate

SOURCE_ID = "FR:bump_direct_exact"


def normalize_bump_exact(payload: dict, *, artifact_sha256: str) -> dict:
    source, compiled = payload.get("source"), payload.get("compiled")
    if (not isinstance(source, dict) or not isinstance(compiled, dict) or
            source.get("country") != "FR" or source.get("operator") != "Bump" or
            source.get("dataset") != "bump-direct-tariffs-tcc-france" or
            compiled.get("mode") != "operator-direct-exact-evse" or
            compiled.get("sourceEvidence", {}).get("sourceGeneratedAt") != source.get("sourceGeneratedAt") or
            not isinstance(source.get("stations"), list) or
            not isinstance(compiled.get("directOffers"), list) or
            not isinstance(compiled.get("quarantinedSourceRankableEvse"), list) or
            not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256 or "")):
        raise ValueError("Bump pinned source/compiled contract invalid")
    source_points = {point.get("idPdcItinerance"): point
                     for station in source["stations"] for point in station.get("points", [])}
    if (len(source_points) != sum(len(station.get("points", [])) for station in source["stations"]) or
            None in source_points):
        raise ValueError("Bump source EVSE identity collision")
    rankable = {identity for identity, point in source_points.items() if point.get("rankable") is True}
    offered = [identity for offer in compiled["directOffers"] for identity in offer.get("evseIds", [])]
    quarantined = [row.get("evseId") for row in compiled["quarantinedSourceRankableEvse"]]
    if (len(offered) != len(set(offered)) or len(quarantined) != len(set(quarantined)) or
            set(offered) & set(quarantined) or set(offered) | set(quarantined) != rankable or
            any(offer.get("verifiedScope") != "exact_evse" or offer.get("currency") != "EUR" or
                offer.get("pricing", {}).get("type") != "rules" for offer in compiled["directOffers"])):
        raise ValueError("Bump compiled offer exact scope or completeness invalid")
    cpo = key("FR", SOURCE_ID, "cpo", "Bump")
    result = {"schemaVersion": SCHEMA_VERSION,
              "source": {"id": SOURCE_ID, "artifactSha256": artifact_sha256,
                         "sourceArtifactSha256": payload.get("sourceArtifactSha256"),
                         "compiledArtifactSha256": payload.get("compiledArtifactSha256"),
                         "generatedAt": source.get("sourceGeneratedAt"),
                         "rawDataset": source.get("dataset")},
              "countries": [{"code": "FR"}],
              "cpos": [{"id": cpo, "country": "FR", "sourceOperatorId": "Bump", "name": "Bump"}],
              "stations": [], "evses": [], "connectors": [], "offers": []}
    seen_stations = set()
    for row in source["stations"]:
        sid, lat, lon = row.get("stationId"), row.get("latitude"), row.get("longitude")
        if (not isinstance(sid, str) or not sid or sid in seen_stations or
                not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                        for v in (lat, lon)) or abs(lat) > 90 or abs(lon) > 180):
            raise ValueError("Bump station identity or coordinates invalid")
        seen_stations.add(sid)
        station_id = key("FR", SOURCE_ID, "station", sid)
        result["stations"].append({"id": station_id, "country": "FR", "cpoId": cpo,
                                   "sourceStationId": sid, "name": row.get("name"),
                                   "address": row.get("address"), "latitude": lat,
                                   "longitude": lon, "networkBrand": "Bump",
                                   "rawSourceFields": {k: v for k, v in row.items() if k != "points"}})
        for point in row.get("points", []):
            source_evse = point["idPdcItinerance"]
            result["evses"].append({"id": key("FR", SOURCE_ID, "evse", source_evse),
                                    "country": "FR", "cpoId": cpo, "stationId": station_id,
                                    "sourceEvseId": source_evse, "officialEvseId": source_evse,
                                    "identityGranularity": "archived_irve_pdc",
                                    "powerKw": point.get("powerKw"), "rawSourceFields": point})
    for offer in compiled["directOffers"]:
        for source_evse in offer["evseIds"]:
            result["offers"].append({"id": key("FR", SOURCE_ID, "offer", [offer["id"], source_evse]),
                                      "channel": "Direct",
                                      "scope": {"evseId": key("FR", SOURCE_ID, "evse", source_evse),
                                                "connectorId": None},
                                      "sourceEvseId": source_evse,
                                      "rawOffer": {"compiledOffer": offer, "sourcePoint": source_points[source_evse]},
                                      "calculationStatus": "not_evaluated"})
    for section in ("stations", "evses", "offers"):
        result[section].sort(key=lambda row: row["id"])
    validate(result)
    return result
