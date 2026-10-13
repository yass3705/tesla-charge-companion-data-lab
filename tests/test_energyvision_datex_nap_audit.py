"""Fail-closed reconciliation: IDs, kind, watts, GPS, source tariff scope."""
import unittest
from scripts.energyvision_datex_nap_audit import (
    audit_identity, audit_tariff_shapes, connector_kind, distance_metres, normalized
)

def source(id="BE*NRG*EUNIT*1", power="22000", typ="iec62196T2"):
    return {"static":{"sites":[{
        "sourceSiteId":"SITE1","latitude":"50.85","longitude":"4.35",
        "stations":[{"stationRatesUnassignedToEvse":[{
            "priceComponents":[{"priceType":"pricePerKWh",
                "rawApplicabilityLeaves":[]}],"sourceLastUpdated":"2026-05-01"
        }],"refillPoints":[{"sourceRefillPointId":"POINT1",
            "sourcePowerW":power,"connectors":[{
                "sourceExternalIdentifier":id,"sourcePowerW":power,
                "sourceConnectorType":typ}]}]}]}]}}

def destination(id="BE*NRG*EUNIT*1", power=22000, typ="TYPE2", lat=50.85):
    return {"location":"L1","evse":"E1","lat":lat,"lon":4.35,
            "power":power,"kind":typ,"ids":(id,)}

class EnergyvisionNapAuditTests(unittest.TestCase):
    def test_exact_match_with_kind_power_and_gps(self):
        r=audit_identity(source(),[destination()])
        self.assertEqual(r["exactVerified"],1)
        self.assertEqual(r["sourceConnectors"],1)
        self.assertEqual(r["unmatchedIds"] if "unmatchedIds" in r else 0,0)
    def test_unique_safe_id_normalization(self):
        r=audit_identity(source("BENRG_EUNIT-1"),[destination()])
        self.assertEqual(r["normalizedVerified"],1)
    def test_multiple_id_matches_never_auto_join(self):
        r=audit_identity(source(),[destination(),{**destination(),"evse":"E2"}])
        self.assertEqual(r["ambiguousIds"],1)
    def test_incompatible_gps_or_power_is_rejected(self):
        x=audit_identity(source(),[destination(lat=51.0)])
        self.assertEqual(x["exactGPSConflict"],1)
        y=audit_identity(source(),[destination(power=7400)])
        self.assertEqual(y["exactPowerMismatch"],1)
    def test_unsupported_or_mismatched_connector_is_rejected(self):
        x=audit_identity(source(),[destination(typ="CCS")])
        self.assertEqual(x["exactConnectorMismatch"],1)
        self.assertEqual(connector_kind("iec62196T2COMBO"),"CCS")
    def test_unmatched_id_never_becomes_tariff(self):
        x=audit_identity(source(),[destination(id="BE*OTHER*UNKNOWN")])
        self.assertEqual(x["unmatchedIds"],1)
    def test_station_tariff_is_only_taxonomy(self):
        x=audit_tariff_shapes(source())
        self.assertEqual(x["counts"]["simpleSingleComponentStationRates"],1)
        self.assertEqual(x["counts"]["stationAdhocRates"],1)
    def test_distance_and_normalization(self):
        self.assertLess(distance_metres(50.85,4.35,"50.85001",4.35),2)
        self.assertEqual(normalized("BE*NRG*EUNIT*1"),"BENRGEUNIT1")

if __name__=="__main__":
    unittest.main()
