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


def keymap(data: dict) -> tuple[dict, dict]:
    keys = {}
    tariffs = {}
    for station in data.get("stations") or []:
        station_id = str(station.get("stationId") or "")
        party = str(station.get("partyId") or "")
        for evse in station.get("evses") or []:
            evse_id = str(evse.get("evseId") or evse.get("uid") or "")
            for connector in evse.get("connectors") or []:
                cid = str(connector.get("id") or "")
                key = (party, station_id, evse_id, cid)
                national_refs = tuple(connector.get("tariffKeys") or [])
                if key in keys:
                    # A duplicate physical identity makes EVSE-level tariff
                    # precedence ambiguous and therefore is not suppressible.
                    raise ValueError(f"Duplicate connector identity {key}")
                keys[key] = national_refs
                if national_refs:
                    tariffs[party] = tariffs.get(party, 0) + 1
    return keys, tariffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("national_before", type=Path)
    ap.add_argument("national_after", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    before = load(args.national_before)
    after = load(args.national_after)
    pre, counts = keymap(before)
    post, _ = keymap(after)
    if set(pre) != set(post):
        missing = list(set(pre) - set(post))[:10]
        extra = list(set(post) - set(pre))[:10]
        raise AssertionError(f"Physical connector ID changed, missing={missing}, extra={extra}")
    violations = []
    fallback = collections.Counter()
    preserved = collections.Counter()
    for physical_id, national_refs in pre.items():
        actual = post[physical_id]
        party = physical_id[0]
        if national_refs:
            preserved[party] += 1
            if actual != national_refs:
                violations.append({
                    "partyId": party, "stationId": physical_id[1],
                    "evseId": physical_id[2], "connectorId": physical_id[3],
                    "nationalTariffKeys": list(national_refs),
                    "afterOverlayKeys": list(actual),
                })
        elif actual:
            fallback[party] += 1
    result = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "country": "NL",
        "preSource": str(args.national_before),
        "postSource": str(args.national_after),
        "scopeConnectors": len(pre),
        "originalNationalTariffConnectorsByCpo": dict(sorted(preserved.items())),
        "onlyMissingTariffConnectorsFilledByCpo": dict(sorted(fallback.items())),
        "totalNationalKeysPreserved": sum(preserved.values()),
        "fallbackConnectors": sum(fallback.values()),
        "overrideViolations": len(violations),
        "violationSamples": violations[:25],
        "policy": "DOT-NL all CPOs canonical: original national connector tariff keys MUST stay unchanged. Direct operator overlays may fill absent only, not replace present national tariffs."
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({
        "connectors": len(pre), "nationalTariffsPreserved": sum(preserved.values()),
        "missingOnlyFilled": sum(fallback.values()),
        "perCpoFallback": dict(sorted(fallback.items())),
        "overrideViolations": len(violations)
    }, ensure_ascii=False, indent=2))
    if violations:
        raise AssertionError(f"{len(violations)} original national tariffs were overwritten! Examples: {violations[:5]}")


if __name__ == "__main__":
    main()
