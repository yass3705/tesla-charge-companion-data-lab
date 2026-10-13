# EnergyVision Belgium DATEX — live authenticated acquisition evidence (2026-10-13)

## Scope and provenance

- Provider: EnergyVision / CPO Belgium.
- API: `https://datex.cpo.energyvision.be/datex` with `Authorization: Bearer` from repository secret `ENERGYVISION_API_KEY`.
- Initial authentication proof: [workflow 38288652812](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38288652812) (12 Oct), `metadata=200`, `health=200`.
- Static/dynamic read-only schema and collection: [workflow 38417695881](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38417695881), 13 Oct, all endpoints `200`.
- Structural JSON evidence: Actions artifact `energyvision-datex-structural-audit-38417695881` (7 days); only tag/attribute names, counts and SHA-256; no XML bodies, site identifiers, prices or credentials are copied into the repository.

## Exact structural counts observed

| Source | Size | XML evidence |
| --- | ---: | --- |
| `/metadata` | 1,456 bytes | 1 publisher metadata document; 2 declared feed records |
| `/health` | 782 bytes | 2 feed health records |
| `/energy-infrastructure-table` | 13,498,261 bytes | 1,236 `energyInfrastructureSite`, 1,236 `energyInfrastructureStation`, 3,791 `refillPoint`, 3,791 `connector`, 1,226 `energyRate`, 4,778 `energyPrice` |
| `/energy-infrastructure-status` | 1,807,691 bytes | 1,238 `energyInfrastructureSiteStatus`, 1,238 `energyInfrastructureStationStatus`, 3,795 `refillPointStatus` |

**Counts are XML occurrences, not certified public/operational/priceable V9 EVSE.** Static vs dynamic differences may be natural at collection time; they require exact ID reconciliation before classifying missing/added points.

The observed static feed carries EVSE IDs and connectors under `energyInfrastructureStation/refillPoint`, while rates are nested `energyInfrastructureStation/energyProduct/energyRate/energyPrice`. We must not automatically attach any station-level rate to every connector. Source `ratePolicy`, power/current, connector, price group, time applicability and TVA must be checked first.

Price-related XML contains `priceGroupIndex`, `priceType`, `value`, `taxIncluded`, `taxRate` and `timeBasedApplicability`, including 4,219 applicability nodes. Rates and price components are **not** independent priceable session offers. No inferred direct ad-hoc price has been sent to the V9 registry.

## Next stage

- [Data Lab #251](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/251) stages site IDs, station IDs, refillPoint IDs, connector types/powers, source rate groups and exact status references in separate fields, then computes identity and pricing taxonomy counts. This is an **audit artifact** only, not a published tariff overlay.
- Follow with a comparison against the canonical Belgium NAP dataset by exact EVSE ID, normalization where unambiguous, coordinates, connector and power. Exclude private and unsupported connectors.
- Only after tariff groups/taxes/time windows and EVSE scope have independent evidence, prepare a separate price-adapter PR and pinned V9 development candidate.

No changes to Production, Stable, Pages, Cloudflare or public price ranking.
