# Allego France archived EVSE route — 28 October 2026

`FR:allego_direct` reads the preserved `data/national/allego_direct_stations_france.json.gz`, SHA-256 `7c860dbe4d6c428d307dc589d8c682660f213e9a3c5f5c4ad3aff739d0ad6386`. It makes no supplier call and changes no rate.

The archive has station IDs, coordinates and explicit IRVE `evseId` values. The normalizer preserves each exact EVSE and its raw source row, including published EVSE-level power, AC/DC kind, direct rate, conditional offers and overstay policy. It creates no connector because the archive provides no connector identity. Each preserved Direct offer has EVSE scope, `connectorId: null` and `calculationStatus: not_evaluated`; it cannot enter pricing or ranking. The archived `rankableDirect` flag is retained as source evidence only, never copied into a V9 validation decision.

The archive's EVSE-level power must not be displayed as a measured power per connector without additional exact topology evidence. Future joins may use the exact IRVE EVSE ID; station name, proximity and power alone cannot assign a tariff.

Proof: `tests/test_v9_canonical_allego_fr.py`, `tests/test_v9_canonical_batch.py`, one-source immutable bundle `f02d887211dee22d73646fa44843e1917bde9b922af9c9e14a43a0996808cee3`, SHA import into Production and `canonical-v9.js` replay: 154 stations, 1,127 EVSE and 1,127 raw offers in this archive, zero connectors or priced offers. These counts describe this snapshot only; they are not acceptance thresholds.
