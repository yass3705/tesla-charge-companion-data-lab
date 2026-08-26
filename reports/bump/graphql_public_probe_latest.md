# Bump public GraphQL probe

Unauthenticated, read-only GraphQL meta-query only. No account/session/token or charging action used.

## Endpoint attempts

- `POST /graphql` → **200** — GraphQL Query typename: **true**

Resolved GraphQL endpoint: **/graphql**

## Public query schema

Introspection status: **200**, fields discovered: **30**

- `chargePoints` → `ChargePointsQuery` — args: `no args`
- `locationPlanning` → `LocationPlanningQuery` — args: `no args`
- `tariffs` → `TariffsQueryController` — args: `no args`

## Namespace `chargePoints` → `ChargePointsQuery`

- `incidentDetectedDefects` → `NON_NULL/IncidentDetectedDefectQueryController` — `no args`
- `incidentReportedDefects` → `NON_NULL/IncidentReportedDefectQueryController` — `no args`
- `incidents` → `NON_NULL/IncidentQueryController` — `no args`
- `interventions` → `NON_NULL/InterventionQueryController` — `no args`
- `locations` → `NON_NULL/LocationQueryController` — `no args`
- `operators` → `NON_NULL/ChargePointOperatorQueryController` — `no args`

## Namespace `tariffs` → `TariffsQueryController`

- `detail` → `Tariff` — `tariffGroupId:NON_NULL/TariffGroupId, evseId:EvseId, hasAnonymous:Boolean`
- `details` → `NON_NULL/LIST/NON_NULL/TariffGroupDetail` — `inputs:NON_NULL/LIST/NON_NULL/TariffGroupDetailInput`
- `simulateTariff` → `NON_NULL/TariffCalculatorOutput` — `coordinates:NON_NULL/ChargePointCoordinatesInput, tariffId:NON_NULL/TariffId, chargingInput:ConsumptionInput, parkingInput:ParkingInput, reservationInput:ReservationInput`
- `simulateTariffGroup` → `TariffCalculatorOutput` — `coordinates:NON_NULL/ChargePointCoordinatesInput, tariffGroupId:NON_NULL/TariffGroupId, chargingInput:ConsumptionInput, parkingInput:ParkingInput, reservationInput:ReservationInput`

## Namespace `locationPlanning` → `LocationPlanningQuery`

- `locationPlan` → `LocationPlan` — `locationId:NON_NULL/LocationId`
- `locationZones` → `NON_NULL/LIST/NON_NULL/LocationZone` — `locationId:NON_NULL/LocationId`
- `parkingSpaces` → `NON_NULL/LIST/NON_NULL/ParkingSpace` — `locationId:NON_NULL/LocationId`

## Type `ChargePointTariffGroup` (OBJECT)

- field `id` → `NON_NULL/ChargePointTariffGroupId`

## Type `Evse` (OBJECT)

- field `accessInfo` → `NON_NULL/EvseAccessInfo`
- field `availability` → `NON_NULL/EvseAvailability`
- field `capabilities` → `NON_NULL/LIST/NON_NULL/EvseCapability`
- field `charger` → `Charger`
- field `chargerSatellite` → `ChargerSatellite`
- field `connectors` → `NON_NULL/LIST/NON_NULL/Connector`
- field `currentInfo` → `NON_NULL/EvseCurrentInfo`
- field `id` → `NON_NULL/EvseId`
- field `identifier` → `NON_NULL/EvseIdentifier`
- field `isRoaming` → `NON_NULL/Boolean`
- field `managingGroupId` → `GroupId`
- field `managingUnit` → `B2BCustomerUnit`
- field `ocppHardwareStatus` → `EvseOcppHardwareStatus`
- field `operator` → `ChargePointOperator`
- field `outOfOrderInfo` → `EvseOutOfOrderInfo`
- field `ownerCustomer` → `B2BCustomer`
- field `ownerGroupId` → `GroupId`
- field `physicalReference` → `PhysicalReference`
- field `priceScoring` → `EvseScoring` — `version:String, scoreDate:Date`
- field `reservationInfo` → `NON_NULL/EvseReservationInfo`
- field `shouldBeCounted` → `NON_NULL/Boolean`
- field `state` → `NON_NULL/EvseState`
- field `status` → `NON_NULL/EvseStatus`
- field `tariffGroup` → `ChargePointTariffGroup`

## Type `EvseId` (SCALAR)


## Type `Location` (OBJECT)

