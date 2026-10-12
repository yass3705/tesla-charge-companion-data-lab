import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("nl_compiler_audit", ROOT / "scripts/v9_nl_direct_tariff_compiler_audit_20261012.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

def station(references, *, status="AVAILABLE", standard="IEC_62196_T2", tariffs=None):
    return {
        "generatedAt": "2026-10-11T10:32:38Z",
        "tariffs": tariffs if tariffs is not None else {},
        "stations": [{
            "stationId": "NL:AAA:0001", "partyId": "AAA",
            "coordinates": {"latitude": 52.0, "longitude": 5.0},
            "evses": [{"evseId": "NL*AAA*E1", "status": status,
                       "connectors": [{"id": "c1", "standard": standard, "powerKw": 22,
                                       "tariffKeys": references}]}],
        }],
    }

def good(typ="REGULAR", rate=0.29):
    return {"type": typ, "currency": "EUR", "elements": [{
        "priceComponents": [{"type": "ENERGY", "priceInclVat": rate, "stepSize": 1}]
    }]}


class NLDirectTariffCompilerAuditTest(unittest.TestCase):
    def test_missing_reference_is_price_unavailable_not_incalculable(self):
        result = audit.evaluate(station([]))
        self.assertEqual(result["counts"]["noNationalReference"], 1)
        self.assertEqual(result["counts"]["compiledNotSimulated"], 0)

    def test_ocpi_tariff_compiled_not_claimed_as_simulated(self):
        result = audit.evaluate(station(["t1"], tariffs={"t1": good()}))
        self.assertEqual(result["counts"]["compiledNotSimulated"], 1)
        self.assertIn("NOT_COMPLETE_PRICE_SIMULATION", result["status"])
        self.assertFalse(result["publishedToTcc"])

    def test_unsupported_dimension_and_orphan_reference_fail_closed(self):
        bad = good()
        bad["elements"][0]["priceComponents"][0]["type"] = "RESERVATION"
        result = audit.evaluate(station(["t1"], tariffs={"t1": bad}))
        self.assertEqual(result["counts"]["unsupportedOrIncompleteContract"], 1)
        result2 = audit.evaluate(station(["nonexistent"], tariffs={"not-used": good()}))
        self.assertEqual(result2["counts"]["sourceReferenceUnresolved"], 1)

    def test_conflicting_tariffs_remain_ambiguous(self):
        result = audit.evaluate(station(["t1", "t2"], tariffs={
            "t1": good(rate=0.29), "t2": good(rate=0.39)
        }))
        self.assertEqual(result["counts"]["ambiguousTariff"], 1)

    def test_no_unsupported_plug_or_nonactive_into_scope(self):
        with self.assertRaisesRegex(ValueError, "No active Type 2"):
            audit.evaluate(station(["t1"], status="OUTOFORDER", tariffs={"t1": good()}))
        with self.assertRaisesRegex(ValueError, "No active Type 2"):
            audit.evaluate(station(["t1"], standard="CHADEMO", tariffs={"t1": good()}))

    def test_offers_with_emsp_only_are_not_direct_priced(self):
        result = audit.evaluate(station(["t1"], tariffs={"t1": good("PROFILE_CHEAP")}))
        self.assertEqual(result["counts"]["thirdPartyOrNonDirectOnly"], 1)


if __name__ == "__main__":
    unittest.main()
