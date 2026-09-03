# Bump direct France — official station inventory

Source: Bump's own daily IRVE dataset on data.gouv.fr. Roaming/partner locations are excluded by construction.

## Coverage

- Official source rows: **2299**
- Bump-operated rows retained: **2299**
- Public stations: **1527**
- Public charge points: **2299**
- Official IRVE `tarification` field present: **false**
- Stations with at least one explicit price candidate: **0**

## Pricing conclusion

Bump's current official IRVE export does **not** publish a `tarification` column. The dataset can authoritatively define the direct-operated station/PDC perimeter, but cannot supply prices. Driver-facing Bump app/API data is required for station-level tariffs.

## Decision rule for TCC

No Bump price is inferred from this inventory. Only explicit, unambiguous station/point prices confirmed against Bump's driver-facing source can be promoted to the TCC tariff layer.
