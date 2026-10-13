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

## Stage 2 — exact identifiers, statuses and pricing taxonomy (13 Oct, 15:09 UTC)

- [Authenticated staging workflow #38419429972](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38419429972) succeeded, alongside its no-secret parser tests. [PR Data Lab #251](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/251) merged at `7f753b7`.
- Short-lived Actions artifact: `energyvision-datex-staging-38419429972` (7 days), with `reports/belgium/energyvision-datex-semantic-audit.json` and `artifacts/energyvision-datex-stage.json.gz`. It contains source station and PDC identifiers and public operator tariff components **without** interpreting them as assignable V9 session prices. No API credential or raw authenticated XML is stored.
- Exactly **1,236 static sites / 1,236 stations / 3,791 PDC / 3,791 connectors**. All PDC have a source external identifier and site coordinates. Connectors comprise **3,667 Type 2** and **124 CCS**; no other connector types in this source run.
- **3,791/3,791 static PDC IDs** match a dynamic PDC ID exactly. The dynamic feed contains **four extra** point references not in the static extract (3,795 dynamic vs 3,791 static); those four must not become phantom stations or receive guessed prices.
- Dynamic states: `available=2,628`, `charging=988`, `unknown=146`, `inoperative=24`, `faulted=9`. The 3,616 available/charging observations are **not** price coverage, and public access still needs verification.
- **1,226 station-level `adHoc` rates**, one per priced station; **ten stations with no rate**. There are **4,778 XML price components**: `pricePerKWh=3,656`, `pricePerMinute=979`, `basePrice=143`. All rate currencies are EUR. All 4,778 source components say `taxIncluded=true`, `taxRate=21`. No component lacked a parseable numeric amount in this staging check.
- Tariff shape: 810 rates contain five components with recurring clock windows and `fromMinute`/`toMinute` restrictions, 169 have `fromMinute`, 247 have no such time restrictions. These are **complex rate conditions**, not five independent prices to add together. The latest source rate `lastUpdated` in this run was 2026-05-26 (earliest 2025-03-17), despite today's successful feed collection; verify rate validity/freshness before numerical ranking.
- Source static SHA-256 `db612cff7e252cfda0adf02e07bb155b3710441e002f0521606bbf106e5c`; dynamic SHA-256 `0f487fc72a0b3095a25e001c78c1a353de5a3699403853d4aa6b7408af3ad1bb`.

### Remaining validation before integrating EnergyVision into V9

1. Compare the 3,791 EnergyVision external EVSE identifiers to the Belgium NAP canonical index and CPO inventories, including duplicate detection, exact connector/power and 5–10 m GPS checks where justified; do **not** attach prices by CPO name or proximity alone.
2. Verify how the source's single station-level rate applies to each PDC, and how clock windows and elapsed-session minute thresholds interact with the grouped price components.
3. Validate source price freshness, tax treatment (already flagged TTC by the source), current status and public access; independently calculate sample ad-hoc sessions.
4. Only then publish a **separate** candidate overlay to Production, preserving current nine-country pin and GitHub Pages untouched until separately approved.

**State: source collection and structural staging successful; no EnergyVision numeric offer published in V9.**

