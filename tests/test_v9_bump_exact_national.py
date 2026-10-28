"""Bump joins only equal official IRVE EVSEs owned by BUMP."""
import copy
import unittest

from scripts.build_v9_bump_exact_national import normalize


class BumpExactNationalTest(unittest.TestCase):
    def setUp(self):
        # The small fixture exercises the same canonical contract as the full archive.
        self.national = {"source": {"id": "FR:irve_static"}, "countries": [{"code": "FR"}],
                         "cpos": [{"id": "cpo", "country": "FR", "sourceOperatorId": "BUMP"}],
                         "stations": [{"id": "station", "country": "FR", "cpoId": "cpo"}],
                         "evses": [{"id": "evse", "country": "FR", "cpoId": "cpo",
                                    "stationId": "station", "officialEvseId": "FRBUMP1",
                                    "sourceEvseId": "FRBUMP1"}],
                         "connectors": [{"id": "plug", "evseId": "evse", "sourceConnectorId": None,
                                         "officialConnectorId": None}], "offers": []}
        self.bump = {"source": {"id": "FR:bump_direct_exact"}, "evses": [
            {"id": "source-evse", "officialEvseId": "FRBUMP1"}],
            "offers": [{"id": "raw-offer", "channel": "Direct", "sourceEvseId": "FRBUMP1",
                        "scope": {"evseId": "source-evse", "connectorId": None},
                        "rawOffer": {"compiledOffer": {"id": "compiled-offer", "pricing": {"type": "rules"}}}}]}

    def test_exact_scope_and_no_price_promotion(self):
        result = normalize(self.national, self.bump, national_sha="a", bump_sha="b")
        self.assertEqual(result["offers"][0]["scope"], {"evseId": "evse", "connectorId": None})
        self.assertEqual(result["offers"][0]["sourceOfferId"], "compiled-offer")
        self.assertEqual(result["offers"][0]["calculationStatus"], "not_evaluated")
        self.assertEqual(result["connectors"][0]["id"], "plug")
        self.assertNotIn("pricing", result["offers"][0])
        self.assertEqual(result, normalize(self.national, self.bump, national_sha="a", bump_sha="b"))

    def test_wrong_operator_or_duplicate_national_evse_never_joins(self):
        bad = copy.deepcopy(self.national)
        bad["cpos"][0]["sourceOperatorId"] = "OTHER"
        self.assertEqual(normalize(bad, self.bump, national_sha="a", bump_sha="b")["offers"], [])
        bad = copy.deepcopy(self.national)
        bad["evses"].append({**bad["evses"][0], "id": "second"})
        self.assertEqual(normalize(bad, self.bump, national_sha="a", bump_sha="b")["offers"], [])

    def test_mismatched_source_scope_fails(self):
        bad = copy.deepcopy(self.bump)
        bad["offers"][0]["sourceEvseId"] = "FRBUMP2"
        with self.assertRaises(ValueError):
            normalize(self.national, bad, national_sha="a", bump_sha="b")


if __name__ == "__main__":
    unittest.main()
