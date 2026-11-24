import unittest
from scripts.audit_electroverse_g5_real_matching import candidate_checks,ident,plug,mode,power_check,validate_national_projection

class G5RealMatchingTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(ident("FR*PD1*E123-4"),"FRPD1E1234")
        self.assertEqual(plug("IRVE · CCS 150 kW"),"CCS")
        self.assertEqual(plug("IEC_62196_T2_COMBO"),"CCS")
        self.assertEqual(mode("TYPE2"),"AC")
    def test_power(self):
        self.assertEqual(power_check(150,150,"DC"),("PASS",0))
        self.assertEqual(power_check(160,150,"DC"),("FAIL",10))
        self.assertEqual(power_check(21.99,22,"AC")[0],"PASS")
        self.assertEqual(power_check(21,22,"AC")[0],"FAIL")
        self.assertEqual(power_check(None,22,"AC")[0],"MISSING")
    def compare(self, s=None, n=None, loc=None, site=None, exact=True, approved=None):
        return candidate_checks(s or {"plug":"CCS","mode":"DC","kw":100},
            n or {"plug":"CCS","mode":"DC","kw":150},
            loc or {"coords":(49,1),"address":"","country":"FR","foreign_be":False,"operator_id":"123","operator_name":"Example"},
            site or {"coords":(49.001,1),"address":"","operator":"Example"},
            exact,False,True,True,1,approved or set(),"NOT_EVALUATED")
    def test_exact_does_not_override_power_or_operator(self):
        r=self.compare()
        self.assertIn("operator",r["missing"])
        self.assertNotIn("operator:MISSING",r["blocking"])
        self.assertIn("power:FAIL",r["blocking"])
        self.assertEqual(r["criteria"]["gps"],"NOT_APPLICABLE")
        self.assertNotEqual(r["decision"],"MATCH_VALIDATED")
    def test_all_failures_logged(self):
        r=self.compare(s={"plug":"TYPE2","mode":"AC","kw":22})
        for k in ("current:FAIL","plug:FAIL","power:FAIL"):
            self.assertIn(k,r["blocking"])
        self.assertEqual(r["criteria"]["tariff_scope"],"NOT_EVALUATED")
    def test_fallback_and_operator(self):
        r=self.compare(exact=False,approved={("123","EXAMPLE")})
        self.assertEqual(r["criteria"]["operator"],"PASS")
        self.assertEqual(r["criteria"]["gps"],"FAIL")
        self.assertEqual(r["criteria"]["evse_identity"],"MISSING")
        self.assertNotEqual(r["decision"],"MATCH_VALIDATED")
    def test_address_or_gps(self):
        loc={"coords":(49,1),"address":"1 rue test","country":"FR","foreign_be":False,"operator_id":"123","operator_name":"Example"}
        site={"coords":(49.001,1),"address":"1 rue test","operator":"Example"}
        r=self.compare(loc=loc,site=site,exact=False,approved={("123","EXAMPLE")})
        self.assertEqual(r["method"],"address+operator")
        self.assertEqual(r["criteria"]["gps"],"NOT_APPLICABLE")
        self.assertEqual(r["criteria"]["station_identity"],"PASS")
        self.assertNotEqual(r["decision"],"MATCH_VALIDATED")
    def test_missing_attributes_not_blocking_with_positive_identity_scope(self):
        r=candidate_checks({"plug":"CCS","mode":"DC","kw":150},{"plug":"CCS","mode":"DC","kw":150},
            {"coords":(49,1),"address":"","country":"","foreign_be":False,"operator_id":"123","operator_name":""},
            {"coords":(49,1),"address":"","operator":"Example"},True,False,True,True,1,set(),"PASS","PASS","NOT_APPLICABLE")
        self.assertEqual(r["decision"],"MATCH_VALIDATED")
        self.assertEqual(set(r["missing"]),{"country","operator"})
        self.assertEqual(r["blocking"],[])
    def test_positive_scope_still_required(self):
        r=self.compare(s={"plug":"CCS","mode":"DC","kw":150})
        self.assertEqual(r["decision"],"UNRESOLVED_INSUFFICIENT_EVIDENCE")
        self.assertIn("tariff_scope:INSUFFICIENT_EVIDENCE",r["blocking"])
    def test_operational_projection(self):
        rows=[["FRS","Station","",49,1,"OP",4,0,[["g","IRVE · CCS 150 kW","DC",150,4,[],["A","B","C","D"]]]]]
        dyn={"schemaVersion":1,"country":"FR","generatedAt":"2026-10-20T07:36:00Z","sourceSha256":"DYN","enServicePdcIds":["A"],"records":[{"id_pdc_itinerance":"B","id_station_itinerance":"FRS","etat_pdc":"hors_service"},{"id_pdc_itinerance":"C","id_station_itinerance":"FRS","etat_pdc":"inconnu"}],"matchedPdc":3,"displayExcludedPdc":2,"states":{"en_service":1,"hors_service":1,"inconnu":1}}
        meta={"pdcCount":4,"sourceSha256":"STAT"}
        proof={"static":{"sourceSha256":"STAT"},"dynamic":{"sha256":"DYN"}}
        active,owners,status=validate_national_projection(rows,dyn,meta,proof)
        self.assertEqual(active,{"A"})
        self.assertEqual(status,{"A":"en_service","B":"hors_service","C":"inconnu","D":"MISSING"})
        self.assertEqual(len(owners),4)
        dyn["enServicePdcIds"]=["A","B"]
        with self.assertRaises(ValueError):validate_national_projection(rows,dyn,meta,proof)
if __name__=="__main__":unittest.main()
