import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_v9_emsp_exact_canonical import normalize


class ExactEmspCanonicalTest(unittest.TestCase):
    def setUp(self):
        self.national = {"source": {"id": "FR:irve_static"},
                         "cpos": [{"id": "cpo", "country": "FR", "sourceOperatorId": "CPO", "name": "CPO"}],
                         "stations": [{"id": "station", "country": "FR", "cpoId": "cpo", "sourceStationId": "S"}],
                         "evses": [{"id": "evse", "country": "FR", "stationId": "station", "cpoId": "cpo",
                                    "sourceEvseId": "FR*ABC*E1", "officialEvseId": "FR*ABC*E1"}],
                         "connectors": [{"id": "plug", "evseId": "evse", "powerKw": 22,
                                         "sourceConnectorId": None, "officialConnectorId": None}]}
        self.report = {"schemaVersion": 1, "policy": "exact_official_evse_only;no_connector_or_price_propagation",
                       "inputs": {"nationalSha256": "a"*64, "electroverseManifestSha256": "b"*64,
                                  "electraProofSha256": "c"*64},
                       "matches": [{"channel": "Electroverse", "offerId": "e-offer",
                                    "officialEvseId": "FR*ABC*E1", "nationalEvseId": "evse",
                                    "nationalStationId": "station", "nationalConnectorId": None,
                                    "proof": "archived_exact_unique_national_irve_pdc"}]}
        self.source = {"e-offer": [{"id": "e-offer", "verifiedScope": "exact_evse",
                                    "evseIds": ["FR*ABC*E1"], "pricing": {"pricePerKwh": .45},
                                    "metadata": {"identityMode": "exact_unique_national_irve_pdc"}}]}

    def build(self):
        return normalize(self.national, self.report, self.source, {}, national_sha="a"*64,
                         report_sha="d"*64, manifest_sha="b"*64, electra_sha="c"*64)

    def test_raw_channel_scope_and_national_identity(self):
        result = self.build()
        self.assertEqual(result["source"]["id"], "FR:emsp_exact")
        self.assertEqual(result["stations"][0]["id"], "station")
        self.assertEqual(result["evses"][0]["officialEvseId"], "FR*ABC*E1")
        self.assertEqual(result["connectors"][0]["officialConnectorId"], None)
        self.assertEqual(result["offers"][0]["channel"], "Electroverse")
        self.assertEqual(result["offers"][0]["scope"], {"evseId": "evse", "connectorId": None})
        self.assertEqual(result["offers"][0]["calculationStatus"], "not_evaluated")
        self.assertEqual(result["offers"][0]["rawOffer"]["pricing"]["pricePerKwh"], .45)

    def test_public_access_exclusion_follows_exact_national_station(self):
        self.national["stations"][0]["publicAccessDecision"] = "exclude_non_public"
        result = self.build()
        self.assertEqual(result["stations"][0]["publicAccessDecision"], "exclude_non_public")
        self.assertEqual(result["offers"][0]["scope"]["evseId"], "evse")

    def test_bad_sha_or_scope_rejected(self):
        self.report["inputs"]["nationalSha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            self.build()
        self.report["inputs"]["nationalSha256"] = "a"*64
        self.source["e-offer"][0]["evseIds"] = ["FR*ABC*E2"]
        with self.assertRaisesRegex(ValueError, "archived exact proof"):
            self.build()

    def test_electra_and_electroverse_keep_distinct_raw_channels(self):
        self.report["matches"].append({"channel": "Electra", "offerId": "t-electra",
                                       "officialEvseId": "FR*ABC*E1", "nationalEvseId": "evse",
                                       "nationalStationId": "station", "nationalConnectorId": None,
                                       "proof": "archived_app_screenshot_exact_evse_tariff_id"})
        electra = {"t-electra": [{"mapping": {"evseId": "FR*ABC*E1", "chargeTariffId": "t-electra"},
                                  "evidence": {"screenshotSha256": "f"*64}}]}
        result = normalize(self.national, self.report, self.source, electra,
                           national_sha="a"*64, report_sha="d"*64,
                           manifest_sha="b"*64, electra_sha="c"*64)
        self.assertEqual({offer["channel"] for offer in result["offers"]}, {"Electra", "Electroverse"})
        self.assertEqual(len({offer["id"] for offer in result["offers"]}), 2)
        self.assertTrue(all(offer["calculationStatus"] == "not_evaluated" for offer in result["offers"]))


if __name__ == "__main__":
    unittest.main()
