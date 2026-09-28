# Belgium NAP bootstrap — 2026-09-28

## Objective

Use the official Belgium NAP DATEX II feed from Eco-Movement as the national
inventory baseline for Tesla Charge Companion V9, then enrich gaps per CPO only
after the national first pass is measured.

## Authentication

The API token is intentionally **not** stored in the repository. The workflow
expects a repository Actions secret named:

`BELGIUM_NAP_TOKEN`

Never commit the token in source, workflow inputs, reports, issues, or logs.

## First authenticated run

Workflow: `.github/workflows/belgium-nap-probe.yml`

It calls:

`GET https://nap-be.eco-movement.com/datex2/v1/locations`

with:

`Authorization: Bearer <secret>`

The raw response is kept only as a short-lived GitHub Actions artifact (7 days).
The repository persists only a structural summary and a sanitized sample:

- `reports/belgium-nap-probe-summary.json`
- `reports/belgium-nap-locations-sample.json`

## After first run

1. Validate the exact production payload schema.
2. Replace heuristic EVSE/connector/operator discovery with exact field paths.
3. Build the canonical Belgium inventory.
4. Measure national coverage and identify CPO/operator gaps.
5. Test `/datex2/v1/status/{evse_id}` on a small representative EVSE sample
   to determine whether ad-hoc price fields are usable for TCC.
6. Only then start per-CPO second-pass tariff work.

## Current blocker

The ChatGPT-side browsing services currently available for this session cannot
perform the authenticated request because their metered browser balances are
exhausted. The GitHub workflow is therefore the safe execution path once the
repository secret is added.
