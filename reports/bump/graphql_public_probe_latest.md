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

- `incidentDetectedDefects` → `IncidentDetectedDefectQueryController` — `no args`
- `incidentReportedDefects` → `IncidentReportedDefectQueryController` — `no args`
- `incidents` → `IncidentQueryController` — `no args`
- `interventions` → `InterventionQueryController` — `no args`
- `locations` → `LocationQueryController` — `no args`
- `operators` → `ChargePointOperatorQueryController` — `no args`

## Namespace `tariffs` → `TariffsQueryController`

- `detail` → `Tariff` — `tariffGroupId:NON_NULL/TariffGroupId, evseId:EvseId, hasAnonymous:Boolean`
- `details` → `TariffGroupDetail` — `inputs:NON_NULL/LIST/NON_NULL/TariffGroupDetailInput`
- `simulateTariff` → `TariffCalculatorOutput` — `coordinates:NON_NULL/ChargePointCoordinatesInput, tariffId:NON_NULL/TariffId, chargingInput:ConsumptionInput, parkingInput:ParkingInput, reservationInput:ReservationInput`
- `simulateTariffGroup` → `TariffCalculatorOutput` — `coordinates:NON_NULL/ChargePointCoordinatesInput, tariffGroupId:NON_NULL/TariffGroupId, chargingInput:ConsumptionInput, parkingInput:ParkingInput, reservationInput:ReservationInput`

## Namespace `locationPlanning` → `LocationPlanningQuery`

- `locationPlan` → `LocationPlan` — `locationId:NON_NULL/LocationId`
- `locationZones` → `LocationZone` — `locationId:NON_NULL/LocationId`
- `parkingSpaces` → `ParkingSpace` — `locationId:NON_NULL/LocationId`

## TCC rule

This probe only establishes public schema metadata. Station prices remain non-rankable until an explicit tariff query can be matched to Bump's official station/PDC inventory.
