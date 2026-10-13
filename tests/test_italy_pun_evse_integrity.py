import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/audit_italy_pun_evse_integrity.py"
spec = importlib.util.spec_from_file_location("audit_it_evse", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ItalianEvseIntegrityTests(unittest.TestCase):
    def example(self):
        evses = [{"evseId": f"IT*EVSE*{i}"} for i in range(75025)]
        stations = [{"stationKey": f"pun:{i}", "evseCount": 0, "evses": []} for i in range(29696)]
        stations[0]["evseCount"] = len(evses)
        stations[0]["evses"] = evses
        return {"country": "IT", "dataset": "pun-national-italy",
                "stations": stations, "evses": evses,
                "scope": {"punTariffsRankable": False}}

    def test_valid_complete_identity(self):
        self.assertTrue(mod.audit(self.example())["readyToGenerateTiles"])

    def test_missing_evse_in_station_rejected(self):
        p = self.example()
        p["stations"][0]["evses"].pop()
        p["stations"][0]["evseCount"] -= 1
        self.assertIn("station EVSE membership not a bijection", mod.audit(p)["errors"])

    def test_raw_pun_prices_cannot_be_ranked(self):
        p = self.example()
        p["scope"]["punTariffsRankable"] = True
        self.assertIn("raw PUN tariffs must be non-rankable", mod.audit(p)["errors"])


if __name__ == "__main__":
    unittest.main()
