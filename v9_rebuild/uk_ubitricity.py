#!/usr/bin/env python3
"""Execute the preserved UK Ubitricity PCPR chain outside the Git checkout."""

from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path

from v9_rebuild.electroverse import ROOT
from v9_rebuild.uk_blink import load_script

RAW = Path("data/national/uk_ubitricity_pcpr.json.gz")
STAGED = Path("data/national/uk_ubitricity_v9.json.gz")
COLLECT_REPORT = Path("reports/uk/ubitricity-pcpr-latest.json")
AUDIT = Path("reports/uk/ubitricity-pcpr-validation-latest.json")
EVIDENCE = Path("data/operator_direct/ubitricity_uk_pcpr_payg_evidence.json")


def validate_output(out: Path) -> dict:
    with gzip.open(out / RAW, "rt", encoding="utf-8") as stream:
        raw = json.load(stream)
    with gzip.open(out / STAGED, "rt", encoding="utf-8") as stream:
        staged = json.load(stream)
    collected = json.loads((out / COLLECT_REPORT).read_text(encoding="utf-8"))
    audit = json.loads((out / AUDIT).read_text(encoding="utf-8"))
    evidence = json.loads((out / EVIDENCE).read_text(encoding="utf-8"))
    sources = staged.get("sources") or []
    if (not isinstance(raw.get("locations"), list) or not isinstance(raw.get("tariffs"), list)
            or raw.get("source") != "operator_supplied_Eco_Movement_PCPR"
            or collected.get("provider") != "Ubitricity"
            or collected.get("credentialsPersisted") is not False
            or collected.get("locations") != len(raw["locations"])
            or collected.get("tariffs") != len(raw["tariffs"])
            or raw.get("collectedAt") != collected.get("collectedAt")
            or staged.get("collectedAt") != raw.get("collectedAt")
            or audit.get("collectedAt") != raw.get("collectedAt")
            or audit.get("credentialsPersisted") is not False
            or audit.get("locations") != len(raw["locations"])
            or len(sources) != 1 or sources[0].get("id") != "ubitricity-pcpr-payg"
            or len(sources[0].get("locations") or []) != len(raw["locations"])
            or sources[0].get("tariffs") != []
            or not isinstance(evidence.get("tariffs"), dict)
            or audit.get("pricedConnectors", -1) + audit.get("unpricedConnectors", -1) != audit.get("connectors")):
        raise ValueError("Ubitricity UK PCPR technical contract invalid")
    identities = set()
    priced = 0
    for location in sources[0]["locations"]:
        if (location.get("country_code"), location.get("party_id"), location.get("operator", {}).get("name")) != ("GB", "UBI", "Ubitricity"):
            raise ValueError("Ubitricity UK location outside validated scope")
        for evse in location.get("evses", []):
            for connector in evse.get("connectors", []):
                key = (location.get("id"), evse.get("evse_id"), connector.get("id"))
                if not all(key) or key in identities:
                    raise ValueError("Ubitricity UK connector identity invalid")
                identities.add(key)
                priced += "validatedV9Offer" in connector
    if len(identities) != audit["connectors"] or priced != audit["pricedConnectors"]:
        raise ValueError("Ubitricity UK exact connector counts invalid")
    return staged


def run(out: Path, *, fixture: Path | None = None) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Ubitricity output must be outside checkout")
    (out / RAW).parent.mkdir(parents=True, exist_ok=True)
    (out / COLLECT_REPORT).parent.mkdir(parents=True, exist_ok=True)
    (out / EVIDENCE).parent.mkdir(parents=True, exist_ok=True)
    collector = load_script(ROOT / "scripts/uk_ubitricity_pcpr_collect.py", "v9_historical_uk_ubitricity_collect")
    collector.ROOT = out
    if fixture is not None:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        if not isinstance(payload.get("locations"), list) or not isinstance(payload.get("tariffs"), list):
            raise ValueError("Ubitricity UK fixture envelope invalid")
        collector.collect = lambda endpoint, token, deadline: (payload[endpoint], 1)
    collector.main()
    validator = load_script(ROOT / "scripts/uk_ubitricity_pcpr_validate.py", "v9_historical_uk_ubitricity_validate")
    validator.ROOT = out
    if fixture is not None:
        # Public detail samples are archived fixture inputs, never fetched by a test.
        samples = payload.get("publicSamples", {})
        def public_sample(location_id, evse_id, connector_id, tariff_id):
            key = "|".join(map(str, (location_id, evse_id, connector_id, tariff_id)))
            if key not in samples:
                raise ValueError("offline fixture: public sample unavailable")
            sample = samples[key]
            if (sample.get("evseId"), str(sample.get("connectorId")), str(sample.get("tariffId"))) != (evse_id, str(connector_id), str(tariff_id)):
                raise ValueError("offline fixture: public sample identity invalid")
            return sample
        validator.public_sample = public_sample
    validator.main()
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("UBITRICITY_PCPR_TOKEN", "").strip():
        raise SystemExit("Missing named Ubitricity PCPR token")
    run(args.out)


if __name__ == "__main__":
    main()
