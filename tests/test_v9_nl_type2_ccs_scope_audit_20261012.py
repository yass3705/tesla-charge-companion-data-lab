import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("nl_scope", ROOT / "scripts/v9_nl_type2_ccs_scope_audit_20261012.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def station(standard, status="AVAILABLE", refs=None, lat=52):
    return {"stations": [{
        "stationId": "NL:AAA:1", "partyId": "AAA",
        "coordinates": {"latitude": lat, "longitude": 5},
        "evses": [{"evseId": "NL*AAA*E1", "status": status,
                   "connectors": [{"standard": standard, "tariffKeys": refs or [], "powerKw": 22}]}],
    }], "generatedAt": "2026-10-12T00:00:00Z"}


class NLScopeAuditTest(unittest.TestCase):
    def test_type2_available_with_no_reference_is_missing_not_incalculable(self):
        result = m.scan(station("IEC_62196_T2"))
        self.assertEqual(result["totals"]["activeWithoutTariffReference"], 1)
        self.assertEqual(result["totals"]["ccsConnectors"], 0)
        self.assertFalse(result["publication"])
        self.assertIn("NOT_PUBLIC_ACCESS_VERIFIED", result["scope"])

    def test_ccs_charging_with_ref_is_counted_but_not_proven_calculable(self):
        result = m.scan(station("IEC_62196_T2_COMBO", status="CHARGING", refs=["tariff-1"]))
        self.assertEqual(result["totals"]["ccsConnectors"], 1)
        self.assertEqual(result["totals"]["activeWithTariffReference"], 1)
        self.assertEqual(result["totals"]["activeWithoutTariffReference"], 0)

    def test_nonactive_excluded_and_nonstandard_plugs_rejected(self):
        result = m.scan(station("IEC_62196_T2", status="OUTOFORDER"))
        self.assertEqual(result["totals"]["activeAvailableOrCharging"], 0)
        with self.assertRaisesRegex(ValueError, "No Type 2 or CCS"):
            m.scan(station("CHADEMO"))

    def test_out_of_bounds_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "No Type 2 or CCS"):
            m.scan(station("IEC_62196_T2", lat=90))


if __name__ == "__main__":
    unittest.main()