- field `address` → `NON_NULL/LocationAddress`
- field `allEvses` → `LIST/Evse`
- field `barriers` → `LIST/AccessBarrier`
- field `canReserve` → `NON_NULL/Boolean`
- field `chargeType` → `NON_NULL/ChargeType`
- field `connectorTypes` → `LIST/NON_NULL/ConnectorType`
- field `coordinates` → `NON_NULL/Point`
- field `evses` → `LIST/Evse`
- field `evsesStatusStateCounts` → `LIST/EvseStatusStateCount`
- field `featuredPartnerOffer` → `PartnerOffer`
- field `hasAtLeastOneAvailableEvse` → `NON_NULL/Boolean`
- field `hasCable` → `NON_NULL/Boolean`
- field `hasMandatoryBarrier` → `NON_NULL/Boolean`
- field `hasPartnerOffers` → `NON_NULL/Boolean`
- field `id` → `NON_NULL/LocationId`
- field `isRoaming` → `NON_NULL/Boolean`
- field `maxPower` → `Power`
- field `mobilityServiceProviders` → `LIST/MobilityServiceProvider`
- field `name` → `NON_NULL/String`
- field `operators` → `NON_NULL/LIST/NON_NULL/ChargePointOperator`
- field `partnerOffers` → `LIST/PartnerOffer`
- field `presentationInfo` → `NON_NULL/PresentationInfo`
- field `priceScoring` → `LocationScoring` — `version:String, scoreDate:Date`
- field `status` → `NON_NULL/LocationStatus`

## Type `LocationQueryController` (OBJECT)

- field `availableEvse` → `Evse` — `id:NON_NULL/LocationId, evseIds:NON_NULL/LIST/NON_NULL/EvseId`
- field `evsesWithLastChargingSession` → `NON_NULL/LIST/NON_NULL/EvseLastChargingSession` — `id:NON_NULL/LocationId`
- field `locationMeterValuesPerMinute` → `NON_NULL/LIST/NON_NULL/LocationMeterValuePerMinute` — `locationId:NON_NULL/LocationId, fromUtc:NON_NULL/DateTime, toUtc:NON_NULL/DateTime, evseIds:LIST/NON_NULL/EvseId`
- field `paginatedViewAllForB2BCustomer` → `NON_NULL/PaginatedOutputOfLocation` — `groupId:NON_NULL/GroupId, pageNumber:NON_NULL/Int, pageSize:NON_NULL/Int`
- field `search` → `NON_NULL/SearchLocationResult` — `input:NON_NULL/LocationSearchInput`
- field `searchAllLocationsPaginated` → `NON_NULL/SearchAllLocationsPaginated` — `input:NON_NULL/LocationSearchInputSearchAndPaginateInput`
- field `searchForB2BCustomer` → `NON_NULL/LIST/NON_NULL/Location` — `groupId:NON_NULL/GroupId, input:NON_NULL/B2BCustomerLocationsSearchInput`
- field `searchForB2BCustomerV2` → `NON_NULL/LIST/NON_NULL/LocationB2BModel` — `groupId:NON_NULL/GroupId, input:NON_NULL/B2BCustomerLocationsSearchInput`
- field `searchV2` → `NON_NULL/SearchLocationResultV2` — `input:NON_NULL/LocationSearchInputV2Input`
- field `searchV3` → `NON_NULL/SearchLocationResultV3` — `input:NON_NULL/LocationSearchInputV3Input`
- field `view` → `Location` — `id:NON_NULL/LocationId`
- field `viewAllForB2BCustomer` → `NON_NULL/LIST/NON_NULL/Location` — `groupId:NON_NULL/GroupId`
- field `viewAllForB2BCustomerV2` → `NON_NULL/LIST/NON_NULL/LocationB2BModel` — `groupId:NON_NULL/GroupId`
- field `viewAllLocationsTariffs` → `NON_NULL/PaginatedOutputOfLocationTariffResult` — `groupId:NON_NULL/GroupId, page:NON_NULL/Int, pageSize:NON_NULL/Int`
- field `viewByIdentifier` → `ViewEvseUsingIdentifierOutput` — `identifier:NON_NULL/EvseIdentifier`
- field `viewByQRUrl` → `ViewEvseUsingQrUrlOutput` — `qrUrl:NON_NULL/String`
- field `viewForB2BCustomer` → `LocationB2BModel` — `id:NON_NULL/LocationId`
- field `viewGroupLocationsForB2BCustomer` → `NON_NULL/PaginatedOutputOfLocationsStatus` — `groupId:NON_NULL/GroupId, pageNumber:NON_NULL/Int, pageSize:NON_NULL/Int, locationsIds:LIST/NON_NULL/LocationId`
- field `viewGroupLocationsOverviewForB2BCustomer` → `NON_NULL/GroupLocationsOverview` — `groupId:NON_NULL/GroupId`
- field `viewLocationTariffs` → `LocationTariffResult` — `groupId:NON_NULL/GroupId, locationId:NON_NULL/LocationId`

