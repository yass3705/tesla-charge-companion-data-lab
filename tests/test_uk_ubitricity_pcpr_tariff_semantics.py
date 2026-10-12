"""Regression cases from exact UK Ubitricity PCPR/PAYG comparisons."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import uk_ubitricity_pcpr_validate as validator


def band(start, end, net, payg=False):
    restrictions = ({"startTime": start, "stopTime": end} if payg else
                    {"start_time": start, "end_time": end})
    component = ({"dimensionType": "ENERGY", "price": net, "vat": 20.0, "stepSize": 1}
                 if payg else
                 {"type": "ENERGY", "price": net, "vat": 20, "step_size": 1})
    return {"restrictions": restrictions,
            "priceComponents" if payg else "price_components": [component]}


class UbitricityTariffSemanticsTests(unittest.TestCase):
    def test_payg_net_vat_and_specific_window_override_baseline(self):
        pcpr = [band("16:00", "19:59", 0.55), band("07:00", "23:59", 0.4583),
                band("00:00", "23:59", 0.3667), band("00:00", "06:59", 0.3667)]
        payg = [band("00:00", "06:59", 0.3667, True),
                band("00:00", "23:59", 0.3667, True),
                band("07:00", "15:59", 0.4583, True),
                band("16:00", "19:59", 0.55, True),
                band("20:00", "23:59", 0.4583, True)]
        self.assertEqual(validator.grid(pcpr, 0), validator.grid(payg, 0, True))
        self.assertEqual(validator.grid(payg, 0, True)[16 * 60], 0.66)

    def test_real_monday_evening_conflict_is_still_rejected(self):
        pcpr = [band("07:00", "23:59", 0.4667),
                band("19:00", "23:59", 0.4083),
                band("00:00", "06:59", 0.375)]
        payg = [band("00:00", "06:59", 0.375, True),
                band("07:00", "19:59", 0.4667, True),
                band("19:00", "23:59", 0.4083, True),
                band("20:00", "23:59", 0.4667, True)]
        self.assertNotEqual(validator.grid(pcpr, 0)[20 * 60],
                            validator.grid(payg, 0, True)[20 * 60])

    def test_equal_specificity_conflict_is_ambiguous(self):
        with self.assertRaisesRegex(ValueError, "equally specific"):
            validator.grid([band("00:00", "23:59", 0.375),
                            band("00:00", "23:59", 0.4667)], 0)

    def test_public_detail_must_retain_exact_location_identity(self):
        payload = {"id": "new-site", "evses": [{"id": "GB*UBI*E123", "connectors": [
            {"id": "1", "tariffs": [{"id": "rate", "currency": "GBP"}]}]}]}
        with mock.patch.object(validator.urllib.request, "urlopen",
                               return_value=io.BytesIO(json.dumps(payload).encode())):
            with self.assertRaisesRegex(ValueError, "location identity changed"):
                validator.public_sample("old-site", "GB*UBI*E123", "1", "rate")


if __name__ == "__main__":
    unittest.main()
