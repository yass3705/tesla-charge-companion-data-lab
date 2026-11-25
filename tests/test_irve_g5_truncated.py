import unittest
from scripts.audit_irve_g5_truncated import split_id,strict_reference,relation,collision
class TestTruncated(unittest.TestCase):
    def test_prefix(self):self.assertEqual(split_id("FR*FR1*EVSCA2"),("FRFR1E","VSCA2"))
    def test_bump(self):self.assertEqual(relation("FRBMPEBMP7269","BMP7269"),"STRUCTURED_PREFIX_REMOVAL")
    def test_arbitrary(self):self.assertEqual(relation("FRFR1EVSCA2","SCA2"),"ARBITRARY_SUFFIX_ONLY")
    def test_exact(self):self.assertEqual(relation("FRFR1EVSCA2","FRFR1EVSCA2"),"NO_SUFFIX")
    def test_no_padding(self):self.assertEqual(relation("FRFR1E0002","2"),"ARBITRARY_SUFFIX_ONLY")
    def test_nonstandard(self):self.assertEqual(split_id("FRFR1EVSCA.2"),(None,None))
    def test_empty(self):self.assertEqual(strict_reference(None),"")
    def test_collision_national(self):self.assertEqual(collision({1,2},{3},set()),"NATIONAL_MULTIPLE_RAW_OWNERS")
    def test_collision_source(self):self.assertEqual(collision({1},{2,3},set()),"SOURCE_MULTIPLE_EVSE_OWNERS")
    def test_full_id(self):self.assertEqual(collision({1},{2},{3}),"SOURCE_ALREADY_HAS_FULL_NATIONAL_ID")
    def test_unique(self):self.assertEqual(collision({1},{2},set()),"GLOBAL_STRUCTURAL_UNIQUENESS_ONLY")
    def test_missing(self):self.assertEqual(collision(set(),{2},set()),"NO_STRUCTURED_TARGET")
