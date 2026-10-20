#!/usr/bin/env python3
"""Run preserved Evyve PCPR collector with an isolated exact-connector check."""

from __future__ import annotations

import argparse
import gzip
import hmac
import json
import os
from pathlib import Path

from v9_rebuild.electroverse import ROOT
from v9_rebuild.uk_blink import load_script

RAW = Path("data/national/uk_evyve_pcpr.json.gz")
STAGED = Path("data/national/uk_evyve_pcpr_v9.json.gz")
REPORT = Path("reports/uk/evyve-pcpr-latest.json")


def validate_output(out: Path) -> dict:
    with gzip.open(out / RAW, "rt", encoding="utf-8") as handle:
        raw = json.load(handle)
    with gzip.open(out / STAGED, "rt", encoding="utf-8") as handle:
        staged = json.load(handle)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    sources = staged.get("sources") or []
    if (raw.get("source") != "Evyve PCPR" or staged.get("country") != "GB"
            or len(sources) != 1 or sources[0].get("id") != "evyve-uk-pcpr-direct"
            or report.get("provider") != "Evyve Charging" or report.get("credentialPersisted") is not False
            or raw.get("collectedAt") != staged.get("collectedAt") or staged.get("collectedAt") != report.get("collectedAt")
            or report.get("publicEvyveLocations") != len(sources[0].get("locations") or [])
            or report.get("readyForV9Review") is not bool(report.get("pricedExactConnectors"))
            or report.get("publicConnectors") != report.get("pricedExactConnectors", 0) + report.get("unpricedPublicConnectors", 0)):
        raise ValueError("UK Evyve PCPR technical contract invalid")
    seen = set()
    tariffs = {str(row.get("id")): row for row in sources[0].get("tariffs") or []}
    for loc in sources[0].get("locations") or []:
        if "evyve" not in str((loc.get("operator") or {}).get("name") or "").casefold() or loc.get("publish") is not True:
            raise ValueError("UK Evyve CPO scope invalid")
        for evse in loc.get("evses") or []:
            for connector in evse.get("connectors") or []:
                key = (loc.get("id"), evse.get("evse_id") or evse.get("uid"), connector.get("id"))
                if not all(key) or key in seen:
                    raise ValueError("UK Evyve connector identity invalid")
                seen.add(key)
                refs = connector.get("tariff_ids") or []
                if not set(refs).issubset(connector.get("sourceTariffIds") or []) or any(ref not in tariffs for ref in refs):
                    raise ValueError("UK Evyve connector tariff reference not exact")
    if len(seen) != report.get("publicConnectors"):
        raise ValueError("UK Evyve connector count mismatch")
    return staged


def run(out: Path, *, fixture: Path | None = None) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("UK Evyve output must be outside checkout")
    evyve = os.environ.get("EVYVE_PCPR_TOKEN", "").strip()
    blink = os.environ.get("BLINK_PCPR_TOKEN", "").strip()
    if not evyve:
        raise RuntimeError("Missing named Evyve PCPR secret")
    if blink and hmac.compare_digest(evyve.encode(), blink.encode()):
        raise RuntimeError("Evyve PCPR secret equals Blink PCPR secret")
    (out / RAW).parent.mkdir(parents=True, exist_ok=True)
    (out / REPORT).parent.mkdir(parents=True, exist_ok=True)
    collector = load_script(ROOT / "scripts/uk_evyve_pcpr_collect.py", "v9_historical_uk_evyve_collect")
    collector.ROOT = out
    if fixture is not None:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        if not isinstance(payload.get("locations"), list) or not isinstance(payload.get("tariffs"), list):
            raise ValueError("UK Evyve fixture envelope invalid")
        collector.collect = lambda endpoint, authorization: (payload[endpoint], 1)
    collector.main()
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    run(parser.parse_args().out)


if __name__ == "__main__":
    main()
