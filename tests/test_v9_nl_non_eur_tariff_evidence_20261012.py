import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
spec = importlib.util.spec_from_file_location("currency",ROOT/"scripts/v9_nl_non_eur_tariff_evidence_20261012.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def fixture(currency, amounts):
    keys=list(audit.REFERENCES)
    tariffs={}
    for key in keys:
        want=audit.REFERENCES[key][1]
        tariffs[key]={"currency":currency if key==keys[0] else want,"elements":[{"priceComponents":[{"type":"ENERGY","priceInclVat":x} for x in amounts]}]}
    return {"generatedAt":"2026-10-11T10:32:38Z","tariffs":tariffs,"stations":[]}

class NonEurTariffEvidenceTest(unittest.TestCase):
    def test_zero_requires_explicit_nonempty_components(self):
        d=audit.audit(fixture("USD",[0.0]))
        self.assertTrue(d["tariffs"]["NL:NUO:Free"]["allNonemptyInclusiveComponentAmountsZero"])
        d2=audit.audit(fixture("USD",[]))
        self.assertFalse(d2["tariffs"]["NL:NUO:Free"]["allNonemptyInclusiveComponentAmountsZero"])
        self.assertFalse(d2["publishedToTcc"])
    def test_changed_source_currency_is_not_silently_converted(self):
        with self.assertRaisesRegex(ValueError,"source currency drift"):
            audit.audit(fixture("EUR",[.29]))

if __name__ == "__main__":
    unittest.main()
