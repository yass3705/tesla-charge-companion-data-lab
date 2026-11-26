# G6.5b — Draft integration contract (not authorized for deployment)

- National IRVE identity master; Electroverse enriches existing exact identity pairs only. Tesla independent; other countries/channels unchanged. No new collection.
- Input: verified raw signature and lineage, explicit UTC-offset start / Europe/Paris, energy kWh, integer elapsed/charge/parking seconds, charge+parking=elapsed, maximum seven days; reject incomplete/unsupported input. Explicit congestion option must be represented or fail closed; never silently ignore unverified fees.
- Output: diagnostic status, reason, currency EUR, per-component and total amount only if gate + candidate converge; retain canonical and exact segment estimates separately if explained, source artifact/code SHA, raw signature and session; no promotion from this draft. Undefined cost/km for zero energy; actual UI efficiency must replace illustrative 0.18 kWh/km.
- Clock/date families use phase-aware models; other families conservative envelope. Calendar gaps, conflicting models, unknown energy allocation or engine mismatch fail closed. Technical rounding reconciliation requires independent exact segment calculation and same cents, no arbitrary epsilon.
- Preserve prior estimates and original decisions; do not claim invoice or live price certification. Incalculable offers remain visible but unranked, explicit reason; never use zero as missing. Rank only eligible estimates; geography/power/plug/channel filters and congestion controls must be tested in isolated runtime preview. Ranking by total and cost/km, deterministic ties, top20 pagination, no supplier calls.
- Before integration: prove source artifact durability and deployment authorization, full UI/runtime regression, G0–G9 governance, separate Production review. G5/G6 PARTIAL. No code changes to Production in this step.

## G6.6a / G6.6b-1

G6.6a technical PASS approved; see versioned memory. G6.6b-1 starts with an immutable crosswalk to actual canonical national catalogue, without runtime activation. Exact national station/EVSE/connector attributes and public-access checks, retain all refusals. No frozen quote may substitute a dynamic session gate. Full G6.6b not yet PASS.

## G6.6b-2

G6.6b-1 import executed but exact crosswalk FAIL (0/24115). Correct canonical label parsing only and use pinned compatible November static/dynamic en_service projection. Compare archived Direct/Electra exact scopes without promotion; do not infer price parity or relax G5. No runtime activation. See memory for evidence.

## G6.6b-3

Candidate November active crosswalk accepted (24102 exact, 13 missing power excluded). Isolated callable quote adapter: verify source/target/signature and exact session; recompute oracle and candidate; no frozen quote. Explicit true congestion retains known raw components, false fails closed until separate classification proven. No runtime or public activation; real Direct/Electra non-regression and durable evidence remain open.

## G6.6b-4

G6.6b-3 PASS technical. Explicit opt-in in actual session engine; test runtime-generated requests with the verified gate through isolated two-pass transport. Exact generation and session response verification, reject explicit chargeTimeline until supported and congestion exclusion unproven. No browser endpoint, deployment, actual UI/other lanes certification. See memory.

## G6.6b-4 retry

Runtime replay 45868606202 failed on reverse-input rank equality, not on quote transport. Stable tie-breaks in actual bridge, unchanged primary criteria and replay assertions. New pin and regression test only; no data or gate change. See memory.

## G6.6b-5a

Actual planner fractional timeline protocol; first conservative tranche for unrestricted and duration-only invariant rate envelopes with candidate agreement. Fee exclusion supported only with archived proof of no positive temporal components, not relabeling time/parking as congestion. Variable clock/calendar rates and external fee semantics unresolved. No browser endpoint, publication or durable archival yet. See memory.

## G6.6b-5b

Clock/date extension isolated; actual modeled step energy allocation by elapsed UTC intersection, require exact energy/duration conservation, retain G6.4c model alternatives and candidate agreement. Mixed duration+clock remains unresolved, congestion proof unchanged. No browser endpoint, publication or durable archival. Prior gates unchanged.
