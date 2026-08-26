# Bump tariff schema

Types discovered: **22**

## `Tariff` (OBJECT)

- `id` → `TariffId`
- `currency` → `CurrencyCode`
- `name` → `String`
- `operator` → `TariffChargePointOperator`
- `type` → `TariffType`
- `generatedDescription` → `TariffDescription`
- `alternativeText` → `String`
- `alternativeUrl` → `String`

## `TariffDescription` (OBJECT)

- `tariffGroupId` → `TariffGroupId`
- `tariffId` → `TariffId`
- `quick` → `String`
- `short` → `String`
- `long` → `String`
- `quickDetail` → `TariffQuickDescriptionInfo`
- `shortDetail` → `TariffShortDescriptionInfo`
- `isTariffChangingInTime` → `Boolean`
- `parking` → `String`

## `TariffGroupDetail` (OBJECT)

- `tariffGroupId` → `TariffGroupId`
- `tariff` → `Tariff`
- `evseId` → `EvseId`

## `TariffCalculatorOutput` (OBJECT)

- `totalAmountExcludingVat` → `Decimal`
- `totalAmountIncludingVat` → `Decimal`
- `currency` → `CurrencyCode`
- `tariffCalculatorTypeOutputs` → `TariffCalculatorTypeOutput`

## `TariffId` (SCALAR)


## `TariffChargePointOperator` (OBJECT)

- `id` → `TariffChargePointOperatorId`

## `TariffType` (ENUM)

- enum: `AD_HOC_PAYMENT`, `PROFILE_CHEAP`, `PROFILE_FAST`, `PROFILE_GREEN`, `REGULAR`

## `TariffGroupId` (SCALAR)


## `TariffQuickDescriptionInfo` (OBJECT)

- `price` → `VatPrice`
- `priceType` → `PriceType`

## `TariffShortDescriptionInfo` (OBJECT)

- `flatFee` → `VatPrice`
- `pricePerKWh` → `VatPrice`
- `pricePerHour` → `VatPrice`
- `minPrice` → `VatPrice`

## `TariffCalculatorTypeOutput` (OBJECT)

- `type` → `TariffCalculatorType`
- `totalAmountExcludingVat` → `Decimal`
- `totalAmountIncludingVat` → `Decimal`
- `amountCategories` → `AmountCategory`
- `priceComponentsOutputs` → `TariffPriceComponentCalculatorOutput`

## `TariffChargePointOperatorId` (SCALAR)


## `VatPrice` (OBJECT)

- `includingVat` → `Price`
- `excludingVat` → `Price`
- `vat` → `TariffVat`

## `PriceType` (ENUM)

- enum: `ENERGY`, `TIME`, `FLAT`

## `TariffCalculatorType` (ENUM)

- enum: `PARKING`, `CHARGING`, `RESERVATION`, `MIN_MAX`

## `AmountCategory` (OBJECT)

- `type` → `AmountCategoryType`
- `amountExcludingVat` → `Decimal`
- `amountIncludingVat` → `Decimal`
- `vat` → `Decimal`

## `TariffPriceComponentCalculatorOutput` (OBJECT)

- `dimensionType` → `TariffDimensionType`
- `amountExcludingVat` → `Decimal`
- `amountIncludingVat` → `Decimal`
- `stepSize` → `Int`
- `consumedSize` → `Decimal`
- `elementId` → `TariffElementId`

## `Price` (OBJECT)

- `currency` → `CurrencyCode`
- `amount` → `Decimal`
- `formattedPrice` → `String`

## `TariffVat` (SCALAR)


## `AmountCategoryType` (ENUM)

- enum: `FLAT`, `TIME`, `ENERGY`, `PARKING_TIME`, `MIN`, `MAX`, `RESERVATION_TIME`

## `TariffDimensionType` (ENUM)

- enum: `ENERGY`, `FLAT`, `TIME`

## `TariffElementId` (SCALAR)

