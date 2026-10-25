"""Frozen UK PCPR archive contracts: exact topology, raw tariff scope and failure modes."""
import copy
import unittest

from scripts.build_v9_canonical_batch import read_route
from v9_rebuild.canonical_registry import BY_SOURCE
from v9_rebuild.canonical_uk_pcpr import normalize_uk_pcpr


IDS = ("GB:blink_pcpr_direct", "GB:allego_pcpr_direct", "GB:source_ev_pcpr_direct")


class UkPcprCanonicalTests(unittest.TestCase):
    def fixture(self, source_id):
        route = BY_SOURCE[source_id]
        payload, sha, _ = read_route(route, source_id)
        payload = copy.deepcopy(payload)
        source = payload["sources"][0]
        source["locations"] = source["locations"][:1]
        refs = {ref for evse in source["locations"][0]["evses"]
                for connector in evse["connectors"] for ref in connector["tariff_ids"]}
        source["tariffs"] = [row for row in source["tariffs"] if row["id"] in refs]
        return payload, sha

    def test_three_archived_families_keep_exact_connectors_and_raw_tariffs(self):
        for source_id in IDS:
            with self.subTest(source=source_id):
                payload, sha = self.fixture(source_id)
                result = normalize_uk_pcpr(payload, artifact_sha256=sha, source_id=source_id)
                source = payload["sources"][0]
                self.assertEqual(result["source"]["artifactSha256"], sha)
                self.assertEqual(len(result["stations"]), 1)
                expected = sum(len(evse["connectors"]) for evse in source["locations"][0]["evses"])
                self.assertEqual(len(result["connectors"]), expected)
                self.assertEqual(len(result["offers"]), expected)
                connectors = {row["id"]: row for row in result["connectors"]}
                evses = {row["id"]: row for row in result["evses"]}
                for offer in result["offers"]:
                    self.assertEqual(offer["channel"], "Direct")
                    self.assertEqual(offer["calculationStatus"], "not_evaluated")
                    self.assertEqual(offer["rawOffer"], result["tariffCatalog"][offer["sourceTariffKey"]])
                    connector = connectors[offer["scope"]["connectorId"]]
                    self.assertEqual(connector["evseId"], offer["scope"]["evseId"])
                    self.assertIsNone(connector["officialConnectorId"])
                    evse = evses[connector["evseId"]]
                    self.assertEqual(evse["officialEvseId"], evse["sourceEvseId"])
                    self.assertTrue(evse["sourceUid"])

    def test_missing_reference_and_connector_identity_fail(self):
        payload, sha = self.fixture(IDS[0])
        connector = payload["sources"][0]["locations"][0]["evses"][0]["connectors"][0]
        connector["tariff_ids"] = ["missing-tariff"]
        with self.assertRaisesRegex(ValueError, "tariff reference"):
            normalize_uk_pcpr(payload, artifact_sha256=sha, source_id=IDS[0])
        payload, sha = self.fixture(IDS[0])
        payload["sources"][0]["locations"][0]["evses"][0]["connectors"][0]["id"] = None
        with self.assertRaisesRegex(ValueError, "connector id"):
            normalize_uk_pcpr(payload, artifact_sha256=sha, source_id=IDS[0])

    def test_eco_movement_keeps_unattributed_refs_out_of_offers(self):
        source_id = "GB:eco_movement_pcpr_raw"
        payload, sha, _ = read_route(BY_SOURCE[source_id], source_id)
        payload = copy.deepcopy(payload)
        source = payload["sources"][0]
        location = next(row for row in source["locations"]
                        if any(set(connector.get("sourceTariffIds") or []) - set(connector.get("tariff_ids") or [])
                               for evse in row["evses"] for connector in evse["connectors"]))
        source["locations"] = [location]
        refs = {ref for evse in location["evses"] for connector in evse["connectors"]
                for ref in connector.get("tariff_ids") or []}
        source["tariffs"] = [row for row in source["tariffs"] if row["id"] in refs]
        result = normalize_uk_pcpr(payload, artifact_sha256=sha, source_id=source_id)
        connectors = {row["id"]: row for row in result["connectors"]}
        self.assertEqual(len(result["stations"]), 1)
        self.assertTrue(result["unresolvedTariffRefs"])
        self.assertTrue(all(ref["sourceTariffKey"] in connectors[ref["connectorId"]]["rawSourceFields"]["sourceTariffIds"]
                            for ref in result["unresolvedTariffRefs"]))
        self.assertTrue(all(offer["sourceTariffKey"] in connectors[offer["scope"]["connectorId"]]["rawSourceFields"]["tariff_ids"]
                            for offer in result["offers"]))
        self.assertTrue(all(offer["calculationStatus"] == "not_evaluated" for offer in result["offers"]))
        altered = copy.deepcopy(payload)
        altered["sources"][0]["locations"][0]["evses"][0]["connectors"][0]["tariff_ids"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "tariff reference"):
            normalize_uk_pcpr(altered, artifact_sha256=sha, source_id=source_id)
        archived, _, _ = read_route(BY_SOURCE[source_id], source_id)
        altered = copy.deepcopy(payload)
        tariff = archived["sources"][0]["tariffs"][0]
        altered["sources"][0]["tariffs"] = [tariff]
        connector = altered["sources"][0]["locations"][0]["evses"][0]["connectors"][0]
        connector["tariff_ids"] = [tariff["id"]]
        connector["sourceTariffIds"] = []
        with self.assertRaisesRegex(ValueError, "tariff reference"):
            normalize_uk_pcpr(altered, artifact_sha256=sha, source_id=source_id)


if __name__ == "__main__":
    unittest.main()
