# Bump official EVSE sample probe

Public unauthenticated GraphQL lookup using one EVSE identifier from Bump's official IRVE dataset.

- Station: **AVIA VOLT - La Guiche**
- EVSE identifier: **FRBMPE0421**
- Declared power: **22 kW**
- GraphQL HTTP status: **200**
- Tariff group IDs discovered: **none**

## Public technical data retained

```json
{
  "chargePoints": {
    "locations": {
      "viewByIdentifier": null
    }
  }
}
```

## GraphQL errors

- The current user is not authorized to access this resource.

## TCC rule

No tariff is published from this sample unless a tariffGroupId is obtained and the corresponding public tariff detail exposes an explicit price structure.
