import importlib.util
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical_registry import BY_SOURCE
from v9_rebuild.canonical_uk_ocpi_pair import normalize_uk_ocpi_pair


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_v9_canonical_batch.py"
SPEC = importlib.util.spec_from_file_location("build_v9_canonical_batch", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SHA = "a" * 64


def fixture(official=None):
    return {"source": "operator_supplied_Eco_Movement_PCPR", "collectedAt": "2026-10-20T00:00:00Z",
            "locations": [{"id": "L1", "country_code": "GB", "party_id": "UBI",
                           "coordinates": {"latitude": "51.5", "longitude": "-0.1"},
                           "evses": [{"uid": "source-uid", "evse_id": official,
                                      "connectors": [{"id": "1", "standard": "IEC_62196_T2",
                                                      "max_electric_power": 7000,
                                                      "tariff_ids": ["T1", "missing"]}]}]}],
            "tariffs": [{"id": "T1", "country_code": "GB", "party_id": "UBI",
                         "currency": "GBP", "elements": []}]}


class CanonicalUkOcpiPairTests(unittest.TestCase):
    def test_exact_connector_scope_and_missing_tariff_reference(self):
        data = normalize_uk_ocpi_pair(fixture("GB*UBI*E123"), artifact_sha256=SHA,
                                      source_id="GB:ubitricity_pcpr_direct")
        self.assertEqual(data["evses"][0]["officialEvseId"], "GB*UBI*E123")
        self.assertEqual(data["connectors"][0]["unresolvedTariffRefs"], ["missing"])
        self.assertEqual(data["connectors"][0]["powerKw"], 7)
        self.assertEqual(len(data["offers"]), 1)
        self.assertEqual(data["offers"][0]["scope"],
                         {"evseId": data["evses"][0]["id"],
                          "connectorId": data["connectors"][0]["id"]})
        self.assertEqual(data["offers"][0]["calculationStatus"], "not_evaluated")
        self.assertEqual(data["offers"][0]["rawOffer"], fixture()["tariffs"][0])

    def test_no_official_id_is_invented(self):
        data = normalize_uk_ocpi_pair(fixture(), artifact_sha256=SHA,
                                      source_id="GB:ubitricity_pcpr_direct")
        self.assertIsNone(data["evses"][0]["officialEvseId"])
        self.assertEqual(data["evses"][0]["sourceEvseId"], "source-uid")

    def test_collisions_and_wrong_tariff_owner_fail(self):
        duplicate = fixture()
        duplicate["locations"].append(duplicate["locations"][0])
        with self.assertRaisesRegex(ValueError, "collision"):
            normalize_uk_ocpi_pair(duplicate, artifact_sha256=SHA,
                                   source_id="GB:ubitricity_pcpr_direct")
        foreign = fixture()
        foreign["tariffs"][0]["party_id"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "ownership"):
            normalize_uk_ocpi_pair(foreign, artifact_sha256=SHA,
                                   source_id="GB:ubitricity_pcpr_direct")

    def test_historical_gridserve_pair_contract(self):
        route = BY_SOURCE["GB:gridserve_pcpr_direct"]
        payload, source_sha, _ = MODULE.read_route(route, route.source_id)
        self.assertEqual(len(source_sha), 64)
        self.assertEqual(len(payload["tariffArtifactSha256"]), 64)
        self.assertEqual(payload["locations"]["collectedAt"], payload["tariffs"]["collectedAt"])
        self.assertIsInstance(payload["locations"]["locations"], list)


if __name__ == "__main__":
    unittest.main()
