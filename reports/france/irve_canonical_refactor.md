# France IRVE canonical refactor

Status: **parallel prototype — no TCC V8 production cutover yet**.

## Target architecture

The national IRVE static consolidation becomes the canonical physical inventory for public charging points in France, excluding Tesla. Tesla remains in its dedicated TCC pipeline.

### Inventory

- Primary source: national deduplicated IRVE static consolidation.
- Canonical grain: one record per PDC/EVSE.
- Preferred keys: `id_pdc_itinerance`, then `id_pdc_local`, with station IDs retained for grouping.
- CPO inventories already collected in the data-lab become enrichment/matching sources instead of competing physical inventories.

### Operational status

TCC only needs operational state, not occupation.

Priority:

1. direct CPO status (`en_service` / `hors_service`), when a verified public source exists;
2. national IRVE dynamic `etat_pdc` only as an optional fallback;
3. `inconnu` otherwise.

`occupation_pdc` is deliberately ignored. Electroverse and Electra are not status sources in this model.

### Tariffs

Structured tariffs are parallel offers attached to the canonical PDC/station:

- direct CPO public tariff;
- direct CPO subscription tariff(s);
- Electroverse tariff;
- Electra tariff / applicable subscription offer.

The IRVE static `tarification` text is a last-resort fallback only when no structured offer is available. The initial parser only promotes a simple, unambiguous single EUR/kWh value (or an explicit `gratuit=true`) to a machine-calculable tariff. All other text remains display-only and must never enter cost ranking.

### Matching order

1. `id_pdc_itinerance`
2. `id_pdc_local`
3. `id_station_itinerance`
4. `id_station_local`
5. controlled geo/name fallback, with a confidence flag

No enrichment should create a second physical station when a canonical IRVE PDC match exists.

## Phase 1 implemented on this branch

- `config/france_irve_model.json`: source-priority contract.
- `scripts/france_irve_canonical.py`: streaming IRVE static normalizer, Tesla exclusion, safe tariff fallback classification.
- `tests/test_france_irve_canonical.py`: unit guardrails.
- `.github/workflows/france-irve-canonical.yml`: parallel national build and candidate artifact.

The workflow does not publish to TCC V8 and does not commit the large generated national file. The candidate is uploaded as a short-lived Actions artifact for validation.

## Next phases after the national base passes validation

1. Build an enrichment adapter contract and map existing direct-CPO datasets to canonical IRVE IDs.
2. Add verified direct-CPO operational status adapters where available.
3. Convert existing CPO price inventories into tariff-offer layers.
4. Attach Electroverse and Electra prices only.
5. Measure match coverage, duplicates, unmatched offers and fallback-tariff usage nationally, then on a Yvelines control slice.
6. Only after comparison with current V8 output, prepare the production cutover PR.
