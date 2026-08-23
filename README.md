# Tesla Charge Companion Data Lab

Public data-research repository for **Tesla Charge Companion**.

This repository is intentionally separated from the private research archive. Everything committed here — including Git history, Actions logs and artifacts — must be safe to expose publicly.

## Public-data rules

Only public charging-infrastructure identifiers, public source URLs, generic extraction code and non-sensitive derived reports belong here.

Do **not** commit credentials, API keys, cookies, authenticated-account exports, screenshots, personal information, private debug logs or copied history from private repositories.

A safety scanner runs before generated data is published. Public mobile-app research must additionally avoid persisting raw APK/XAPK files, JWTs, Supabase client keys, tenant/organisation identifiers or authenticated request material. Such material may only be used transiently at runtime when it is explicitly public client configuration and only for read-only requests permitted by the client/backend.

## France scope: Lidl

Two distinct public tariff channels are intentionally kept separate:

1. **Lidl Plus / operator_direct** — sourced from Lidl France's official public E-Mobility page. Lidl explicitly states that the same per-kWh tariff applies everywhere in France, so this is modeled as a national network rule rather than 6,334 duplicated EVSE tariffs. The monitor extracts AC/DC prices, preauthorisation amounts and promotion status without using an authenticated Lidl account or private API.
2. **Intercharge ad-hoc payment / adhoc_payment** — EVSE-level public direct-payment pricing. This is not assumed to equal Lidl Plus. A smoke validation showed that `FR*LDL*E00002411` can return a different ad-hoc price from the Lidl Plus app tariff.

The official Lidl Plus rule is written to `data/operator_direct/lidl_plus_france.json` only when the tariff evidence changes. A lightweight public GitHub Action checks the official page daily without creating needless daily commits when the tariff is unchanged.

Generated public-payment data remains candidate data until representative checks confirm the intended source interpretation.

## Morocco scope

The Morocco public lab currently tracks **FastVolt, Kilowatt, EVPlug/EvOne, TotalEnergies Club EV-Charge, Shell Recharge/Vivo Energy and EVGO**. Tesla is intentionally outside this non-Tesla investigation.

The key modeling rule is that **CPO/operator, site brand and app/access network are different concepts**. A station appearing inside Kilowatt, EVGO or another app does not by itself prove that the app provider is the charging-point operator. For example, `TotalEnergies Al Waha` is visible in Kilowatt with a free 22 kW connector while it was not found in the TotalEnergies Club EV-Charge station list during the same manual check; its CPO therefore remains unresolved until backend/operator metadata confirms it.

Sanitized manual app observations are stored in `data/seed/morocco_manual_app_observations.json`. Screenshots themselves are deliberately not committed. The migration baseline and current blockers are documented under `reports/morocco/`.

The public workflow `.github/workflows/morocco-public-probe.yml` downloads public Android packages only into temporary storage, mines charging-infrastructure signals, performs explicit read-only probes, removes all raw client material and persists only a field-whitelisted summary.

## France scope: Electric 55 Charging (E55C)

The E55C national station inventory is built exclusively from the official E55C static IRVE resource on data.gouv.fr. A row qualifies only when the schema field `nom_operateur` strictly identifies Electric 55 Charging; the dataset publisher, infrastructure owner (`nom_amenageur`) and commercial brand (`nom_enseigne`) are never used as substitutes for CPO identity.

The generated file `data/national/electric55_stations_france.json` preserves station and EVSE roaming identifiers, coordinates, connector types, nominal power and access/payment metadata. Exact direct-payment links come from the public E55C map, and machine-readable consumer prices come from the read-only tariff display used by E55C Scan Pay for the exact charge point. Charging-time, parking-time, energy and session-fee dimensions remain separate; third-party eMSP prices are excluded.

Dynamic availability is intentionally excluded and must be joined in TCC from Electroverse or Electra. The daily workflow checks one representative of each globally scoped tariff profile plus every new charge point; Sundays and explicit full-refresh runs recheck every mapped E55C charge point.

## Repository layout

- `data/seed/` — sanitized public extraction seeds and manually verified observations
- `data/adhoc_payment/` — public ad-hoc payment candidates
- `data/operator_direct/` — validated-source operator/app tariff rules
- `scripts/` — public extraction and safety tooling
- `reports/` — concise extraction/validation reports
- `.github/workflows/` — reproducible public Actions pipelines

Long-term target: move collection workloads to Cloudflare and keep GitHub as a transparent validation/publication layer.
