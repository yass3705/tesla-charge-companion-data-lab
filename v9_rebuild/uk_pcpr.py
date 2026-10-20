#!/usr/bin/env python3
"""Run preserved Allego UK and Source EV PCPR methods in isolated staging."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT
from v9_rebuild.uk_blink import load_script

PROVIDERS = {
    "allego_uk": ("Allego UK", "allego-uk-pcpr-direct", "ALLEGO_UK_PCPR_TOKEN", "uk_allego_pcpr_validate.py"),
    "source_ev": ("Source EV", "source-ev-uk-pcpr-direct", "SOURCE_EV_PCPR_TOKEN", "uk_source_ev_pcpr_validate.py"),
}


def paths(provider: str) -> tuple[Path, Path, Path, Path]:
    if provider not in PROVIDERS:
        raise ValueError("Unsupported UK PCPR provider")
    return (Path(f"data/national/uk_{provider}_pcpr.json.gz"),
            Path(f"data/national/uk_{provider}_pcpr_v9.json.gz"),
            Path(f"reports/uk/{provider}-pcpr-latest.json"),
            Path(f"reports/uk/{provider}-pcpr-validation-latest.json"))


def validate_output(out: Path, provider: str) -> dict:
    raw_path, staged_path, report_path, audit_path = paths(provider)
    with gzip.open(out / raw_path, "rt", encoding="utf-8") as handle:
        raw = json.load(handle)
    with gzip.open(out / staged_path, "rt", encoding="utf-8") as handle:
        staged = json.load(handle)
    report = json.loads((out / report_path).read_text(encoding="utf-8"))
    audit = json.loads((out / audit_path).read_text(encoding="utf-8"))
    name, source_id, _, _ = PROVIDERS[provider]
    sources = staged.get("sources") or []
    if (staged.get("country") != "GB" or len(sources) != 1 or sources[0].get("id") != source_id
            or report.get("provider") != name or report.get("credentialPersisted") is not False
            or raw.get("collectedAt") != staged.get("collectedAt") or staged.get("collectedAt") != report.get("collectedAt")
            or audit.get("collectedAt") != report.get("collectedAt")
            or audit.get("publicLocations") != len(sources[0].get("locations") or [])
            or audit.get("publicConnectors") != report.get("publicConnectors")
            or audit.get("exactPricedConnectors") != report.get("pricedExactConnectors")
            or audit.get("distinctTariffs") != len(sources[0].get("tariffs") or [])
            or audit.get("validatedForV9") is not bool(audit.get("exactPricedConnectors"))):
        raise ValueError(f"UK {provider} PCPR technical contract invalid")
    return staged


def run(out: Path, provider: str, *, fixture: Path | None = None) -> None:
    raw_path, staged_path, report_path, audit_path = paths(provider)
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("UK PCPR output must be outside checkout")
    (out / raw_path).parent.mkdir(parents=True, exist_ok=True)
    (out / report_path).parent.mkdir(parents=True, exist_ok=True)
    collector = load_script(ROOT / "scripts/uk_pcpr_cpo_collect.py", f"v9_historical_uk_{provider}_collect")
    collector.ROOT = out
    if fixture is not None:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        if not isinstance(payload.get("locations"), list) or not isinstance(payload.get("tariffs"), list):
            raise ValueError("UK PCPR fixture envelope invalid")
        collector.collect = lambda endpoint, authorization, budget: payload[endpoint]
    old_args = sys.argv
    try:
        sys.argv = ["uk_pcpr_cpo_collect.py", provider]
        collector.main()
    finally:
        sys.argv = old_args
    auditor = load_script(ROOT / "scripts" / PROVIDERS[provider][3], f"v9_historical_uk_{provider}_audit")
    auditor.ROOT = out
    auditor.SRC = out / staged_path
    auditor.REPORT = out / report_path
    auditor.OUT = out / audit_path
    auditor.main()
    validate_output(out, provider)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get(PROVIDERS[args.provider][2]):
        raise SystemExit("Missing named UK PCPR provider secret")
    run(args.out, args.provider)


if __name__ == "__main__":
    main()
