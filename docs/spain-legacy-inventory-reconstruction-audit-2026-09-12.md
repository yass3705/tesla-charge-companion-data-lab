# Spain legacy 618-label reconstruction audit

Date: 2026-09-12
Status: CLOSED_STRUCTURED_RECOVERY_ATTEMPT_WITH_DOCUMENTED_UNCERTAINTY

## Purpose

This document prevents repeated reconstruction loops around the historical Spain REVE work queue of 618 derived labels. `legacyWorkLabelCount=618` remains a historical work-queue reference, not an authoritative physical-CPO denominator.

## Durable findings

- The durable current REVE snapshot contains 148 distinct operator identities and all 148 now have a persisted nominative first-pass decision in `docs/spain-cpo-progress-2026-09.json`.
- The historical 618-label membership was not durably persisted as a complete nominal list in Git.
- Git history was searched structurally for Spain inventory/progress/bootstrap material and immutable decision commits were preserved/reused where available.
- Commit `533827dfa61b661b572aa382b7125b5c3779fa17` is explicitly titled `Refresh Spain REVE CPO inventory`, but its committed diff only adds a refresh timestamp comment to `.github/workflows/spain-reve-v9-main-bootstrap.yml`; it does **not** persist the refreshed inventory itself. Therefore this commit cannot be treated as the missing 618-label nominal source.
- Earlier immutable commits and the current durable REVE coverage/aliases remain valid evidence for identities actually present in the canonical chain; no missing historical label identity may be invented from the numeric gap 618-148.

## Anti-stagnation guard

The one structured historical reconstruction attempt is considered complete. Do not repeat the same broad Git/artifact searches on later runs. Resume historical recovery only when a genuinely new durable source appears (for example a newly discovered immutable blob/ref/commit containing nominal labels, a retained artifact that is actually accessible and not previously inspected, or another persisted dataset with explicit historical label identity).

Until then:

1. Preserve `legacyWorkLabelCount=618` and the documented uncertainty.
2. Treat 148 as the minimum durably proven nominative first-pass coverage, not as proof that the historical 618 queue is complete.
3. Continue REVE tariff/status collection under its hourly quota independently of the missing historical membership.
4. Never synthesize identities merely to close the numeric gap.
5. Keep all critical progress state in versioned Git, never only in GitHub Actions artifacts.

## Current checkpoint

- Durable first-pass minimum: 148/618.
- Current replacement inventory: 148/148 decision-covered.
- `FIRST PASS COMPLETE`: **not proven** for the historical 618-label queue.
