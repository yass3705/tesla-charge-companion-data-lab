import copy
import unittest

from v9_rebuild.canonical import normalize_swiss, validate


ARTIFACT_SHA = "a" * 64


def row(eid, *, priced=False):
    return {"evseId": eid, "operatorId": "CH*ABC", "operatorName": "Archived CPO", "chargingStationId": "STATION-1",
            "names": [{"lang": "fr", "value": "Gare"}], "address": {"City": "Meyrin"},
            "coordinates": {"Google": "46.2 6.1"}, "plugs": ["CCS", "Type 2 Outlet"],
            "chargingFacilities": [{"power": "50.0"}, {"power": "22.0"}],
            "accessibility": "Free publicly accessible", "authenticationModes": ["REMOTE"],
            "paymentOptions": ["Direct Payment"], "isOpen24Hours": True,
            "directTariff": {"status": "priced" if priced else "unresolved", "overlays": [
                {"sourceLabel": "Archive", "sourceFile": "data/switzerland/archive.json", "sourceEvseId": eid,
                 "data": {"tariffId": "archived-reference"}}
            ] if priced else []}}


def source(rows):
    return {"schemaVersion": 3, "country": "CH", "dataset": "switzerland-public-charging-v9", "generatedAt": "2026-10-22T00:00:00Z", "evses": rows}


class CanonicalSwissTest(unittest.TestCase):
    def test_identity_relations_raw_fields_and_missing_price(self):
        rows = [row("CH*ABC*E1", priced=True), row("CH*ABC*E2")]
        data = normalize_swiss(source(rows), artifact_sha256=ARTIFACT_SHA)
        self.assertEqual(len(data["stations"]), 1)
        self.assertEqual(len(data["evses"]), 2)
        self.assertEqual(len(data["connectors"]), 4)
        self.assertEqual(len(data["offers"]), 1)
        self.assertEqual(data["offers"][0]["channel"], "Direct")
        self.assertEqual(data["offers"][0]["rawOffer"], rows[0]["directTariff"]["overlays"][0]["data"])
        by_source = {evse["sourceEvseId"]: evse for evse in data["evses"]}
        self.assertEqual(by_source["CH*ABC*E1"]["rawSourceFields"], {k: v for k, v in rows[0].items() if k != "directTariff"})
        self.assertTrue(all(conn["officialConnectorId"] is None for conn in data["connectors"]))
        self.assertTrue(all(conn["sourceConnectorId"] is None for conn in data["connectors"]))
        self.assertEqual({conn["powerKw"] for conn in data["connectors"]}, {50.0, 22.0})
        self.assertEqual(by_source["CH*ABC*E2"]["officialEvseId"], "CH*ABC*E2")
        self.assertFalse(any(offer["scope"]["evseId"] == by_source["CH*ABC*E2"]["id"] for offer in data["offers"]))

    def test_keys_stable_when_rows_reorder_and_one_disappears(self):
        rows = [row("CH*ABC*E1", priced=True), row("CH*ABC*E2")]
        first = normalize_swiss(source(rows), artifact_sha256=ARTIFACT_SHA)
        second = normalize_swiss(source(list(reversed(rows))), artifact_sha256="b" * 64)
        for section in ("cpos", "stations", "evses", "connectors", "offers"):
            self.assertEqual({x["id"] for x in first[section]}, {x["id"] for x in second[section]})
            self.assertEqual(first[section], second[section])
        removed = normalize_swiss(source(rows[:1]), artifact_sha256="c" * 64)
        self.assertIn(removed["evses"][0]["id"], {x["id"] for x in first["evses"]})

    def test_collisions_and_unproven_offers_rejected(self):
        with self.assertRaisesRegex(ValueError, "collision"):
            normalize_swiss(source([row("CH*ABC*E1"), row("CH*ABC*E1")]), artifact_sha256=ARTIFACT_SHA)
        bad = row("CH*ABC*E1", priced=True)
        bad["directTariff"]["overlays"][0]["sourceEvseId"] = "CH*ABC*E2"
        with self.assertRaisesRegex(ValueError, "scope"):
            normalize_swiss(source([bad]), artifact_sha256=ARTIFACT_SHA)
        data = normalize_swiss(source([row("CH*ABC*E1")]), artifact_sha256=ARTIFACT_SHA)
        data["connectors"][0]["officialConnectorId"] = "invented"
        with self.assertRaisesRegex(ValueError, "invented official"):
            validate(data)

    def test_offer_connector_must_belong_to_scoped_evse(self):
        data = normalize_swiss(source([row("CH*ABC*E1", priced=True), row("CH*ABC*E2")]), artifact_sha256=ARTIFACT_SHA)
        other = next(connector for connector in data["connectors"] if connector["evseId"] != data["offers"][0]["scope"]["evseId"])
        data["offers"][0]["scope"]["connectorId"] = other["id"]
        with self.assertRaisesRegex(ValueError, "offer ownership"):
            validate(data)


if __name__ == "__main__":
    unittest.main()
