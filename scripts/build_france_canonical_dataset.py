#!/usr/bin/env python3
"""Build the canonical France public-charging tariff snapshot for Tesla Charge Companion.

The build is intentionally non-destructive: source regional/operator/station JSON files
remain authoritative evidence. This script assembles them into one deterministic,
standalone JSON snapshot with explicit precedence and unresolved-gap rules.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data/national/france_public_charging_canonical.json"
OVERRIDES = ROOT / "data/regional_coverage/manual_status_overrides_2026_08_22.json"
BOURGES = ROOT / "data/station_verifications/modulo_bourges_maurice_roy_adhoc_2026_08_22.json"

EXPECTED_GAPS = [
    "Brest Métropole / Easy Charge Service live app price",
    "Prise de Nice direct public/ad-hoc tariff",
    "Mayenne e-Totem rollout visibility/tariff",
    "Sarthe IRVE rapid live app tariff",
    "SDE2A/Andà direct tariff",
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid JSON: {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object: {path.relative_to(ROOT)}")
    return payload


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def france_relevant(payload: dict[str, Any]) -> bool:
    """Exclude explicitly non-French source files; retain legacy files with no country field."""
    country = payload.get("country")
    if country is None:
        return True
    return str(country).strip().lower() in {"fr", "france"}


def source_entry(path: Path, *, include_payload: bool) -> dict[str, Any]:
    payload = load_json(path)
    item: dict[str, Any] = {
        "sourcePath": rel(path),
        "dataset": payload.get("dataset"),
        "schemaVersion": payload.get("schemaVersion"),
        "country": payload.get("country"),
        "region": payload.get("region"),
        "department": payload.get("department"),
        "operator": payload.get("operator") or payload.get("network"),
        "authority": payload.get("authority"),
        "generatedAt": payload.get("generatedAt"),
        "verifiedAt": payload.get("verifiedAt"),
        "publicationStatus": payload.get("publicationStatus"),
    }
    item = {k: v for k, v in item.items() if v is not None}
    if include_payload:
        item["payload"] = payload
    return item


def collect(directory: Path, *, exclude: set[str] | None = None, include_payload: bool = True) -> list[dict[str, Any]]:
    exclude = exclude or set()
    result: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), key=lambda p: p.name.casefold()):
        if path.name in exclude:
            continue
        payload = load_json(path)
        if not france_relevant(payload):
            continue
        result.append(source_entry(path, include_payload=include_payload))
    return result


def validate_inputs(overrides: dict[str, Any]) -> None:
    gaps = overrides.get("remainingTrueGaps")
    if gaps != EXPECTED_GAPS:
        raise SystemExit(
            "remainingTrueGaps changed unexpectedly. "
            f"Expected exactly {EXPECTED_GAPS!r}, got {gaps!r}"
        )

    override_rows = overrides.get("overrides")
    if not isinstance(override_rows, list) or not override_rows:
        raise SystemExit("Manual override layer has no overrides")

    for row in override_rows:
        path_value = row.get("regionalFile")
        if not path_value:
            raise SystemExit(f"Override row missing regionalFile: {row!r}")
        path = ROOT / path_value
        if not path.exists():
            raise SystemExit(f"Override references missing regional file: {path_value}")

    bourges = load_json(BOURGES)
    if bourges.get("publicationStatus") != "manual_verified_corrected":
        raise SystemExit("Bourges corrected evidence is not marked manual_verified_corrected")
    periods = bourges["nonSubscriber"]["periods"]
    daytime = next(p for p in periods if p["start"] == "07:00" and p["end"] == "20:00")
    if daytime.get("energyEurPerKwh") != 0.51:
        raise SystemExit("Bourges regression: daytime non-subscriber energy must be 0.51 EUR/kWh")
    fee = daytime.get("timeFee", {})
    if fee.get("firstHours") != 4 or fee.get("firstHoursEurPerHour") != 0.0 or fee.get("afterFirstHoursEurPerHour") != 1.56:
        raise SystemExit("Bourges regression: daytime time rule must be 4 h free then 1.56 EUR/h")
    member_daytime = next(
        p for p in bourges["subscriber"]["periods"]
        if p["start"] == "07:00" and p["end"] == "20:00"
    )
    member_fee = member_daytime.get("timeFee", {})
    if member_daytime.get("energyEurPerKwh") != 0.40 or member_fee.get("afterFirstHoursEurPerHour") != 1.20:
        raise SystemExit("Bourges regression: member daytime must be 0.40 EUR/kWh then 1.20 EUR/h after 4 h")


def build() -> dict[str, Any]:
    overrides = load_json(OVERRIDES)
    validate_inputs(overrides)

    regional = collect(
        ROOT / "data/regional_coverage",
        exclude={OVERRIDES.name},
        include_payload=True,
    )
    operator_direct = collect(ROOT / "data/operator_direct", include_payload=True)
    station_verifications = collect(ROOT / "data/station_verifications", include_payload=True)

    if not regional:
        raise SystemExit("No regional coverage sources found")
    if not operator_direct:
        raise SystemExit("No operator-direct sources found")
    if not station_verifications:
        raise SystemExit("No station verification sources found")

    regional_paths = {item["sourcePath"] for item in regional}
    for row in overrides["overrides"]:
        if row["regionalFile"] not in regional_paths:
            raise SystemExit(f"Override regional file not included in canonical source set: {row['regionalFile']}")

    station_paths = {item["sourcePath"] for item in station_verifications}
    if rel(BOURGES) not in station_paths:
        raise SystemExit("Corrected Bourges evidence is missing from canonical station evidence")

    return {
        "schemaVersion": "1.0.0",
        "dataset": "france-public-charging-canonical",
        "country": "FR",
        "scope": "public and validated direct charging tariff evidence for Tesla Charge Companion",
        "sourceSnapshotAt": overrides.get("generatedAt"),
        "deterministicBuild": True,
        "sourcePrecedence": [
            {
                "rank": 1,
                "source": "manual_station_verification",
                "rule": "For an exact matched station/EVSE and checked access scenario, verified station/app evidence has priority.",
            },
            {
                "rank": 2,
                "source": "manual_status_override",
                "rule": "For an exact matched local scope, the manual override supersedes older regional reference-only wording without creating a universal tariff.",
            },
            {
                "rank": 3,
                "source": "operator_direct",
                "rule": "Use validated official direct-CPO tariff rules within their stated network, power, profile, time and station scope.",
            },
            {
                "rank": 4,
                "source": "regional_research",
                "rule": "Use regional coverage for discovery and network-family classification; never invent a tariff from coverage alone.",
            },
        ],
        "policy": {
            "doNotInventDepartmentDefaults": True,
            "preserveStationAndNetworkScope": True,
            "preservePowerCustomerProfileClockTimeDurationAndParking": True,
            "directCpoAndRoamingSeparate": True,
            "notDisplayedDoesNotMeanZero": True,
            "unresolvedDirectPricesRemainUnranked": True,
        },
        "manualStatusOverrides": {
            "sourcePath": rel(OVERRIDES),
            "payload": overrides,
        },
        "remainingTrueGaps": list(EXPECTED_GAPS),
        "appReadiness": {
            "manualVerificationPhaseCompleteForAccessibleData": True,
            "remainingTrueGapCount": len(EXPECTED_GAPS),
            "safeToUseExactMatchedVerifiedStationRules": True,
            "safeToUseUniversalDepartmentDefaults": False,
        },
        "counts": {
            "regionalCoverageSources": len(regional),
            "operatorDirectSources": len(operator_direct),
            "stationVerificationSources": len(station_verifications),
            "remainingTrueGaps": len(EXPECTED_GAPS),
        },
        "regionalCoverageSources": regional,
        "operatorDirectSources": operator_direct,
        "stationVerifications": station_verifications,
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the existing output differs from a freshly built deterministic snapshot",
    )
    args = parser.parse_args()

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    text = render(build())

    if args.check:
        if not out.exists():
            print(f"Canonical output missing: {rel(out) if out.is_relative_to(ROOT) else out}", file=sys.stderr)
            return 1
        current = out.read_text(encoding="utf-8")
        if current != text:
            print("Canonical output is stale; rebuild with scripts/build_france_canonical_dataset.py", file=sys.stderr)
            return 1
        print(f"Canonical output is current: {rel(out) if out.is_relative_to(ROOT) else out}")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
