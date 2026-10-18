import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from atlante_official import chargeback_evidence_confirmed


class ChargeBackEvidenceTest(unittest.TestCase):
    def test_missing_promotion_does_not_claim_discount(self):
        self.assertFalse(chargeback_evidence_confirmed('Atlante Go 0,29 €/kWh'))

    def test_partial_evidence_does_not_claim_discount(self):
        self.assertFalse(chargeback_evidence_confirmed('Chez Atlante, vous cagnottez 50 %'))

    def test_complete_official_conditions(self):
        self.assertTrue(chargeback_evidence_confirmed('Chez Atlante, vous cagnottez 50 %. Powerdot et ChargeLeague : 10 % de cagnottage. Crédit à disposition que dans les stations Atlante et Powerdot.'))
