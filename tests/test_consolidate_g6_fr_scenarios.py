import unittest
from scripts.consolidate_g6_fr_scenarios import gate,key,AGREE,AMBIG,DATE,valid_amount
class TestGate(unittest.TestCase):
    def setUp(self):
        self.session=dict(startAt="2026-11-25T10:00:00Z",energy="10",duration=60,charging=45,parking=15)
        self.record=dict(session_key=key(self.session),decision=AGREE,estimate_eur="5.10")
    def test_exact(self):self.assertEqual(gate(self.record,self.session),"DIAGNOSTIC_CONDITIONAL_AGREEMENT")
    def test_label_irrelevant(self):self.assertEqual(gate(self.record,dict(self.session,id="other")),"DIAGNOSTIC_CONDITIONAL_AGREEMENT")
    def test_mutations(self):
        for k,v in dict(startAt="2026-11-26T10:00:00Z",energy="11",duration=61,charging=46,parking=16).items():
            self.assertEqual(gate(self.record,dict(self.session,**{k:v})),"INCALCULABLE_UNTESTED_SESSION")
    def test_missing(self):self.assertEqual(gate(self.record,{}),"INCALCULABLE_UNTESTED_SESSION")
    def test_no_record(self):self.assertEqual(gate(None,self.session),"INCALCULABLE_UNTESTED_SESSION")
    def test_ambiguity(self):
        for d in (AMBIG,DATE,"HISTORICAL_REPLAY_ONLY"):
            self.assertEqual(gate(dict(self.record,decision=d),self.session),"INCALCULABLE_REVIEW")
    def test_invalid_amount(self):
        for v in ("","NaN","Infinity","-1",None):
            self.assertFalse(valid_amount(v))
            self.assertEqual(gate(dict(self.record,estimate_eur=v),self.session),"INCALCULABLE_REVIEW")
    def test_zero(self):self.assertTrue(valid_amount("0"))
