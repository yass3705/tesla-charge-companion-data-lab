#!/usr/bin/env python3
"""Build raw FR eMSP offers from archived exact-EVSE evidence only.

The national topology is copied solely to carry an exact scoped raw offer into
the prepared candidate. No tariff component is interpreted here.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v9_rebuild.canonical import key, validate


SOURCE_ID = "FR:emsp_exact"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_archive(directory: Path, electra_path: Path) -> tuple[dict, dict, str, str]:
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest.get("dataset") != "electroverse-france-evse-national-overlay" or manifest.get("country") != "FR":
        raise ValueError("Electroverse archive identity invalid")
    electroverse = defaultdict(list)
    seen_tiles = set()
    for tile in manifest.get("tiles", []):
        name = tile.get("file")
        if not isinstance(name, str) or not re.fullmatch(r"t_[0-9-]+_[0-9-]+\.json\.gz", name) or name in seen_tiles:
            raise ValueError("Electroverse tile descriptor invalid")
        seen_tiles.add(name)
        raw = (directory / name).read_bytes()
        if sha(raw) != tile.get("sha256") or len(raw) != tile.get("bytes"):
            raise ValueError("Electroverse tile integrity invalid")
        payload = json.loads(gzip.decompress(raw))
        rows = payload.get("emspOffers")
        if payload.get("country") != "FR" or not isinstance(rows, list) or len(rows) != tile.get("count"):
            raise ValueError("Electroverse tile schema or internal count invalid")
        for offer in rows:
            electroverse[offer.get("id")].append(offer)
    if len(seen_tiles) != manifest.get("tileCount"):
        raise ValueError("Electroverse tile set incomplete")
    electra_raw = electra_path.read_bytes()
    electra_payload = json.loads(electra_raw)
    if electra_payload.get("schemaVersion") != 1 or not isinstance(electra_payload.get("verifiedLinks"), list):
        raise ValueError("Electra evidence schema invalid")
    electra = defaultdict(list)
    for link in electra_payload["verifiedLinks"]:
        if not re.fullmatch(r"[a-f0-9]{64}", str(link.get("screenshotSha256") or "")) or not link.get("verifiedForPublishedSource"):
            continue
        for mapping in link.get("mappings", []):
            electra[mapping.get("chargeTariffId")].append({"mapping": mapping, "evidence": {
                "screenshotSha256": link["screenshotSha256"],
                "verifiedForPublishedSource": link["verifiedForPublishedSource"],
                "locationId": link.get("locationId")}})
    return electroverse, electra, sha(manifest_raw), sha(electra_raw)


def normalize(national: dict, report: dict, electroverse: dict, electra: dict,
              *, national_sha: str, report_sha: str, manifest_sha: str, electra_sha: str) -> dict:
    if (national.get("source", {}).get("id") != "FR:irve_static" or report.get("schemaVersion") != 1 or
            report.get("policy") != "exact_official_evse_only;no_connector_or_price_propagation"):
        raise ValueError("Exact eMSP input identity invalid")
    expected = report.get("inputs") or {}
    if expected != {"nationalSha256": national_sha, "electroverseManifestSha256": manifest_sha,
                    "electraProofSha256": electra_sha}:
        raise ValueError("Exact eMSP input SHA mismatch")
    stations = {row["id"]: row for row in national["stations"]}
    evses = {row["id"]: row for row in national["evses"]}
    cpos = {row["id"]: row for row in national["cpos"]}
    connectors = defaultdict(list)
    for row in national["connectors"]:
        connectors[row["evseId"]].append(row)
    used_stations, used_evses, used_cpos, used_connectors, offers = {}, {}, {}, {}, []
    seen = set()
    for match in report.get("matches", []):
        channel, offer_id = match.get("channel"), match.get("offerId")
        identity = (channel, offer_id, match.get("nationalEvseId"))
        if (identity in seen or channel not in {"Electra", "Electroverse"} or not all(identity) or
                match.get("nationalConnectorId") is not None):
            raise ValueError("Exact eMSP match identity invalid")
        seen.add(identity)
        evse = evses.get(match["nationalEvseId"])
        if (not evse or evse.get("officialEvseId") != match.get("officialEvseId") or
                evse.get("stationId") != match.get("nationalStationId")):
            raise ValueError("Exact eMSP match has no national EVSE")
        station = stations[evse["stationId"]]
        if channel == "Electroverse":
            variants = electroverse.get(offer_id, [])
            if (len(variants) != 1 or variants[0].get("verifiedScope") != "exact_evse" or
                    variants[0].get("metadata", {}).get("identityMode") != "exact_unique_national_irve_pdc" or
                    variants[0].get("evseIds") != [evse["officialEvseId"]]):
                raise ValueError("Electroverse archived exact proof invalid")
            raw_offer = variants[0]
        else:
            variants = electra.get(offer_id, [])
            if len(variants) != 1 or variants[0]["mapping"].get("evseId") != evse["officialEvseId"]:
                raise ValueError("Electra archived exact proof invalid")
            raw_offer = variants[0]
        used_stations[station["id"]] = station
        used_evses[evse["id"]] = evse
        used_cpos[station["cpoId"]] = cpos[station["cpoId"]]
        for connector in connectors[evse["id"]]:
            used_connectors[connector["id"]] = connector
        offers.append({"id": key("FR", SOURCE_ID, "offer", identity), "channel": channel,
                       "scope": {"evseId": evse["id"], "connectorId": None},
                       "sourceOfferId": offer_id, "officialEvseId": evse["officialEvseId"],
                       "proof": match["proof"], "rawOffer": raw_offer,
                       "calculationStatus": "not_evaluated"})
    result = {"schemaVersion": 1,
              "source": {"id": SOURCE_ID, "artifactSha256": sha((national_sha + report_sha + manifest_sha + electra_sha).encode()),
                         "rawDataset": "archived-exact-emsp-evidence", "nationalSha256": national_sha,
                         "joinReportSha256": report_sha, "electroverseManifestSha256": manifest_sha,
                         "electraProofSha256": electra_sha},
              "countries": [{"code": "FR"}],
              "cpos": sorted(used_cpos.values(), key=lambda row: row["id"]),
              "stations": sorted(used_stations.values(), key=lambda row: row["id"]),
              "evses": sorted(used_evses.values(), key=lambda row: row["id"]),
              "connectors": sorted(used_connectors.values(), key=lambda row: row["id"]),
              "offers": sorted(offers, key=lambda row: row["id"])}
    validate(result)
    return result


def build(national_path: Path, report_path: Path, archive: Path, electra_path: Path, output: Path,
          expected_report_sha: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_report_sha):
        raise ValueError("Expected exact join report SHA required")
    output = output.resolve()
    root = Path(__file__).resolve().parents[1]
    if output == root or root in output.parents:
        raise ValueError("Canonical output must stay outside checkout")
    national_raw, report_raw = national_path.read_bytes(), report_path.read_bytes()
    if sha(report_raw) != expected_report_sha:
        raise ValueError("Exact join report SHA mismatch")
    electroverse, electra, manifest_sha, electra_sha = read_archive(archive, electra_path)
    result = normalize(json.loads(national_raw), json.loads(report_raw), electroverse, electra,
                       national_sha=sha(national_raw), report_sha=sha(report_raw),
                       manifest_sha=manifest_sha, electra_sha=electra_sha)
    raw = (json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("Existing canonical eMSP artifact differs")
    if not output.exists():
        output.write_bytes(raw)
    return {"source": SOURCE_ID, "path": str(output), "sha256": sha(raw), "offers": len(result["offers"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--national", required=True, type=Path)
    parser.add_argument("--join-report", required=True, type=Path)
    parser.add_argument("--report-sha", required=True)
    parser.add_argument("--electroverse", required=True, type=Path)
    parser.add_argument("--electra", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.national, args.join_report, args.electroverse,
                           args.electra, args.out, args.report_sha)))
