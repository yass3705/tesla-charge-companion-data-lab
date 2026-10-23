import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_v9_canonical_batch as batch
from v9_rebuild.canonical import normalize_belgium_nap
from v9_rebuild.canonical_registry import CanonicalRoute


def location(name="L1"):
    price = {"rateId": "R1", "ratePolicy": "adHoc", "currency": "EUR",
             "priceType": "pricePerKWh", "value": 0.50, "taxIncluded": True}
    return {"id": name, "operator": "Example CPO", "countryCode": "BE",
            "brand": "Example", "latitude": 50.1, "longitude": 4.1,
            "stations": [{"id": "S1", "evses": [{"id": "native-E1",
                "externalIdentifiers": ["BE*EXA*E1"],
                "connectors": [{"type": "iec62196T2", "maxPowerW": 22000,
                                "externalIdentifiers": ["BE*EXA*E1"]}],
                "prices": [price]}]}]}


class BelgiumNapCanonicalTests(unittest.TestCase):
    def test_exact_source_identity_and_unparsed_price(self):
        payload = {"country": "BE", "source": "archived-nap", "locations": [location("L1"), location("L2")]}
        result = normalize_belgium_nap(payload, artifact_sha256="a" * 64)
        reordered = normalize_belgium_nap({**payload, "locations": list(reversed(payload["locations"]))},
                                           artifact_sha256="a" * 64)
        for section in ("stations", "evses", "connectors", "offers"):
            self.assertEqual(result[section], reordered[section])
        self.assertEqual(result["evses"][0]["officialEvseId"], "BE*EXA*E1")
        self.assertIsNone(result["connectors"][0]["officialConnectorId"])
        self.assertEqual(result["offers"][0]["calculationStatus"], "not_evaluated")
        self.assertEqual(result["offers"][0]["rawOffer"]["value"], 0.50)
        self.assertNotIn("pricing", result["offers"][0])
        changed = json.loads(json.dumps(payload))
        changed["locations"][0]["stations"][0]["evses"][0]["prices"][0]["ratePolicy"] = "contract"
        unclassified = normalize_belgium_nap(changed, artifact_sha256="a" * 64)
        self.assertEqual(len(unclassified["offers"]), 1)
        self.assertEqual(sum(len(row["unclassifiedPrices"]) for row in unclassified["evses"]), 1)
        repeated = normalize_belgium_nap({**payload, "locations": [location("L1"), location("L1")]},
                                         artifact_sha256="a" * 64)
        self.assertEqual(len(repeated["stations"]), 1)
        self.assertEqual(len(repeated["evses"]), 1)
        self.assertEqual(len(repeated["offers"]), 1)
        self.assertEqual(len(repeated["stations"][0]["archiveVariants"]), 1)

    def test_page_manifest_checks_sequence_and_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages = root / "data/belgium/pages"
            pages.mkdir(parents=True)
            page = {"country": "BE", "locationCount": 1, "locations": [location()]}
            (pages / "page.json.gz").write_bytes(gzip.compress(json.dumps(page).encode()))
            manifest = {"country": "BE", "source": "archived-nap", "pageSize": 1, "pageCount": 1,
                        "pages": [{"pageIndex": 0, "offset": 0, "locationCount": 1,
                                   "canonicalPath": "data/belgium/pages/page.json.gz",
                                   "firstLocationId": "L1", "lastLocationId": "L1"}]}
            path = root / "data/belgium/manifest.json"
            path.write_text(json.dumps(manifest))
            route = CanonicalRoute("BE:nap_static", "data/belgium/manifest.json", normalize_belgium_nap,
                                   page_manifest=True)
            with patch.object(batch, "ROOT", root):
                payload, artifact_sha, manifest_sha = batch.read_route(route, "BE:nap_static")
                self.assertEqual(payload["locations"][0]["id"], "L1")
                self.assertEqual(len(artifact_sha), 64)
                self.assertEqual(len(manifest_sha), 64)
                manifest["pages"][0]["firstLocationId"] = "wrong"
                path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, "contents or boundaries"):
                    batch.read_route(route, "BE:nap_static")


if __name__ == "__main__":
    unittest.main()
