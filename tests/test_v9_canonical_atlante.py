import copy
import gzip
import hashlib
import json
import unittest
from pathlib import Path

from v9_rebuild.canonical import normalize_atlante_france, normalize_atlante_italy


ARCHIVE = Path(__file__).resolve().parents[1] / "data/national/atlante_direct_stations_italy_latest.json.gz"
FR_ARCHIVE = ARCHIVE.with_name("atlante_direct_stations_france_latest.json.gz")


class CanonicalAtlanteItalyTest(unittest.TestCase):
    def test_archived_exact_scope_and_stable_ids(self):
        raw = ARCHIVE.read_bytes()
        source = json.loads(gzip.decompress(raw))
        first = normalize_atlante_italy(source, artifact_sha256=hashlib.sha256(raw).hexdigest())
        reordered = copy.deepcopy(source)
        reordered["locations"].reverse()
        second = normalize_atlante_italy(reordered, artifact_sha256="b" * 64)
        for section in ("cpos", "stations", "evses", "connectors", "offers"):
            self.assertEqual([row["id"] for row in first[section]], [row["id"] for row in second[section]])
        source_evses = {item["evseId"] for station in source["locations"] for item in station["connectors"]}
        self.assertEqual({row["officialEvseId"] for row in first["evses"]}, source_evses)
        owners = {row["id"]: row["evseId"] for row in first["connectors"]}
        self.assertTrue(all(owners[offer["scope"]["connectorId"]] == offer["scope"]["evseId"] for offer in first["offers"]))
        self.assertTrue(all(row["officialConnectorId"] is None for row in first["connectors"]))
        self.assertTrue(all(row["calculationStatus"] == "not_evaluated" for row in first["offers"]))

    def test_mismatched_tariff_identifier_rejected(self):
        source = json.loads(gzip.decompress(ARCHIVE.read_bytes()))
        source["locations"][0]["connectors"][0]["tariffs"][0]["identifiers"]["evseId"] = "another-EVSE"
        with self.assertRaisesRegex(ValueError, "connector scope"):
            normalize_atlante_italy(source, artifact_sha256="a" * 64)

    def test_french_archive_uses_same_exact_connector_contract(self):
        raw = FR_ARCHIVE.read_bytes()
        source = json.loads(gzip.decompress(raw))
        result = normalize_atlante_france(source, artifact_sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["source"]["id"], "FR:atlante_direct")
        self.assertEqual(result["countries"], [{"code": "FR"}])
        evses = {row["id"]: row for row in result["evses"]}
        connectors = {row["id"]: row for row in result["connectors"]}
        source_connectors = [c for station in source["locations"] for c in station["connectors"]]
        self.assertEqual({row["officialEvseId"] for row in evses.values()},
                         {row["evseId"] for row in source_connectors})
        self.assertEqual(len(result["connectors"]), len(source_connectors))
        for offer in result["offers"]:
            scope = offer["scope"]
            self.assertEqual(connectors[scope["connectorId"]]["evseId"], scope["evseId"])
            self.assertEqual(offer["rawOffer"]["identifiers"]["evseId"],
                             evses[scope["evseId"]]["officialEvseId"])
            self.assertEqual(offer["rawOffer"]["identifiers"]["connectorId"],
                             connectors[scope["connectorId"]]["sourceConnectorId"])
            self.assertEqual(offer["calculationStatus"], "not_evaluated")

    def test_french_archive_rejects_country_or_tariff_scope_change(self):
        source = json.loads(gzip.decompress(FR_ARCHIVE.read_bytes()))
        wrong_country = copy.deepcopy(source)
        wrong_country["locations"][0]["countryCode"] = "IT"
        with self.assertRaisesRegex(ValueError, "station identity"):
            normalize_atlante_france(wrong_country, artifact_sha256="a" * 64)
        source["locations"][0]["connectors"][0]["tariffs"][0]["identifiers"]["connectorId"] = "other"
        with self.assertRaisesRegex(ValueError, "connector scope"):
            normalize_atlante_france(source, artifact_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
