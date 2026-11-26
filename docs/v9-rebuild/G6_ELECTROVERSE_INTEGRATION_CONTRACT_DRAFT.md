# G6.5b — Draft integration contract (not authorized for deployment)

- National IRVE identity master; Electroverse enriches existing exact identity pairs only. Tesla independent; other countries/channels unchanged. No new collection.
- Input: verified raw signature and lineage, explicit UTC-offset start / Europe/Paris, energy kWh, integer elapsed/charge/parking seconds, charge+parking=elapsed, maximum seven days; reject incomplete/unsupported input. Explicit congestion option must be represented or fail closed; never silently ignore unverified fees.
- Output: diagnostic status, reason, currency EUR, per-component and total amount only if gate + candidate converge; retain canonical and exact segment estimates separately if explained, source artifact/code SHA, raw signature and session; no promotion from this draft. Undefined cost/km for zero energy; actual UI efficiency must replace illustrative 0.18 kWh/km.
- Clock/date families use phase-aware models; other families conservative envelope. Calendar gaps, conflicting models, unknown energy allocation or engine mismatch fail closed. Technical rounding reconciliation requires independent exact segment calculation and same cents, no arbitrary epsilon.
- Preserve prior estimates and original decisions; do not claim invoice or live price certification. Incalculable offers remain visible but unranked, explicit reason; never use zero as missing. Rank only eligible estimates; geography/power/plug/channel filters and congestion controls must be tested in isolated runtime preview. Ranking by total and cost/km, deterministic ties, top20 pagination, no supplier calls.
- Before integration: prove source artifact durability and deployment authorization, full UI/runtime regression, G0–G9 governance, separate Production review. G5/G6 PARTIAL. No code changes to Production in this step.

## G6.6a / G6.6b-1

G6.6a technical PASS approved; see versioned memory. G6.6b-1 starts with an immutable crosswalk to actual canonical national catalogue, without runtime activation. Exact national station/EVSE/connector attributes and public-access checks, retain all refusals. No frozen quote may substitute a dynamic session gate. Full G6.6b not yet PASS.
