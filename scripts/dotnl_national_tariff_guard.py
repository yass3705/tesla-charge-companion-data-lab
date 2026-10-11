#!/usr/bin/env python3
"""Assert that non-Tesla NL national CPO tariff references survive operator overlays.

The exact DOT-NL connector tariff is the canonical reference for every CPO,
even when REGULAR or type is omitted. Independent CPO API overlays are fallback
for wholly missing national price links only. This guard rejects any changes
to existing original tariff key arrays, including illegal eMSP substitutions.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path


def load(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf8") as f:
        return json.load(f)


def keymap(data: dict) -> tuple[dict, dict, int]:
    # Some DOT-NL stations contain duplicate (station, EVSE, connector) IDs.
    # Retain every physical record as an occurrence, instead of assuming
    # unique IDs and wrongly rejecting the entire national snapshot.
    keys = collections.defaultdict(list)
    tariffs = collections.Counter()
    record_count = 0
    for station in data.get("stations") or []:
        station_id = str(station.get("stationId") or "")
        party = str(station.get("partyId") or "")
        for evse in station.get("evses") or []:
            evse_id = str(evse.get("evseId") or evse.get("uid") or "")
            for connector in evse.get("connectors") or []:
                cid = str(connector.get("id") or "")
                key = (party, station_id, evse_id, cid)
                original_refs = tuple(connector.get("tariffKeys") or [])
                keys[key].append(original_refs)
                record_count += 1
                if original_refs:
                    tariffs[party] += 1
    return dict(keys), dict(tariffs), record_count

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("national_before", type=Path)
    ap.add_argument("national_after", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    before = load(args.national_before)
    after = load(args.national_after)
    pre, counts, source_records = keymap(before)
    post, _, final_records = keymap(after)
    if set(pre) != set(post):
        missing = list(set(pre) - set(post))[:10]
        extra = list(set(post) - set(pre))[:10]
        raise AssertionError(f"Physical connector ID changed, missing={missing}, extra={extra}")
    violations = []
    fallback = collections.Counter()
    preserved = collections.Counter()
    duplicate_physical_keys = 0
    for physical_id, national_rows in pre.items():
        # Compare the *multiset* of national tariffs for duplicate identities.
        # This catches overwrite of any occurrence, without mistaking
        # pre-existing duplicated IDs for corruption.
        actual_rows = post[physical_id]
        party = physical_id[0]
        if len(national_rows) != len(actual_rows):
            violations.append({"partyId": party, "stationId": physical_id[1],
               "evseId": physical_id[2], "connectorId": physical_id[3],
               "reason": "physical_connector_occurrence_count_changed"})
            continue
        if len(national_rows) > 1:
            duplicate_physical_keys += 1
        national_refs = collections.Counter(national_rows)
        actual_refs = collections.Counter(actual_rows)
        for refs, count in national_refs.items():
            if refs:
                preserved[party] += count
                if actual_refs[refs] < count:
                    violations.append({
                      "partyId": party, "stationId": physical_id[1],
                      "evseId": physical_id[2], "connectorId": physical_id[3],
                      "nationalTariffKeys": list(refs),
                      "preservedOccurrences": actual_refs[refs],
                      "expectedOccurrences": count,
                      "reason": "original_dotnl_tariff_occurrence_lost"
                    })
        if not national_refs.get((),0):
            continue
        # Count supplementary prices only where source had empty references.
        # If an originally blank connector now has a price, it is an allowed
        # exact CPO fallback rather than a DOT-NL price substitution.
        prior_empty = national_refs[()]
        now_empty = actual_refs[()]
        fallback[party] += max(0, prior_empty - now_empty)
    result = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "country": "NL",
        "preSource": str(args.national_before),
        "postSource": str(args.national_after),
        "scopeConnectors": source_records,
        "sourceUniquePhysicalConnectorKeys": len(pre),
        "duplicatePhysicalConnectorKeys": duplicate_physical_keys,
        "originalNationalTariffConnectorsByCpo": dict(sorted(preserved.items())),
        "onlyMissingTariffConnectorsFilledByCpo": dict(sorted(fallback.items())),
        "totalNationalKeysPreserved": sum(preserved.values()),
        "fallbackConnectors": sum(fallback.values()),
        "overrideViolations": len(violations),
        "sourceConnectorRecordCountEqualsFinal": source_records == final_records,
        "violationSamples": violations[:25],
        "policy": "DOT-NL all CPOs canonical: original national connector tariff keys MUST stay unchanged. Direct operator overlays may fill absent only, not replace present national tariffs."
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({
        "connectors": source_records, "duplicatePhysicalKeys": duplicate_physical_keys,
        "nationalTariffsPreserved": sum(preserved.values()),
        "missingOnlyFilled": sum(fallback.values()),
        "perCpoFallback": dict(sorted(fallback.items())),
        "overrideViolations": len(violations)
    }, ensure_ascii=False, indent=2))
    if source_records != final_records:
        raise AssertionError("Source/final connector record count changed")
    if violations:
        raise AssertionError(f"{len(violations)} original national tariffs were overwritten! Examples: {violations[:5]}")


if __name__ == "__main__":
    main()
