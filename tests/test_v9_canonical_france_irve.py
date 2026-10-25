import copy
import unittest

from v9_rebuild.canonical import normalize_france_irve_compact


def station(source_id="FRABCP1", evse_id="FRABCE1"):
    return [source_id, "Gare", "Rue Exemple", 48.0, 2.0, "ABC", 1, 0,
            [["irve-0-ac-22", "IRVE · Type 2 22 kW", "AC", 22.0, 1, [], [evse_id]],
             ["irve-1-ac-22", "IRVE · E/F 22 kW", "AC", 22.0, 1, [], [evse_id]]],
            "2026-10-23", "ABC réseau"]


class FranceIrveCanonicalTests(unittest.TestCase):
    def test_one_evse_two_unidentified_plugs(self):
        first = normalize_france_irve_compact([station(), station("FRABCP2", "FRABCE2")], artifact_sha256="a" * 64)
        second = normalize_france_irve_compact([station("FRABCP2", "FRABCE2"), station()], artifact_sha256="b" * 64)
        for section in ("stations", "evses", "connectors"):
            self.assertEqual([row["id"] for row in first[section]], [row["id"] for row in second[section]])
        self.assertEqual(len(first["evses"]), 2)
        self.assertEqual(len(first["connectors"]), 4)
        self.assertEqual(first["offers"], [])
        self.assertTrue(all(row["officialConnectorId"] is None for row in first["connectors"]))
        self.assertEqual({row["officialEvseId"] for row in first["evses"]}, {"FRABCE1", "FRABCE2"})

    def test_ownership_and_internal_count_fail_closed(self):
        altered = station()
        altered[6] = 2
        with self.assertRaisesRegex(ValueError, "count"):
            normalize_france_irve_compact([altered], artifact_sha256="a" * 64)
        duplicate = copy.deepcopy(station("FRABCP2"))
        with self.assertRaisesRegex(ValueError, "ownership"):
            normalize_france_irve_compact([station(), duplicate], artifact_sha256="a" * 64)

    def test_pinned_public_access_decision_preserves_raw_station(self):
        ledger = {"schemaVersion": "1.0.0", "dataset": "france-irve-public-access-validation-ledger",
                  "decisions": [{"stationIds": ["FRABCP1"], "decision": "exclude_non_public"},
                                {"stationIds": ["FRABCP2"], "decision": "keep_public"}]}
        result = normalize_france_irve_compact(
            [station(), station("FRABCP2", "FRABCE2")], artifact_sha256="a" * 64,
            access_ledger=ledger, access_ledger_sha256="b" * 64)
        by_source = {row["sourceStationId"]: row for row in result["stations"]}
        self.assertEqual(by_source["FRABCP1"]["publicAccessDecision"], "exclude_non_public")
        self.assertNotIn("publicAccessDecision", by_source["FRABCP2"])
        self.assertEqual(len(result["evses"]), 2)
        self.assertEqual(result["source"]["accessLedgerSha256"], "b" * 64)
        with self.assertRaisesRegex(ValueError, "collision"):
            normalize_france_irve_compact([station()], artifact_sha256="a" * 64,
                access_ledger={**ledger, "decisions": ledger["decisions"] * 2}, access_ledger_sha256="b" * 64)


if __name__ == "__main__":
    unittest.main()
