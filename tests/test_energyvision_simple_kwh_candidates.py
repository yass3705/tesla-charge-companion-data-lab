"""Simple-source price arithmetic remains separate from V9 offer publication."""
import copy
import unittest
from scripts.energyvision_simple_kwh_candidates import candidates, simple_rate

def sample():
    return {
        "provider":"EnergyVision", "country":"BE", "v9PublicationReady":False,
        "sourceStatic":{"sha256":"b"*64}, "collectedAt":"2026-10-13T17:00:00Z",
        "dynamic":{"refillPointStatuses":[
            {"sourceReferenceId":"P1","status":"available"},
            {"sourceReferenceId":"P2","status":"charging"}]},
        "static":{"sites":[{"sourceSiteId":"S1","stations":[{
            "sourceStationId":"S1a",
            "stationRatesUnassignedToEvse":[{
                "sourceRateId":"R1","ratePolicy":"adHoc", "currency":"EUR",
                "sourceLastUpdated":"2026-03-01T00:00:00Z",
                "priceComponents":[{"priceType":"pricePerKWh","amountSource":"0.38",
                  "taxIncluded":"true","taxRateSource":"21","rawApplicabilityLeaves":[]}]}],
            "refillPoints":[{
                "sourceRefillPointId":"P1","connectors":[{"sourceConnectorType":"iec62196T2","sourcePowerW":"22000","sourceExternalIdentifier":"BE*NRG*1"}]},
                {"sourceRefillPointId":"P2","connectors":[{"sourceConnectorType":"iec62196T2","sourcePowerW":"22000","sourceExternalIdentifier":"BE*NRG*2"}]}
            ]}]}]}
    }

class SimpleKwhTests(unittest.TestCase):
    def test_homogeneous_station_can_produce_only_proof_candidates(self):
        data=candidates(sample())
        self.assertEqual(data["counts"]["homogeneousStations"],1)
        self.assertEqual(data["counts"]["candidateSourcePDC"],2)
        self.assertEqual(data["counts"]["activeSourcePDC"],2)
        self.assertEqual(data["v9PricedPDC"],0)
        self.assertFalse(data["v9PublicationReady"])
        for p in data["pdcCandidates"]:
            self.assertEqual(p["independent20KwhEnergyOnlyExampleEur"],"7.60")
            self.assertFalse(p["v9Priceable"])
            self.assertFalse(p["sourceStationRateScopeVerifiedForPDC"])
    def test_inconsistent_pdc_power_excluded(self):
        s=sample()
        s["static"]["sites"][0]["stations"][0]["refillPoints"][1]["connectors"][0]["sourcePowerW"]="7000"
        self.assertEqual(candidates(s)["counts"],{})
    def test_time_restriction_excluded(self):
        s=sample()
        p=s["static"]["sites"][0]["stations"][0]["stationRatesUnassignedToEvse"][0]["priceComponents"][0]
        p["rawApplicabilityLeaves"]=[{"path":"energyPrice/timeBasedApplicability/fromMinute","value":"360"}]
        self.assertIsNone(simple_rate(s["static"]["sites"][0]["stations"][0]["stationRatesUnassignedToEvse"][0]))
        self.assertEqual(candidates(s)["counts"],{})
    def test_additional_minute_component_excluded(self):
        s=sample()
        r=s["static"]["sites"][0]["stations"][0]["stationRatesUnassignedToEvse"][0]
        r["priceComponents"].append({"priceType":"pricePerMinute","amountSource":"0.10"})
        self.assertIsNone(simple_rate(r))
    def test_missing_ttc_or_wrong_tax_excluded(self):
        s=sample()
        r=s["static"]["sites"][0]["stations"][0]["stationRatesUnassignedToEvse"][0]
        r["priceComponents"][0]["taxIncluded"]="false"
        self.assertIsNone(simple_rate(r))
        r["priceComponents"][0]["taxIncluded"]="true"
        r["priceComponents"][0]["taxRateSource"]="0"
        self.assertIsNone(simple_rate(r))
    def test_duplicate_evse_rejected(self):
        s=sample()
        s["static"]["sites"][0]["stations"][0]["refillPoints"][1]["connectors"][0]["sourceExternalIdentifier"]="BE*NRG*1"
        with self.assertRaises(ValueError):
            candidates(s)
    def test_published_source_rejected(self):
        s=sample();s["v9PublicationReady"]=True
        with self.assertRaises(ValueError):
            candidates(s)

if __name__=="__main__":
    unittest.main()
