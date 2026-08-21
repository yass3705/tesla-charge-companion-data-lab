# Hauts-de-France — manual station checks (2026-08-21)

Sanitized derived validation only. No screenshots, credentials or private raw artifacts are stored here.

Reference data:
- current first-party Pass Pass Electrique rules effective 2025-04-01;
- current USEDA DIRVE 02 direct tariff effective 2025-09-01;
- current TE80 direct rules effective 2026-01-28;
- Tesla Charge Companion source-offer display checked manually against the current Electra-rich extraction used by the France catalogue.

## Results

| Station | TCC sample | Result | Notes |
|---|---|---|---|
| Laon \| Place Victor Hugo | DIRVE 02, DC 50 kW, Electra + Electroverse 0.36 EUR/kWh | PASS | The displayed source offers match the raw Electra offer and the current USEDA direct tariff. No time fee is present. |
| Château-Thierry \| Centre Aquatique | DIRVE 02, AC 22 kW, Electra + Electroverse 0.36 EUR/kWh | PASS | Confirms the USEDA 0.36 EUR/kWh rule across a different power class. |
| TE80 - Albert - allée Georges Lamant | AC 22 kW; Electroverse 0.45 EUR/kWh + time rule; Electra exposes two candidate source tariffs and is excluded from ranking | PASS_WITH_SCOPE_NOTE | TCC is faithful to the source offers and correctly treats the Electra ambiguity as non-rankable. The exact TE80 direct rule is a separate local offer and is not yet surfaced as its own direct-network row. |
| AUBY - Parc d'activités les Près Loribes | Pass Pass; Electroverse 0.36 EUR/kWh + 0.04 EUR/min after 180 min; Electra ambiguous | PASS_WITH_SCOPE_NOTE | Electra raw data contains two distinct candidate tariffs for the same location with no reliable connector mapping; the warning/exclusion is correct. The current Pass Pass direct subscriber/non-subscriber grid is a separate offer and should not be inferred from the roaming value. |
| GERBEROY - Rue du Faubourg Saint-Jean | Pass Pass; Electroverse 0.47 EUR/kWh + 0.20 EUR/min after 90 min; Electra ambiguous | PASS_WITH_SCOPE_NOTE | Same ambiguity pattern as Auby. Current Pass Pass direct rapid prices remain separate from the roaming/source offer. |
| FOUQUIERES LES BETHUNES - Actipolis | Pass Pass, ultra-rapid sample; Electroverse 0.51 EUR/kWh + 0.40 EUR/min after 45 min | PASS | This value also matches the current Pass Pass non-subscriber ultra-rapid rule. It remains important to preserve the provider label rather than merge equal-priced offers. |
| ARRAS - Allée du 7e Chasseur | Pass Pass, AC 22 kW; Electroverse 0.36 EUR/kWh + 0.04 EUR/min after 180 min; Electra ambiguous | PASS_WITH_SCOPE_NOTE | Source display and Electra ambiguity handling are correct. The current Pass Pass direct normal tariff is a distinct subscriber/non-subscriber offer and is not yet surfaced separately. |

## Product implications

1. Keep Electra ambiguous offers excluded from ranking until a reliable EVSE/connector mapping exists.
2. Add local direct-network offers as separate providers/offers for USEDA, TE80 and Pass Pass instead of overwriting Electra/Electroverse roaming/source tariffs.
3. For Pass Pass, use the station category (normal / rapid / ultra-rapid / long-stay) and station-displayed tariff as authoritative; do not derive a direct tariff from a generic power threshold alone.
4. Preserve provider identity even when two offers happen to have exactly the same price.

Overall result: the current TCC source-offer rendering behaves correctly on the seven checked Hauts-de-France samples. The remaining gap is presentation/classification of the validated local direct-network offers, not corruption of the Electra/Electroverse source values.
