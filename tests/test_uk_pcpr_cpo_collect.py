"""Offline safety checks for Allego UK / Source EV Eco-Movement PCPR collector."""
import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts/uk_pcpr_cpo_collect.py"
spec = importlib.util.spec_from_file_location("uk_pcpr", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def location(operator, tariff_ids=None, extra=None):
    item = {
        "id": "L1", "country_code": "GB", "country": "GBR", "party_id": "ABC",
        "operator": {"name": operator}, "publish": True,
        "coordinates": {"latitude": "51.5", "longitude": "-0.1"},
        "evses": [{"uid": "1", "evse_id": "GB*ABC*E1", "status": "AVAILABLE",
                   "connectors": [{"id": "1", "max_electric_power": 22000,
                                   "tariff_ids": tariff_ids if tariff_ids is not None else ["T1"]}]}],
    }
    item.update(extra or {})
    return item


def tariff(id="T1"):
    return {"id": id, "country_code": "GB", "party_id": "ABC", "currency": "GBP",
            "elements": [{"price_components": [{"type": "ENERGY",
                                                "price": 0.5, "step_size": 1}]}]}


class TestUkPcpr(unittest.TestCase):
    def test_each_operator_priced_only_with_exact_connector(self):
        for key, name in (("allego_uk", "Allego UK"), ("source_ev", "Source-EV")):
            with self.subTest(key=key):
                result, audit = module.stage([location(name)], [tariff()], "now", module.provider(key))
                self.assertEqual(audit["pricedExactConnectors"], 1)
                self.assertFalse(audit["publishedToV9"])
                source = result["sources"][0]
                self.assertEqual(source["locations"][0]["evses"][0]["connectors"][0]["tariff_ids"], ["T1"])
                self.assertEqual(source["tariffs"][0]["elements"][0]["price_components"][0]["price"], 0.6)
                self.assertIsNone(source["tariffs"][0]["elements"][0]["price_components"][0]["vat"])

    def test_different_operator_never_published(self):
        for key in module.PROVIDERS:
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError, "No public"):
                    module.stage([location("ChargePoint")], [tariff()], "now", module.provider(key))

    def test_unknown_reference_remains_unpriced(self):
        result, report = module.stage([location("Allego", ["NOPE"])],
                                      [tariff()], "now", module.provider("allego_uk"))
        self.assertEqual(report["unpricedPublicConnectors"], 1)
        self.assertEqual(result["sources"][0]["locations"][0]["evses"][0]["connectors"][0]["tariff_ids"], [])

    def test_ambiguous_reference_fails_closed(self):
        result, report = module.stage([location("Allego", ["T1", "NOPE"])],
                                      [tariff()], "now", module.provider("allego_uk"))
        self.assertEqual(report["pricedExactConnectors"], 0)
        self.assertEqual(result["sources"][0]["tariffs"], [])

    def test_access_dealership_and_operator_rules(self):
        cfg = module.provider("source_ev")
        self.assertEqual(module.eligible_location(location("Source EV", extra={"parking_type": "PRIVATE"}), cfg),
                         "nonpublic_access")
        self.assertEqual(module.eligible_location(location("Source EV", extra={
            "facilities": [{"code": "TRUCK_DEALERSHIP"}]}), cfg), "dealership")
        self.assertEqual(module.eligible_location(location("Allego"), cfg), "wrong_declared_CPO")

    def test_tariff_gbp_and_components(self):
        other = tariff()
        other["currency"] = "EUR"
        self.assertEqual(module.make_tariff(other)[1], "non_GBP_UK_tariff")
        other = tariff()
        other["elements"][0]["price_components"][0]["type"] = "UNKNOWN"
        self.assertEqual(module.make_tariff(other)[1], "unsupported_component")


if __name__ == "__main__":
    unittest.main()
