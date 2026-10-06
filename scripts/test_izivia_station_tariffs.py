import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("izivia_station_tariffs", ROOT / "izivia_station_tariffs.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class StationTariffWatchTests(unittest.TestCase):
    def test_only_direct_station_price_is_recorded(self):
        self.assertEqual(watch.direct_texts([
            {"itemType": "subscription", "rawPricingInfos": ["0.10€/kWh"]},
            {"itemType": "charging_location", "rawPricingInfos": [" 0.35€/kWh ", "0.35€/kWh"]},
        ]), ["0.35€/kWh"])

    def test_capture_uses_exact_network_filter_and_all_markers(self):
        calls = []

        def fake_request(path, method="GET", body=None):
            calls.append((path, method, body))
            if path == "map/markers":
                return 200, [{"id": "a"}, {"id": "b"}]
            if "pricing-info-items" in path:
                return 200, [{"itemType": "subscription", "rawPricingInfos": ["0.10€/kWh"]}]
            return 200, {"legacyId": "FR*SOD*P*FAST*1*_*_*_", "name": path,
                         "chargingConnectorsStats": [{"standard": "combo_t2", "maxPowerInW": 150000,
                                                      "availableConnectorCount": 0, "totalConnectorCount": 2}]}

        with patch.object(watch, "request", side_effect=fake_request):
            rows = watch.capture_network("IZIVIA FAST", watch.NETWORKS["IZIVIA FAST"], 2, minimum=2)
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["status"] for r in rows}, {"no_direct_price"})
        self.assertEqual(rows[0]["connectorStats"][0]["totalConnectorCount"], 2)
        self.assertNotIn("availableConnectorCount", rows[0]["connectorStats"][0])
        self.assertTrue(any(c[0] == "map/markers" and c[2]["filters"]["marketingNetworkIds"] == [watch.NETWORKS["IZIVIA FAST"]["id"]] for c in calls))

    def test_comparison_reports_direct_price_change_and_station_removal(self):
        row = {"mapId": "a", "legacyId": "x", "code": "1", "name": "Site", "address": None,
               "directRawPricing": ["0.30€/kWh"], "connectorStats": [], "status": "direct_price_published"}
        before = {"networks": {"IZIVIA FAST": [row], "IZIVIA Express": []}}
        after = {"networks": {"IZIVIA FAST": [{**row, "directRawPricing": ["0.35€/kWh"]}],
                              "IZIVIA Express": []}}
        self.assertEqual(watch.compare(before, after)["IZIVIA FAST"]["tariffChangedMapIds"], ["a"])
        with self.assertRaisesRegex(RuntimeError, "coverage fell"):
            watch.compare(before, {"networks": {"IZIVIA FAST": [], "IZIVIA Express": []}})


if __name__ == "__main__":
    unittest.main()
