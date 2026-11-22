import unittest

from scripts.compare_italy_stable_pun_evse import (
    candidate_inventory, compare, pun_inventory, stable_inventory,
)


def row(station, groups):
    return [station, None, None, 0, 0, None, 0, [], groups]


class ItalyStablePunDeltaTest(unittest.TestCase):
    def test_exact_ids_and_power_differences_without_aliasing_connectors(self):
        old = stable_inventory([row("station-a", [
            ["IT*E1", None, "AC", 22, 1, [], []],
            ["IT*E2", None, "DC", 50, 1, [], []],
            ["IT*E3", None, "AC", 11, 1, [], []],
        ])])
        new = candidate_inventory([row("station-a", [
            ["IT*E1:connector:1", None, "TYPE2", 22, 1, [], ["IT*E1"]],
            ["IT*E2:connector:2", None, "CCS", 150, 1, [], ["IT*E2"]],
        ])])
        pun = pun_inventory({"evses": [
            {"evseId": "IT*E1", "stationId": "station-a", "connectors": [{"standard": "IEC_62196_T2", "maxPowerKw": 22}]},
            {"evseId": "IT*E2", "stationId": "station-a", "connectors": [{"standard": "CCS", "maxPowerKw": 150}]},
            {"evseId": "IT*E3", "stationId": "station-a", "connectors": [{"standard": "CHADEMO", "maxPowerKw": 11}]},
        ]})
        result = compare(old, new, pun)
        self.assertEqual((result["stableOnlyEvseIds"], result["sharedEvsePowerDifferences"]), (1, 1))
        self.assertEqual(result["stableOnly"][0]["reason"], "pun_has_no_supported_powered_connector")
        self.assertEqual(result["powerDifferences"][0]["evseId"], "IT*E2")
        self.assertFalse(result["tariffParityCertified"])

    def test_missing_upstream_and_compact_loss_are_separate(self):
        old = stable_inventory([row("s", [["IT*OLD", None, "AC", 22, 1, [], []],
                                           ["IT*LOST", None, "AC", 22, 1, [], []]])])
        pun = pun_inventory({"evses": [{"evseId": "IT*LOST", "stationId": "s",
                                         "connectors": [{"standard": "TYPE2", "maxPowerKw": 22}]}]})
        result = compare(old, {}, pun)
        self.assertEqual(result["stableOnlyReasons"]["absent_from_pun"], 1)
        self.assertEqual(result["stableOnlyReasons"]["present_in_pun_but_missing_from_compact"], 1)


if __name__ == "__main__":
    unittest.main()
