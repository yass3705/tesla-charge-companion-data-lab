"""A dated two-station tariff probe stays archived and inactive."""

import json
import unittest
from pathlib import Path

from v9_rebuild.orchestrator import ROOT, read_sources


class RetiredElectroverseTargetedTests(unittest.TestCase):
    def test_exact_historical_scope_and_replacement(self):
        retired = json.loads((ROOT / "migration/v9/g2-retired-methods.json").read_text())
        item = next(row for row in retired["retired"]
                    if row["workflow"].endswith("electroverse-targeted-station-probe.yml"))
        self.assertEqual(item["classification"], "historical_targeted_tariff_investigation")
        self.assertFalse((ROOT / item["workflow"]).exists())
        self.assertTrue((ROOT / item["script"]).is_file())
        report = json.loads((ROOT / "reports/electroverse/targeted-station-probe.json").read_text())
        self.assertEqual({row["id"] for row in report["targets"]},
                         {"electra-bois-d-arcy", "lidl-dole"})
        sources = {row["id"] for row in read_sources()}
        self.assertTrue({"FR:electroverse_daily", "FR:electroverse_full", "FR:electroverse_overlay"} <= sources)
        self.assertFalse(any(item["workflow"] in row["legacy_workflows"] for row in read_sources()))


if __name__ == "__main__":
    unittest.main()
