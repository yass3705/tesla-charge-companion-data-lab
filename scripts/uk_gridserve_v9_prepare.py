#!/usr/bin/env python3
"""Public-only Gridserve OCPI PCPR -> TCC V9 exact-connector dataset.
No tariff estimation, no private/depot/test locations, no removed EVSE.
"""
from __future__ import annotations

import collections
import copy
import gzip
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCATION_SOURCE = ROOT / "data/national/uk_gridserve_pcpr_locations.json.gz"
TARIFF_SOURCE = ROOT / "data/national/uk_gridserve_pcpr_tariffs.json.gz"
DATA_OUT = ROOT / "data/national/uk_gridserve_v9.json.gz"
CROSSWALK_OUT = ROOT / "reports/uk/gridserve-v9-connector-crosswalk.json.gz"
AUDIT_OUT = ROOT / "reports/uk/gridserve-v9-integration-latest.json"

# Concrete private fleet and retired locations from the 2026-10-02
# Gridserve PCPR missing tariff investigation (no guessing on prices).
BLOCKED_LOCATION_IDS = {
    "297345e2-08c2-4878-89b9-5fdac09df322", # live testing
    "351ae22f-3c3f-418e-8ee6-18bc2ed78f86", # Network Rail Bristol
    "6a3e96a7-d7ec-4c9d-b004-4a0983e897d5", # EF fleet depot Enfield
    "75b843b0-4a06-4715-83c9-5636bdc38a4c", # EF fleet depot Sunderland
    "94b71d1a-5ca2-4dbb-abef-8a9c5a2c033f", # Network Rail Swindon
    "951bcb0b-7162-458e-9fd2-5de1fa00469b", # EF fleet depot Leeds
    "d2d20832-2243-424e-b8bf-f2c79fe99211", # EF fleet depot Derby
    "1b16f98b-4975-410d-a2e3-551e8784a263", # retired station graveyard
    "b50a2d70-3276-4539-9cc7-3a5be39d76c3", # IVER HQ private
}

# Match unequivocal non-public indicators; do not exclude public retail sites
# merely because of a commercial operator or a generic "parking lot".
NONPUBLIC_NAME = re.compile(
    r"(^[_\s]*live testing\b|^[_\s]*retired\b|^EF\s*[-–]\s*DEPOT\b|"
    r"^Network Rail\s*[-–]\s*|"
    r"\b(?:staff only|employees only|private charging|private depot|"
    r"fleet depot|internal test|not for public use|restricted access)\b|"
    r"\bHQ\s*$)",
    re.I,
)
KNOWN_LEGACY_TARIFF_IDS = {"A0-GBP", "GS1", "GS3", "GS9"}
PUBLIC_CURRENCIES = {"GBP"}

def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)

