# Tesla Charge Companion Data Lab

Public data-research repository for **Tesla Charge Companion**.

This repository is intentionally separated from the private research archive. Everything committed here — including Git history, Actions logs and artifacts — must be safe to expose publicly.

## Public-data rules

Only public charging-infrastructure identifiers, public source URLs, generic extraction code and non-sensitive derived reports belong here.

Do **not** commit credentials, API keys, cookies, authenticated-account exports, screenshots, personal information, private debug logs or copied history from private repositories.

A safety scanner runs before generated data is published.

## Current scope: Lidl France

The first public pipeline probes Lidl EVSEs through the public Intercharge direct-payment flow.

Important source classification: this public payment flow is **not treated as Lidl Plus pricing**. The first manual validation showed that `FR*LDL*E00002411` is **0.29 EUR/kWh in Lidl Plus** while the public Intercharge ad-hoc payment page returned **0.39 EUR/kWh** at the same EVSE. These two tariff sources must therefore remain separate.

The current smoke seed contains only a small sanitized EVSE sample. National extraction will be enabled only after the source classification and publication model are validated.

Generated public-payment data is stored as **candidate ad-hoc pricing**, never as a Lidl Plus operator-direct tariff.

## Repository layout

- `data/seed/` — sanitized public extraction seeds
- `data/adhoc_payment/` — public ad-hoc payment candidates
- `data/operator_direct/` — reserved for operator/app tariffs that are actually validated as such
- `scripts/` — public extraction and safety tooling
- `reports/` — concise extraction/validation reports
- `.github/workflows/` — reproducible public Actions pipelines

Long-term target: move collection workloads to Cloudflare and keep GitHub as a transparent validation/publication layer.
