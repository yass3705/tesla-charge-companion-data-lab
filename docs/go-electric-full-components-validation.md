# Go Electric Italy V9 full components

Validated 2026-09-01 from the public unauthenticated NextCharge UI and exact Go Electric PUN identities.

- 2,214 exact validated Go Electric EVSE.
- time: 1,052 EVSE, EUR/min proven by rendered UI.
- parking: 700 EVSE, EUR/min proven by rendered UI.
- `onNoEnergyDelivery`: 626 EVSE, post-charge connected-time surcharge.
- `onAfterTime`: 74 EVSE, threshold explicitly rendered as elapsed time since connector connection; source `afterTime` is seconds.
- Window restrictions mapped to existing V9 primitives; unsafe boundary crossings fail closed.

Authoritative runs:
- semantics proof: 33551150109 — success.
- full-component activation and existing-engine primitive mapping: 33551692099 — success.

The generated research candidate remains `publicationAllowed=false`; stable runtime publication is handled separately.
