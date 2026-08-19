# Tesla Charge Companion Data Lab

Public data-research repository for **Tesla Charge Companion**.

This repository is intentionally separated from the private research archive. Everything committed here — including Git history, Actions logs and artifacts — must be safe to expose publicly.

## Public-data rules

Only public charging-infrastructure identifiers, public source URLs, generic extraction code and non-sensitive derived reports belong here.

Do **not** commit credentials, API keys, cookies, authenticated-account exports, screenshots, personal information, private debug logs or copied history from private repositories.

A safety scanner runs before generated data is published.

## Current scope: Lidl France

Two distinct public tariff channels are intentionally kept separate:

1. **Lidl Plus / operator_direct** — sourced from Lidl France's official public E-Mobility page. Lidl explicitly states that the same per-kWh tariff applies everywhere in France, so this is modeled as a national network rule rather than 6,334 duplicated EVSE tariffs. The monitor extracts AC/DC prices, preauthorisation amounts and promotion status without using an authenticated Lidl account or private API.
2. **Intercharge ad-hoc payment / adhoc_payment** — EVSE-level public direct-payment pricing. This is not assumed to equal Lidl Plus. A smoke validation showed that `FR*LDL*E00002411` can return a different ad-hoc price from the Lidl Plus app tariff.

The official Lidl Plus rule is written to `data/operator_direct/lidl_plus_france.json` only when the tariff evidence changes. A lightweight public GitHub Action checks the official page daily without creating needless daily commits when the tariff is unchanged.

Generated public-payment data remains candidate data until representative checks confirm the intended source interpretation.

## Repository layout

- `data/seed/` — sanitized public extraction seeds
- `data/adhoc_payment/` — public ad-hoc payment candidates
- `data/operator_direct/` — validated-source operator/app tariff rules
- `scripts/` — public extraction and safety tooling
- `reports/` — concise extraction/validation reports
- `.github/workflows/` — reproducible public Actions pipelines

Long-term target: move collection workloads to Cloudflare and keep GitHub as a transparent validation/publication layer.
