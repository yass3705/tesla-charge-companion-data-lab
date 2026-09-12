# Spain CPO coherence audit — run 11

Date: 2026-09-12
Result: GREEN_WITH_DOCUMENTED_LEGACY_COUNTER_UNCERTAINTY

Triggered because nominal first-pass progress has remained at the durable lower bound for two consecutive executions after the reconstructed current REVE inventory reached full decision coverage.

## Verified

- Historical reference remains `legacyWorkLabelCount=618`; it is a historical work queue, not an authoritative physical-CPO denominator.
- Durable current REVE replacement inventory contains 148 identities and all 148 have one persisted nominative decision.
- Category reconciliation is exact and disjoint at the stored counter level: `14 sourceValidated + 4 partial + 35 active + 84 setAside + 3 excludedPlatform + 8 supersededAlias = 148`.
- Durable first-pass lower bound remains `148/618`; maximum unnamed historical remainder is 470. No identity is synthesized from that numeric gap.
- The structured historical reconstruction attempt is closed by `docs/spain-legacy-inventory-reconstruction-audit-2026-09-12.md`; broad history/artifact searches must not be replayed without genuinely new durable evidence.
- Current-snapshot aliases/platform exclusions are retained in the canonical decision accounting and do not inflate the physical-CPO denominator.
- No set-aside case is reopened in this audit and no repeated tariff investigation is performed without new evidence.
- Critical country progress is persisted in Git (`docs/spain-cpo-progress-2026-09.json` plus the reconstruction audit), rather than relying on Actions artifacts.
- REVE tariff/status cursors and the last-run record are persisted on `tesla-charge-companion-stable@spain-reve-preintegration`; national `/locations` collection remains closed.

## Anti-stagnation action

With the durable 148/148 replacement inventory exhausted, nominal first-pass growth is permitted only from a newly discovered durable label identity with provenance. REVE tariff/status pagination may continue independently under the one-batch-per-hour / five-request hard limit. Existing difficult or set-aside cases remain untouched until the historical first pass can be advanced by new evidence or the first-pass phase is otherwise legitimately completed.