def write_gz(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", compresslevel=9, mtime=0, fileobj=buf) as stream:
        stream.write(serialized)
    path.write_bytes(buf.getvalue())

def exact_tariff_map(tariffs):
    result = {}
    for tariff in tariffs:
        if not isinstance(tariff, dict):
            continue
        tid = str(tariff.get("id") or "").strip()
        if not tid:
            continue
        assert tariff.get("country_code") == "GB", f"Non-GB tariff {tid}"
        assert str(tariff.get("currency", "")).upper() in PUBLIC_CURRENCIES, f"Currency for {tid}"
        # Tariff identifiers are only safe in the runtime adapter if unique.
        assert tid not in result, f"Ambiguous duplicate tariff ID {tid}"
        elements = tariff.get("elements") or []
        assert isinstance(elements, list) and elements, f"No components for {tid}"
        for element in elements:
            pcs = element.get("price_components") or []
            assert pcs, f"No components for {tid}"
            for pc in pcs:
                assert pc.get("type") in ("ENERGY", "TIME", "FLAT", "PARKING_TIME"), f"Unknown component: {tid}"
                assert isinstance(pc.get("price"), (int, float)) and pc["price"] >= 0, f"Invalid {tid}"
        result[tid] = tariff
    return result

def private_reason(loc):
    if str(loc.get("id") or "") in BLOCKED_LOCATION_IDS:
        return "known_nonpublic_or_retired_location"
    if loc.get("publish") is not True:
        return "not_explicitly_published"
    if str(loc.get("country_code") or "").upper() != "GB":
        return "outside_GB"
    if str(loc.get("parking_type") or "").upper() in {"PRIVATE", "RESTRICTED", "CUSTOMER_ONLY", "STAFF_ONLY"}:
        return "restricted_parking"
    label = str(loc.get("name") or "")
    if NONPUBLIC_NAME.search(label):
        return "explicit_nonpublic_name"
    # No broad inference from facilities / non-24-7 opening hours.
    coord = loc.get("coordinates") or {}
    try:
        lat, lon = float(coord["latitude"]), float(coord["longitude"])
        if not (49 <= lat <= 61 and -9 <= lon <= 3):
            return "out_of_uk_bounds"
    except (KeyError, TypeError, ValueError):
        return "invalid_coordinates"
    return None

def build(locdoc, tardoc):
    tariff_map = exact_tariff_map(tardoc["tariffs"])
    rejected = collections.Counter()
    retained, links = [], []
    referenced = collections.Counter()
    unpriced = collections.Counter()
    retained_tariffs = set()
    connector_keys = set()
    all_input_evse = sum(len(loc.get("evses") or []) for loc in locdoc["locations"])
    all_input_connectors = sum(len(evse.get("connectors") or []) for loc in locdoc["locations"] for evse in loc.get("evses") or [])
    evse_count = connector_count = priced_count = 0
    for original in locdoc["locations"]:
        reason = private_reason(original)
        if reason:
            rejected[reason] += 1
            continue
        loc = copy.deepcopy(original)
        new_evses = []
        for evse in loc.get("evses") or []:
            if str(evse.get("status") or "").upper() == "REMOVED":
                rejected["removed_evse"] += 1
                continue
            eid = str(evse.get("uid") or evse.get("evse_id") or "").strip()
            assert eid, f"Missing Gridserve EVSE id in {loc['id']}"
            kept_connections = []
            for connector in evse.get("connectors") or []:
                cid = str(connector.get("id") or "").strip()
                assert cid, f"Missing connector ID {loc['id']}/{eid}"
                physical_key = (str(loc["id"]), eid, cid)
                assert physical_key not in connector_keys, f"Duplicate physical connector {physical_key}"
                connector_keys.add(physical_key)
                tariff_ids = [str(t) for t in connector.get("tariff_ids") or [] if t is not None]
                assert len(tariff_ids) == len(set(tariff_ids)), f"Repeated connector tariff: {physical_key}"
                found = [t for t in tariff_ids if t in tariff_map]
                missing = [t for t in tariff_ids if t not in tariff_map]
                if missing:
                    # Never publish an unknown public tariff ID. Known legacy IDs
                    # remain unpriced, and MUST NOT resolve to a retail tariff.
                    unknown = set(missing) - KNOWN_LEGACY_TARIFF_IDS
                    assert not unknown, f"New unmatched public Gridserve tariff IDs {unknown} at {physical_key}"
                    unpriced["known_legacy_unmapped"] += 1
                elif not tariff_ids:
                    unpriced["no_tariff_reference"] += 1
                for tid in found:
                    assert tariff_map[tid].get("party_id") == loc.get("party_id"), (
                        f"Tariff owner mismatch {physical_key}: {tid}"
                    )
                    referenced[tid] += 1
                    retained_tariffs.add(tid)
                if found:
                    priced_count += 1
                # If any tariff reference is ambiguous, DO NOT price this connector.
                safe = not missing
                next_connector = copy.deepcopy(connector)
                if not safe:
                    next_connector["tariff_ids"] = []
                kept_connections.append(next_connector)
                links.append({
                    "locationId": str(loc["id"]), "evseUid": eid,
                    "connectorId": cid, "maxElectricPowerW": connector.get("max_electric_power"),
                    "tariffIds": found if safe else [], "originalTariffIds": tariff_ids,
                    "priceVerified": bool(found and safe),
                    "unpricedReason": "unmapped_tariff_id" if missing else ("no_reference" if not found else None),
                })
                connector_count += 1
            if kept_connections:
                e = copy.deepcopy(evse)
                e["connectors"] = kept_connections
                new_evses.append(e)
                evse_count += 1
        if new_evses:
            loc["evses"] = new_evses
            retained.append(loc)
        else:
            rejected["no_nonremoved_evse"] += 1
    assert len(retained) >= 100, f"Gridserve coverage dropped: {len(retained)} locations"
    assert evse_count >= 1000 and connector_count >= 1000, "Gridserve EVSE/connector coverage regression"
    assert priced_count >= 1000, f"Insufficient exact connector prices: {priced_count}"
    assert retained_tariffs, "No exact Gridserve direct tariffs"
    # Re-check absence of non-public locations and connectors with invented prices.
    assert all(private_reason(loc) is None for loc in retained)
    output = {
        "country": "GB", "collectedAt": locdoc["collectedAt"],
        "source": "GRIDSERVE PCPR exact connector public subset",
        "sources": [{
            "id": "gridserve-pcpr-direct", "name": "GRIDSERVE", "country": "GB",
            "pricingScope": "cpo_direct_exact_connector",
            "locations": retained,
            "tariffs": [tariff_map[t] for t in sorted(retained_tariffs)],
        }],
    }
    report = {
        "provider": "GRIDSERVE", "country": "GB", "status": "validated_public_connector_exact",
        "collectedAt": locdoc["collectedAt"], "sourceSnapshotAt": tardoc["collectedAt"],
        "inputLocations": len(locdoc["locations"]), "inputEvses": all_input_evse,
        "inputConnectors": all_input_connectors,
        "publicLocations": len(retained), "publicEvses": evse_count,
        "publicConnectors": connector_count,
        "exactPricedConnectors": sum(link["priceVerified"] for link in links),
        "unpricedPublicConnectors": sum(not link["priceVerified"] for link in links),
        "distinctExactTariffIds": len(retained_tariffs),
        "exactTariffConnectorCounts": dict(sorted(referenced.items())),
        "excludedCounts": dict(sorted(rejected.items())),
        "unpricedReasons": dict(sorted(unpriced.items())),
        "publicUnmappedTariffReferences": sorted({tid for link in links for tid in link["originalTariffIds"] if tid not in tariff_map}),
        "crosswalkPath": str(CROSSWALK_OUT.relative_to(ROOT)),
        "runtimePath": str(DATA_OUT.relative_to(ROOT)),
        "tariffPolicy": "direct CPO OCPI tariff_ids only; exact connector; GBP; ambiguous remain unpriced",
        "accessPolicy": "explicitly published UK only; known depots, rail fleets, internal tests, headquarters, retired and explicitly restricted access excluded",
        "validatedForV9": True,
    }
    return output, {"provider": "GRIDSERVE", "collectedAt": locdoc["collectedAt"], "links": links}, report

def main():
    locdoc, tardoc = read_gz(LOCATION_SOURCE), read_gz(TARIFF_SOURCE)
    assert locdoc["collectedAt"] == tardoc["collectedAt"], "Locations and tariffs collected at different times"
    output, crosswalk, report = build(locdoc, tardoc)
    write_gz(DATA_OUT, output)
    write_gz(CROSSWALK_OUT, crosswalk)
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
