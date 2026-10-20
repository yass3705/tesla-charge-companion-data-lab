"""Offline V9 migration checks using archived UK Ubitricity shapes and samples."""

import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from v9_rebuild.electroverse import ROOT
from v9_rebuild.uk_ubitricity import run, validate_output


def fixture_payload():
    with gzip.open(ROOT / "data/national/uk_ubitricity_pcpr.json.gz", "rt") as stream:
        raw = json.load(stream)
    evidence = json.loads((ROOT / "data/operator_direct/ubitricity_uk_pcpr_payg_evidence.json").read_text())
    tariff_id = "f9c8695b565b8164e2a02029c4cc73f7"
    sample = evidence["tariffs"][tariff_id][0]
    locations = [location for location in raw["locations"] if any(
        evse.get("evse_id") == sample["evseId"] and any(
            str(connector.get("id")) == str(sample["connectorId"]) and tariff_id in connector.get("tariff_ids", [])
            for connector in evse.get("connectors", []))
        for evse in location.get("evses", []))]
    assert len(locations) == 1
    location = locations[0]
    location["evses"] = [evse for evse in location["evses"] if evse.get("evse_id") == sample["evseId"]]
    location["evses"][0]["connectors"] = [connector for connector in location["evses"][0]["connectors"]
                                            if str(connector.get("id")) == str(sample["connectorId"])]
    tariffs = [tariff for tariff in raw["tariffs"] if str(tariff.get("id")) == tariff_id]
    assert len(tariffs) == 1
    key = "|".join(map(str, (location["id"], sample["evseId"], sample["connectorId"], tariff_id)))
    return {"locations": [location], "tariffs": tariffs, "publicSamples": {key: sample}}


class UbitricityMigrationTests(unittest.TestCase):
    def test_archived_exact_connector_and_offline_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            fixture = Path(tmp) / "fixture.json"
            fixture.write_text(json.dumps(fixture_payload()))
            with mock.patch.dict(os.environ, {"UBITRICITY_PCPR_TOKEN": "fixture-token"}):
                run(out, fixture=fixture)
            staged = validate_output(out)
            self.assertEqual(len(staged["sources"][0]["locations"]), 1)
            audit = json.loads((out / "reports/uk/ubitricity-pcpr-validation-latest.json").read_text())
            self.assertEqual(audit["pricedConnectors"], 1)

    def test_empty_snapshot_keeps_missing_price_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            fixture = Path(tmp) / "fixture.json"
            fixture.write_text(json.dumps({"locations": [], "tariffs": []}))
            with mock.patch.dict(os.environ, {"UBITRICITY_PCPR_TOKEN": "fixture-token"}):
                run(out, fixture=fixture)
            audit = json.loads((out / "reports/uk/ubitricity-pcpr-validation-latest.json").read_text())
            self.assertEqual(audit["status"], "no_exact_tariff_available")

    def test_corrupt_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            fixture = Path(tmp) / "fixture.json"
            fixture.write_text(json.dumps({"locations": [], "tariffs": []}))
            with mock.patch.dict(os.environ, {"UBITRICITY_PCPR_TOKEN": "fixture-token"}):
                run(out, fixture=fixture)
            (out / "data/national/uk_ubitricity_v9.json.gz").write_bytes(b"bad")
            with self.assertRaises((OSError, gzip.BadGzipFile)):
                validate_output(out)


if __name__ == "__main__":
    unittest.main()
