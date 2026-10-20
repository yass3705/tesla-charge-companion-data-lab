#!/usr/bin/env python3
"""Run the preserved DOT-NL method outside the checkout.

The known endpoints and integration scripts come from the archived workflow.
Fixture paths allow technical validation without contacting a supplier.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCATIONS_URL = "https://opendata.ndw.nu/charging_point_locations_ocpi.json.gz"
TARIFFS_URL = "https://opendata.ndw.nu/charging_point_tariffs_ocpi.json.gz"


def invoke(script: str, *args: object) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *(str(arg) for arg in args)],
                   cwd=ROOT, check=True, capture_output=True, text=True)


def download_or_copy(url: str, fixture: Path | None, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if fixture is None:
        with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as output:
            shutil.copyfileobj(response, output)
    else:
        shutil.copyfile(fixture, target)
    with gzip.open(target, "rt", encoding="utf-8-sig") as handle:
        if not isinstance(json.load(handle), list):
            raise ValueError("DOT-NL input must be a gzip JSON array")


def validate_output(out: Path) -> None:
    base = out / "data/national/netherlands_dotnl"
    with gzip.open(base / "normalized.json.gz", "rt", encoding="utf-8") as handle:
        normalized = json.load(handle)
    if (normalized.get("scope", {}).get("countryCode") != "NL"
            or normalized.get("scope", {}).get("teslaExcluded") is not True
            or not isinstance(normalized.get("stations"), list)
            or not isinstance(normalized.get("tariffs"), dict)):
        raise ValueError("Invalid normalized DOT-NL schema or scope")
    report = json.loads((out / "reports/netherlands/dotnl-national-tariff-preservation-latest.json").read_text())
    if report.get("overrideViolations") != 0 or report.get("sourceConnectorRecordCountEqualsFinal") is not True:
        raise ValueError("National tariff references changed")
    runtime = base / "runtime"
    manifest = json.loads((runtime / "manifest.json").read_text())
    scope = manifest.get("scope", {})
    if (manifest.get("schemaVersion") != 3 or scope.get("countryCode") != "NL"
            or scope.get("teslaExcluded") is not True or scope.get("ocpiOpeningTimes") is not True
            or scope.get("ocpiParkingRestrictions") is not True):
        raise ValueError("Invalid DOT-NL runtime manifest")
    files = [(manifest["allFile"], manifest["allSha256"])]
    files.extend((tile["file"], tile["sha256"]) for tile in manifest.get("tiles", []))
    for name, expected in files:
        path = runtime / name
        if path.resolve().parent != runtime.resolve() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Runtime file checksum mismatch: {name}")
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            if not isinstance(json.load(handle), list):
                raise ValueError(f"Invalid runtime JSON: {name}")


def run(out: Path, locations: Path | None = None, tariffs: Path | None = None, *, electra: bool = True) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Output must be outside the checkout")
    raw = out / "raw"
    loc = raw / "locations.json.gz"
    tariff = raw / "tariffs.json.gz"
    download_or_copy(LOCATIONS_URL, locations, loc)
    download_or_copy(TARIFFS_URL, tariffs, tariff)
    base = out / "data/national/netherlands_dotnl"
    normalized = base / "normalized.json.gz"
    invoke("dotnl_netherlands_build.py", loc, tariff, normalized, out / "docs/netherlands-dotnl-build-report.json")
    national = raw / "normalized-national.json.gz"
    shutil.copyfile(normalized, national)
    candidate = ROOT / "data/operator_direct/ubitricity_nl_payg_exact_overlay_candidate.json.gz.b64"
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    invoke("integrate_ubitricity_nl_payg.py", "--normalized", normalized, "--candidate", candidate,
           "--overlay", out / "data/operator_direct/ubitricity_nl_payg_exact_overlay.json",
           "--report", out / "reports/netherlands/ubitricity-direct-payg-integration-latest.json")
    if electra:
        invoke("integrate_electra_nl_graphql.py", "--normalized", normalized,
               "--overlay", out / "data/operator_direct/electra_nl_graphql_exact_overlay.json",
               "--report", out / "reports/netherlands/electra-direct-payg-integration-latest.json")
    invoke("dotnl_national_tariff_guard.py", national, normalized,
           out / "reports/netherlands/dotnl-national-tariff-preservation-latest.json")
    runtime = base / "runtime"
    invoke("dotnl_netherlands_runtime.py", normalized, runtime, out / "docs/netherlands-dotnl-runtime-report.json")
    invoke("dotnl_netherlands_access_patch.py", normalized, runtime,
           out / "docs/netherlands-dotnl-access-report.json")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--locations", type=Path)
    parser.add_argument("--tariffs", type=Path)
    parser.add_argument("--skip-electra", action="store_true", help="Offline fixture test only")
    args = parser.parse_args()
    if (args.locations is None) != (args.tariffs is None):
        parser.error("Both fixture inputs are required")
    run(args.out, args.locations, args.tariffs, electra=not args.skip_electra)


if __name__ == "__main__":
    main()
