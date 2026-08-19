# Tesla Charge Companion Data Lab

Public data-research repository for **Tesla Charge Companion**.

This repository is intentionally separated from the private research archive. Everything committed here — including Git history, Actions logs and artifacts — must be safe to expose publicly.

## Public-data rules

Only public charging-infrastructure identifiers, public source URLs, generic extraction code and non-sensitive derived reports belong here.

Do **not** commit credentials, API keys, cookies, authenticated-account exports, screenshots, personal information, private debug logs or copied history from private repositories.

A safety scanner runs before generated data is published.

## Current scope: Lidl France

The first pipeline researches operator-direct Lidl charging tariffs at EVSE level through a public direct-payment flow.

Sanitized seed snapshot:

- 1,405 physical Lidl charging sites represented in the source snapshot
- 6,334 `FR*LDL*…` EVSE identifiers
- source snapshot generated 2026-08-18
- committed seed contains only the EVSE identifier list in compressed text form
- no private repository history, account data, screenshots, cookies, tokens or authenticated exports are copied here

The national extraction produces a separate **candidate** operator-direct dataset. It is not production data until representative stations have been manually validated.

Reference manual check currently used for validation: `FR*LDL*E00002411` should return **0.29 EUR/kWh** for the Lidl Rue de l'Aerostation Maritime site when the public source and Lidl Plus tariff are aligned.

## Repository layout

- `data/seed/` — sanitized public extraction seeds
- `data/operator_direct/` — generated candidate operator-direct datasets
- `scripts/` — public extraction and safety tooling
- `reports/` — concise extraction/validation reports
- `.github/workflows/` — reproducible public Actions pipelines

Long-term target: move collection workloads to Cloudflare and keep GitHub as a transparent validation/publication layer.
