import copy
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_v9_electra_nl_exact_canonical.py"
spec = importlib.util.spec_from_file_location("electra_nl_exact", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ElectraNlExactCanonicalTest(unittest.TestCase):
    def setUp(self):
        self.tariff_key = "NL:ELD:ELECTRA-PAYG:fixture"
        self.national = {"schemaVersion": "1.0.0", "dataset": "dot-nl", "stations": [{
            "stationId": "NL:ELD:STATION", "countryCode": "NL", "partyId": "ELD",
            "operatorName": "Electra", "evses": [{"uid": "UID1", "evseId": "NL*ELD*E1", "connectors": [
                {"id": "ccs_1", "powerType": "DC", "powerKw": 150,
                 "tariffKeys": [self.tariff_key]},
                {"id": "ccs_2", "powerType": "DC", "powerKw": 150,
                 "tariffKeys": []}]}]}], "tariffs": {}}
        self.overlay = {"schemaVersion": 1, "dataset": "nl-electra-direct-payg-exact-overlay",
                        "country": "NL", "partyId": "ELD",
                        "policy": {"directCpoOnly": True, "exactEvseAndUniqueConnectorMatchOnly": True},
                        "tariffs": {self.tariff_key: {"tariffKey": self.tariff_key,
                           "countryCode": "NL", "partyId": "ELD",
                           "sourceMetadata": {"omittedUnsupportedComponents": [
                               {"type": "CONGESTION_TIME", "price": 24}]} }},
                        "matches": [{"stationId": "NL:ELD:STATION", "evseId": "NL*ELD*E1",
                                     "connectorId": "ccs_1", "tariffKey": self.tariff_key,
                                     "sourceConnectorId": "uuid-1", "match": "exact_evse_unique_connector"}]}

    def test_exact_connector_and_raw_tariff_only(self):
        result = module.normalize(self.national, self.overlay, national_sha="a" * 64,
                                  overlay_sha="b" * 64)
        self.assertEqual(result["source"]["id"], module.SOURCE_ID)
        self.assertEqual(len(result["stations"]), 1)
        self.assertEqual(len(result["connectors"]), 2)
        self.assertEqual(len(result["offers"]), 1)
        offer = result["offers"][0]
        exact = next(row for row in result["connectors"] if row["sourceConnectorId"] == "ccs_1")
        other = next(row for row in result["connectors"] if row["sourceConnectorId"] == "ccs_2")
        self.assertEqual(offer["scope"]["connectorId"], exact["id"])
        self.assertNotEqual(offer["scope"]["connectorId"], other["id"])
        self.assertEqual(offer["channel"], "Direct")
        self.assertEqual(offer["calculationStatus"], "not_evaluated")
        self.assertEqual(offer["rawOffer"], self.overlay["tariffs"][self.tariff_key])

    def test_bad_exact_proofs_fail_closed(self):
        for mutate in (
            lambda d: d["matches"][0].update(connectorId="ccs_2"),
            lambda d: d["matches"][0].update(evseId="NL*ELD*OTHER"),
            lambda d: d["matches"].append(copy.deepcopy(d["matches"][0])),
            lambda d: d["policy"].update(exactEvseAndUniqueConnectorMatchOnly=False),
            lambda d: d["tariffs"][self.tariff_key].update(partyId="OTHER"),
        ):
            changed = copy.deepcopy(self.overlay)
            mutate(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                module.normalize(self.national, changed, national_sha="a" * 64,
                                 overlay_sha="b" * 64)

    def test_immutable_output_outside_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            national = root / "national.json.gz"
            overlay = root / "overlay.json"
            output = root / "candidate.json"
            national.write_bytes(gzip.compress(json.dumps(self.national).encode()))
            overlay.write_text(json.dumps(self.overlay))
            first = module.build(national, overlay, output)
            self.assertEqual(first["sha256"], module.build(national, overlay, output)["sha256"])
            output.write_text("corrupt")
            with self.assertRaises(ValueError):
                module.build(national, overlay, output)


if __name__ == "__main__":
    unittest.main()
