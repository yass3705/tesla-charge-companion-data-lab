#!/usr/bin/env python3
"""Run preserved Blink PCPR collection and exact-connector audit together."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import os
from pathlib import Path

from v9_rebuild.electroverse import ROOT

RAW = Path("data/national/uk_blink_pcpr.json.gz")
STAGED = Path("data/national/uk_blink_pcpr_v9.json.gz")
REPORT = Path("reports/uk/blink-pcpr-latest.json")
AUDIT = Path("reports/uk/blink-pcpr-validation-latest.json")


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Historical UK Blink method missing: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_output(out: Path) -> dict:
    with gzip.open(out / RAW, "rt", encoding="utf-8") as handle:
        raw = json.load(handle)
    with gzip.open(out / STAGED, "rt", encoding="utf-8") as handle:
        staged = json.load(handle)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    audit = json.loads((out / AUDIT).read_text(encoding="utf-8"))
    sources = staged.get("sources") or []
    if (raw.get("source") != "Blink PCPR" or staged.get("country") != "GB"
            or len(sources) != 1 or sources[0].get("id") != "blink-uk-pcpr-direct"
            or report.get("provider") != "Blink Charging" or report.get("credentialPersisted") is not False
            or raw.get("collectedAt") != staged.get("collectedAt") or staged.get("collectedAt") != report.get("collectedAt")
            or audit.get("collectedAt") != report.get("collectedAt")
            or audit.get("publicLocations") != len(sources[0].get("locations") or [])
            or audit.get("publicConnectors") != report.get("publicConnectors")
            or audit.get("exactPricedConnectors") != report.get("pricedExactConnectors")
            or audit.get("distinctTariffs") != len(sources[0].get("tariffs") or [])
            or audit.get("validatedForV9") is not bool(audit.get("exactPricedConnectors"))):
        raise ValueError("UK Blink PCPR technical contract invalid")
    return staged


def run(out: Path, *, fixture: Path | None = None) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("UK Blink output must be outside checkout")
    (out / RAW).parent.mkdir(parents=True, exist_ok=True)
    (out / REPORT).parent.mkdir(parents=True, exist_ok=True)
    collector = load_script(ROOT / "scripts/uk_blink_pcpr_collect.py", "v9_historical_uk_blink_collect")
    collector.ROOT = out
    if fixture is not None:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        if not isinstance(payload.get("locations"), list) or not isinstance(payload.get("tariffs"), list):
            raise ValueError("Blink fixture envelope invalid")
        collector.collect = lambda endpoint, authorization: (payload[endpoint], 1)
    collector.main()
    auditor = load_script(ROOT / "scripts/uk_blink_pcpr_validate.py", "v9_historical_uk_blink_audit")
    auditor.ROOT = out
    auditor.SRC = out / STAGED
    auditor.REPORT = out / REPORT
    auditor.OUT = out / AUDIT
    auditor.main()
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("BLINK_PCPR_TOKEN"):
        raise SystemExit("Missing named Blink PCPR secret")
    run(args.out)


if __name__ == "__main__":
    main()