## Type `LocationSearchInput` (INPUT_OBJECT)

- input `canReserve` → `Boolean`
- input `capabilities` → `LIST/NON_NULL/EvseCapability`
- input `connectorTypes` → `LIST/NON_NULL/ConnectorType`
- input `hasCable` → `Boolean`
- input `isAvailable` → `Boolean`
- input `isRoaming` → `Boolean`
- input `maxPower` → `Power`
- input `minPower` → `Power`
- input `searchZone` → `NON_NULL/LocationSearchZoneInput`

## Type `LocationSearchInputV2Input` (INPUT_OBJECT)

- input `appendPowerAggregation` → `Boolean`
- input `canReserve` → `Boolean`
- input `capabilities` → `LIST/NON_NULL/EvseCapability`
- input `connectorTypes` → `LIST/NON_NULL/ConnectorType`
- input `evsePriceScores` → `LIST/NON_NULL/ScoreCategory`
- input `hasCable` → `Boolean`
- input `isAvailable` → `Boolean`
- input `isBumpOrPartner` → `Boolean`
- input `isCompanyOwned` → `Boolean`
- input `isRoaming` → `Boolean`
- input `maxPower` → `Power`
- input `minPower` → `Power`
- input `searchZone` → `NON_NULL/LocationSearchZoneInput`
- input `usableBy` → `LIST/NON_NULL/VehicleCompatibilityType`

## Type `LocationSearchInputV3Input` (INPUT_OBJECT)

- input `appendPowerAggregation` → `Boolean`
- input `canReserve` → `Boolean`
- input `capabilities` → `LIST/NON_NULL/EvseCapability`
- input `clusterSize` → `Int`
- input `connectorTypes` → `LIST/NON_NULL/ConnectorType`
- input `evsePriceScores` → `LIST/NON_NULL/ScoreCategory`
- input `hasCable` → `Boolean`
- input `isAvailable` → `Boolean`
- input `isBumpOrPartner` → `Boolean`
- input `isRoaming` → `Boolean`
- input `maxPower` → `Power`
- input `minPower` → `Power`
- input `searchZone` → `NON_NULL/LocationSearchZoneInput`

## Type `LocationSearchPointInput` (INPUT_OBJECT)

- input `latitude` → `NON_NULL/Float`
- input `longitude` → `NON_NULL/Float`

## Type `LocationSearchZoneInput` (INPUT_OBJECT)

- input `bottomRight` → `NON_NULL/LocationSearchPointInput`
- input `topLeft` → `NON_NULL/LocationSearchPointInput`

## Type `Point` (OBJECT)

- field `latitude` → `NON_NULL/Float`
- field `longitude` → `NON_NULL/Float`

## Type `SearchLocationResult` (OBJECT)

- field `facets` → `NON_NULL/SearchLocationFacets`
- field `locations` → `NON_NULL/LIST/NON_NULL/Location`

## Type `SearchLocationResultV2` (OBJECT)

- field `facets` → `NON_NULL/SearchLocationFacets`
- field `locations` → `NON_NULL/LIST/NON_NULL/LightLocation`

## Type `SearchLocationResultV3` (OBJECT)

- field `locations` → `NON_NULL/LIST/NON_NULL/GeoLocationFacet`

## Type `Tariff` (OBJECT)

- field `alternativeText` → `String`
- field `alternativeUrl` → `String`
- field `currency` → `NON_NULL/CurrencyCode`
- field `generatedDescription` → `TariffDescription`
- field `id` → `NON_NULL/TariffId`
- field `name` → `String`
- field `operator` → `NON_NULL/TariffChargePointOperator`
- field `type` → `TariffType`

## Type `TariffCalculatorOutput` (OBJECT)

- field `currency` → `NON_NULL/CurrencyCode`
- field `tariffCalculatorTypeOutputs` → `NON_NULL/LIST/NON_NULL/TariffCalculatorTypeOutput`
- field `totalAmountExcludingVat` → `NON_NULL/Decimal`
- field `totalAmountIncludingVat` → `Decimal`

## Type `TariffGroupDetail` (OBJECT)

- field `evseId` → `EvseId`
- field `tariff` → `Tariff`
- field `tariffGroupId` → `NON_NULL/TariffGroupId`

## Type `TariffGroupDetailInput` (INPUT_OBJECT)

- input `evseId` → `EvseId`
- input `hasAnonymous` → `Boolean`
- input `tariffGroupId` → `NON_NULL/TariffGroupId`

## Type `TariffGroupId` (SCALAR)


## Type `TariffId` (SCALAR)


## TCC rule

This probe only establishes public schema metadata. Station prices remain non-rankable until an explicit tariff query can be matched to Bump's official station/PDC inventory.
