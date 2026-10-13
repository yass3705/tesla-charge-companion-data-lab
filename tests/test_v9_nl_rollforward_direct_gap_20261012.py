import importlib.util
import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("rolling",ROOT/"scripts/v9_nl_rollforward_direct_gap_20261012.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class RollforwardTest(unittest.TestCase):
    def test_comparison_distinguishes_new_connectors_from_missing_refs(self):
        old={"datasetGeneratedAt":"2026-10-11T10:30:00+00:00",
             "totals":{"type2CcsConnectorOccurrences":5,"activeAvailableOrCharging":4,
                       "activeWithTariffReference":3,"activeWithoutTariffReference":1},
             "operatorRows":{"AAA":{"activeAvailableOrCharging":4,"activeWithoutTariffReference":1}}}
        latest={"datasetGeneratedAt":"2026-10-12T10:56:00+00:00",
             "totals":{"type2CcsConnectorOccurrences":6,"activeAvailableOrCharging":5,
                       "activeWithTariffReference":3,"activeWithoutTariffReference":2},
             "operatorRows":{"AAA":{"activeAvailableOrCharging":5,"activeWithoutTariffReference":2}}}
        a={"totalActiveType2CcsConnectorOccurrences":4,
           "counts":{"compiledNotSimulated":3,"noNationalReference":1},
           "cpoBreakdown":{"AAA":{"activeType2Ccs":4,"compiledNotSimulated":3,"noNationalReference":1}}}
        b={"totalActiveType2CcsConnectorOccurrences":5,
           "counts":{"compiledNotSimulated":3,"noNationalReference":2},
           "cpoBreakdown":{"AAA":{"activeType2Ccs":5,"compiledNotSimulated":3,"noNationalReference":2}},
           "compilerRejectionReasons":{},"examplesByClass":{}}
        r=mod.compare(old,latest,a,b,"old","new")
        self.assertEqual(r["delta"]["activeWithoutTariffReference"],1)
        self.assertEqual(r["operatorsByCurrentMissingRef"][0]["newMissingRef"],2)
        self.assertFalse(r["publishedToTcc"])
    def test_reconciles_incomplete_baselines_fail_closed(self):
        old={"datasetGeneratedAt":"a","totals":{"activeAvailableOrCharging":2,
                    "activeWithoutTariffReference":1,"activeWithTariffReference":1},"operatorRows":{}}
        comp={"totalActiveType2CcsConnectorOccurrences":1,"counts":{"noNationalReference":1}}
        with self.assertRaisesRegex(ValueError,"Prior scope"):
            mod.compare(old,old,comp,comp,"x","y")
if __name__=="__main__":unittest.main()
