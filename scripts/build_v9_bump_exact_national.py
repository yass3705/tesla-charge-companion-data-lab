#!/usr/bin/env python3
"""Copy only Bump offers with an exact official national EVSE identity.

No station, geographic, power or name fallback is permitted. The copied offer
remains raw and cannot enter session ranking until its complete pricing is
checked against the archived runtime oracles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v9_rebuild.canonical import key, validate

SOURCE_ID = "FR:bump_national_exact"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalize(national: dict, bump: dict, *, national_sha: str, bump_sha: str) -> dict:
    if (national.get("source", {}).get("id") != "FR:irve_static" or
            bump.get("source", {}).get("id") != "FR:bump_direct_exact"):
        raise ValueError("Bump exact join source identity invalid")
    national_cpos = {row["id"]: row for row in national["cpos"]}
    national_stations = {row["id"]: row for row in national["stations"]}
    official = {}
    for evse in national["evses"]:
        identity = evse.get("officialEvseId")
        if identity:
            official.setdefault(identity, []).append(evse)
    bump_evses = {row["id"]: row for row in bump["evses"]}
    used_stations, used_evses, used_cpos, used_connectors, offers = {}, {}, {}, {}, []
    connectors = {}
    for connector in national["connectors"]:
        connectors.setdefault(connector["evseId"], []).append(connector)
    for offer in bump["offers"]:
        source_evse = bump_evses.get(offer.get("scope", {}).get("evseId"))
        identity = offer.get("sourceEvseId")
        if (not source_evse or source_evse.get("officialEvseId") != identity or
                offer.get("channel") != "Direct" or
                offer.get("scope", {}).get("connectorId") is not None):
            raise ValueError("Bump offer source EVSE scope invalid")
        matches = official.get(identity, [])
        if len(matches) != 1:
            continue
        evse = matches[0]
        station = national_stations[evse["stationId"]]
        cpo = national_cpos[station["cpoId"]]
        if cpo.get("sourceOperatorId") != "BUMP":
            continue
        used_stations[station["id"]] = station
        used_evses[evse["id"]] = evse
        used_cpos[cpo["id"]] = cpo
        for connector in connectors.get(evse["id"], []):
            used_connectors[connector["id"]] = connector
        offers.append({"id": key("FR", SOURCE_ID, "offer", [identity, offer["id"]]),
                       "channel": "Direct", "scope": {"evseId": evse["id"], "connectorId": None},
                       "officialEvseId": identity, "sourceOfferId": offer["id"],
                       "rawOffer": offer["rawOffer"], "calculationStatus": "not_evaluated"})
    result = {"schemaVersion": 1,
              "source": {"id": SOURCE_ID, "artifactSha256": sha((national_sha + ':' + bump_sha).encode()),
                         "rawDataset": "archived-bump-exact-national-evse",
                         "nationalSha256": national_sha, "bumpCanonicalSha256": bump_sha},
              "countries": [{"code": "FR"}],
              "cpos": sorted(used_cpos.values(), key=lambda row: row["id"]),
              "stations": sorted(used_stations.values(), key=lambda row: row["id"]),
              "evses": sorted(used_evses.values(), key=lambda row: row["id"]),
              "connectors": sorted(used_connectors.values(), key=lambda row: row["id"]),
              "offers": sorted(offers, key=lambda row: row["id"])}
    validate(result)
    return result


def build(national_path: Path, bump_path: Path, output: Path) -> dict:
    root = Path(__file__).resolve().parents[1]
    output = output.resolve()
    if output == root or root in output.parents:
        raise ValueError("Bump join output must stay outside Git checkout")
    national_raw, bump_raw = national_path.read_bytes(), bump_path.read_bytes()
    result = normalize(json.loads(national_raw), json.loads(bump_raw),
                       national_sha=sha(national_raw), bump_sha=sha(bump_raw))
    raw = (json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("Existing Bump join artifact differs")
    if not output.exists():
        output.write_bytes(raw)
    return {"source": SOURCE_ID, "sha256": sha(raw), "matchedOffers": len(result["offers"]),
            "path": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--national", required=True, type=Path)
    parser.add_argument("--bump", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.national, args.bump, args.out)))
