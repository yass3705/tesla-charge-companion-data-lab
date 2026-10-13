"""EnergyVision DATEX staging must preserve site scope, never invent EVSE prices."""
import unittest

from scripts.energyvision_datex_semantic_stage import audit, interpret_static, interpret_dynamic


STATIC = b"""<?xml version="1.0"?>
<payload xmlns="urn:datex">
 <energyInfrastructureTable>
  <energyInfrastructureSite id="BE_SITE_1">
   <brand><values><value>Example CPO</value></values></brand>
   <typeOfSite><value>onStreet</value></typeOfSite>
   <entrance><pointByCoordinates><pointCoordinates>
    <latitude>50.85</latitude><longitude>4.35</longitude>
   </pointCoordinates></pointByCoordinates></entrance>
   <energyInfrastructureStation id="STATION_1">
   <numberOfRefillPoints>2</numberOfRefillPoints>
   <authenticationAndIdentificationMethods><value>apps</value></authenticationAndIdentificationMethods>
    <refillPoint id="EVSE_A">
      <currentType><value>ac</value></currentType>
      <availableChargingPower>22000</availableChargingPower>
      <connector><connectorType><value>iec62196T2</value></connectorType>
       <maxPowerAtSocket>22000</maxPowerAtSocket>
       <externalIdentifier><identifier>BE*ABC*E1</identifier></externalIdentifier>
      </connector>
    </refillPoint>
    <refillPoint id="EVSE_B">
      <connector><connectorType><value>iec62196T2Combo</value></connectorType></connector>
    </refillPoint>
    <energyProduct>
      <energyRate id="RATE_1">
       <ratePolicy><value>adHoc</value></ratePolicy>
       <applicableCurrency>EUR</applicableCurrency>
       <energyPrice><priceGroupIndex>0</priceGroupIndex>
        <priceType><value>pricePerKWh</value></priceType>
        <value>0.35</value><taxIncluded>false</taxIncluded><taxRate>21</taxRate>
       </energyPrice>
      </energyRate>
      <energyRate id="RATE_2">
       <ratePolicy><value>adHoc</value></ratePolicy>
       <applicableCurrency>EUR</applicableCurrency>
       <energyPrice><priceGroupIndex>1</priceGroupIndex>
        <priceType><value>pricePerMinute</value></priceType><value>0.15</value>
       </energyPrice>
      </energyRate>
    </energyProduct>
   </energyInfrastructureStation>
  </energyInfrastructureSite>
 </energyInfrastructureTable>
</payload>"""
DYNAMIC = b"""<payload xmlns="urn:datex">
 <energyInfrastructureSiteStatus><reference id="BE_SITE_1"/>
  <energyInfrastructureStationStatus><reference id="STATION_1"/>
   <refillPointStatus><reference id="EVSE_A"/><status><value>available</value></status></refillPointStatus>
   <refillPointStatus><reference id="EVSE_B"/><status><value>occupied</value></status></refillPointStatus>
  </energyInfrastructureStationStatus>
 </energyInfrastructureSiteStatus>
</payload>"""


class StageEnergyVisionTests(unittest.TestCase):
    def test_station_rate_is_not_promoted_to_evse(self):
        parsed = interpret_static(STATIC)
        self.assertEqual(len(parsed["sites"]), 1)
        self.assertEqual(parsed["sites"][0]["sourceSiteType"], "onStreet")
        station = parsed["sites"][0]["stations"][0]
        self.assertEqual(station["declaredRefillPoints"], "2")
        self.assertEqual(station["authenticationMethods"], ["apps"])
        self.assertEqual(len(station["refillPoints"]), 2)
        self.assertEqual(len(station["stationRatesUnassignedToEvse"]), 2)
        self.assertEqual(station["stationRatesUnassignedToEvse"][0]["sourceRateId"], "RATE_1")
        self.assertEqual(station["stationRatesUnassignedToEvse"][0]["priceComponents"][0]["amountSource"], "0.35")
        for point in station["refillPoints"]:
            self.assertNotIn("price", point)
            self.assertNotIn("tariff", point)
        self.assertEqual(station["refillPoints"][0]["connectors"][0]["sourceExternalIdentifier"], "BE*ABC*E1")

    def test_exact_dynamic_reference_join_and_publication_gate(self):
        a = {"static": interpret_static(STATIC), "dynamic": interpret_dynamic(DYNAMIC)}
        result = audit(a)
        self.assertEqual(result["counts"]["sites"], 1)
        self.assertEqual(result["counts"]["refillPoints"], 2)
        self.assertEqual(result["counts"]["exactStaticDynamicRefillLinks"], 2)
        self.assertEqual(result["counts"]["stationLevelRates"], 2)
        self.assertEqual(result["counts"]["priceComponents"], 2)
        self.assertFalse(result["v9ReadyForPriceRanking"])

    def test_ambiguous_dynamic_id_stays_unmatched(self):
        wrong = DYNAMIC.replace(b'EVSE_B', b'EVSE_WRONG')
        a = {"static": interpret_static(STATIC), "dynamic": interpret_dynamic(wrong)}
        result = audit(a)
        self.assertEqual(result["counts"]["exactStaticDynamicRefillLinks"], 1)
        self.assertEqual(result["counts"]["staticRefillWithoutDynamic"], 1)
        self.assertEqual(result["counts"]["dynamicRefillWithoutStatic"], 1)


if __name__ == "__main__":
    unittest.main()
