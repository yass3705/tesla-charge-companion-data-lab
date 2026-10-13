"""Only vehicle connectors supported by TCC may enter the NL pilot."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from pilot_electra_nl_emsp import kind  # noqa: E402


class AllowedConnectorTest(unittest.TestCase):
    def test_allowed(self):
        for standard, expected in [('DOMESTIC_E', 'NORMAL'), ('DOMESTIC_F', 'NORMAL'),
                                   ('IEC_62196_T2', 'TYPE2'), ('IEC_62196_T2_COMBO', 'CCS')]:
            self.assertEqual(kind(standard), expected)

    def test_rejected(self):
        for standard in ('CHADEMO', 'IEC_62196_T1', 'IEC_62196_T1_COMBO',
                         'IEC_60309_2_THREE_32', 'TESLA_S', 'DOMESTIC_H'):
            self.assertIsNone(kind(standard), standard)


if __name__ == '__main__':
    unittest.main()
