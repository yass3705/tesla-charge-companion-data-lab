# Electroverse refresh methods

## Legacy sequential method — preserved 2026-09-28

Reference implementation:
`scripts/legacy/electroverse_incremental_refresh_sequential_2026-09-28.mjs`

Source SHA at preservation time: `dbe38c3dee33c01beff0a61a5d11683427f7f820`.

Characteristics:
- one station at a time;
- paced requests via `REQUEST_INTERVAL_MS` (default 1500 ms);
- two single-query attempts;
- paged GraphQL fallback for stations requiring EVSE pagination;
- canonical tariff projection and SHA-256 tariff hash;
- compact `checked-at.json` freshness ledger;
- unchanged tariff hashes do not rewrite station payloads.

This file is the rollback/reference implementation and should not be deleted when the active refresh changes.

## Hybrid candidate validated on 2026-09-28

Validated benchmark configuration:
- batch size 5;
- concurrency 2;
- failed or incomplete batch members retried with the existing single-station query;
- 1,000-station benchmark: 1,000/1,000 final coverage, 50.48 validated stations/minute.

The active implementation should retain the existing single/paged logic as fallback for difficult stations.
