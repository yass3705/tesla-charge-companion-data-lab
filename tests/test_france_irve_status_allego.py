import unittest
from collections import Counter

from scripts.france_irve_status_allego import normalize_allego_status, records_from_dxp


class AllegoStatusAdapterTests(unittest.TestCase):
    def test_operational_states_ignore_occupation(self):
        self.assertEqual(normalize_allego_status("Available"), "in_service")
        self.assertEqual(normalize_allego_status("Occupied"), "in_service")
        self.assertEqual(normalize_allego_status("Charging"), "in_service")
        self.assertEqual(normalize_allego_status("Reserved"), "in_service")

    def test_explicit_failure_states_are_out_of_service(self):
        self.assertEqual(normalize_allego_status("Unavailable"), "out_of_service")
        self.assertEqual(normalize_allego_status("Faulted"), "out_of_service")
        self.assertEqual(normalize_allego_status("OutOfService"), "out_of_service")
        self.assertEqual(normalize_allego_status("Offline"), "out_of_service")

    def test_unknown_and_unrecognized_fail_closed(self):
        self.assertEqual(normalize_allego_status("Unknown"), "unknown")
        self.assertEqual(normalize_allego_status("SomethingNew"), "unknown")
        self.assertEqual(normalize_allego_status(None), "unknown")

    def test_exact_visual_id_to_existing_irve_pdc(self):
        expected = {1: "FRALLEGO8002611", 2: "FRALLEGO8002612"}
        payload = {
            "chargePointId": "FRALLEGO800261",
            "chargePointStatus": "Available",
            "evses": [
                {"visualId": 1, "status": "Available"},
                {"visualId": 2, "status": "Occupied"},
            ],
        }
        records, stats = records_from_dxp("FRALLEGO800261", expected, payload, "2026-08-28T14:00:00Z")
        self.assertEqual([r["idPdcItinerance"] for r in records], ["FRALLEGO8002611", "FRALLEGO8002612"])
        self.assertTrue(all(r["status"] == "in_service" for r in records))
        self.assertTrue(all(r["matchConfidence"] == "exact" for r in records))
        self.assertEqual(stats["records"], 2)

    def test_dxp_evse_not_in_current_irve_is_never_created(self):
        expected = {1: "FRALLEGO8001301"}
        payload = {
            "chargePointId": "FRALLEGO800130",
            "evses": [
                {"visualId": 1, "status": "Available"},
                {"visualId": 2, "status": "Available"},
            ],
        }
        records, stats = records_from_dxp("FRALLEGO800130", expected, payload, "2026-08-28T14:00:00Z")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["idPdcItinerance"], "FRALLEGO8001301")
        self.assertEqual(stats["dxp_evse_not_in_current_irve"], 1)

    def test_chargepoint_mismatch_produces_no_record(self):
        records, stats = records_from_dxp(
            "FRALLEGO800130",
            {1: "FRALLEGO8001301"},
            {"chargePointId": "FRALLEGO999999", "evses": [{"visualId": 1, "status": "Available"}]},
            "2026-08-28T14:00:00Z",
        )
        self.assertEqual(records, [])
        self.assertEqual(stats["chargepoint_id_mismatch"], 1)

    def test_missing_evse_in_dxp_is_reported_not_guessed(self):
        expected = {1: "FRALLEGO8001301", 2: "FRALLEGO8001302"}
        payload = {"chargePointId": "FRALLEGO800130", "evses": [{"visualId": 1, "status": "Available"}]}
        records, stats = records_from_dxp("FRALLEGO800130", expected, payload, "2026-08-28T14:00:00Z")
        self.assertEqual(len(records), 1)
        self.assertEqual(stats["irve_pdc_missing_from_dxp_payload"], 1)


if __name__ == "__main__":
    unittest.main()
