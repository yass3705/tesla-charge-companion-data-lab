# France canonical IRVE model

Status: **prototype contract for TCC v8 migration**.

## Decision

For France, Tesla Charge Companion uses the national **IRVE static** dataset as
the canonical physical inventory for every public non-Tesla charge point.

The source is not modified. TCC builds a normalized derived layer and attaches
status/tariff enrichments to it.

Tesla remains in its existing dedicated pipeline and is excluded from this
derived non-Tesla layer.

## Source roles and priorities

### Physical inventory

1. `IRVE_STATIC` — authoritative national station/PDC inventory.

Operator-specific inventories are no longer allowed to create a second physical
copy of a charge point already represented by IRVE. Their records become
enrichments.

### Operational status

TCC only needs operational state, not occupancy.

Priority, highest first:

1. `CPO_DIRECT`
2. `IRVE_DYNAMIC`
3. `UNKNOWN`

Allowed normalized values:

- `in_service`
- `out_of_service`
- `unknown`

`occupation_pdc` is ignored.

Electroverse and Electra are **tariff-only** sources and must never set the TCC
operational status.

Status is attached to the PDC, not merely to the station. If a station has a
22 kW PDC in service and a 150 kW PDC out of service, those states remain
independent so TCC power/connector filters can return the correct result.

### Tariff offers

A PDC can expose several offers at the same time:

- `DIRECT_PUBLIC`
- `CPO_SUBSCRIPTION`
- `ELECTROVERSE`
- `ELECTRA`

These offers coexist; one does not overwrite another.

The IRVE static `tarification` field is retained verbatim for provenance and
display. It becomes a calculative `IRVE_FALLBACK_PARSED` offer only when:

1. no structured offer above is available; and
2. the text is unambiguous enough for the strict parser.

The structured IRVE `gratuit=true` flag can also yield a zero-price fallback.
Complex texts involving time/session/parking/subscription/conditional pricing
are display-only and do not participate in cost ranking.

## Enrichment interchange contract

Each adapter exports a small normalized JSON object:

```json
{
  "schemaVersion": "1.0",
  "provider": "Example CPO",
  "sourceKind": "cpo_direct",
  "records": [
    {
      "idPdcItinerance": "FR*ABC*E123",
      "idStationItinerance": "FR*ABC*S123",
      "status": "en_service",
      "asOf": "2026-08-28T08:00:00Z",
      "offers": [
        {
          "type": "DIRECT_PUBLIC",
          "currency": "EUR",
          "energyEurPerKwh": 0.39,
          "calculative": true
        }
      ]
    }
  ]
}
```

Accepted `sourceKind` values:

- `cpo_direct`: status + direct/subscription tariff offers
- `irve_dynamic`: status fallback only
- `electroverse`: tariff offers only
- `electra`: tariff offers only

Matching is exact by `idPdcItinerance` whenever possible. A station identifier
may apply station-level tariff rules to all child PDCs, but station-level status
is deliberately not propagated. Unmatched records are reported rather than
fuzzy-matched automatically.

## Prototype command

Full official national source:

```bash
python scripts/france_irve_canonical.py \
  --out out/france_irve_canonical.json \
  --summary-out out/france_irve_summary.json
```

With enrichments:

```bash
python scripts/france_irve_canonical.py \
  --enrichment out/cpo_direct.json \
  --enrichment out/irve_dynamic.json \
  --enrichment out/electroverse.json \
  --enrichment out/electra.json \
  --out out/france_irve_canonical.json \
  --summary-out out/france_irve_summary.json
```

A limited `--limit N` run is for smoke validation only.

## Migration order

1. Validate the official national IRVE static source against the canonical
   normalizer and quantify Tesla exclusion, missing identifiers and tariff text.
2. Add a normalized IRVE dynamic status adapter as a fallback.
3. Migrate direct CPO sources one at a time, starting with already validated
   national sources. Each adapter should emit status when directly available
   plus direct/subscription tariff offers.
4. Convert Electroverse output to tariff-only enrichment.
5. Convert Electra output to tariff-only enrichment.
6. Compare the derived France dataset against current TCC v8 on a controlled
   region (Yvelines first), including PDC counts, powers, direct tariffs,
   subscriptions and out-of-service cases.
7. Only after parity/regression checks, replace the old France non-Tesla
   station inventory in TCC v8. Tesla remains untouched.

## Non-goals of this first prototype

- no occupancy/free/busy model;
- no fuzzy name/geospatial matching;
- no deletion of existing operator datasets;
- no direct publication into the stable TCC repository;
- no committed national generated JSON while the schema is still under test.
