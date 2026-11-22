# V2 R&D iteration — checkpoint policy, offline only (2026-10-15)

## Scope and proof
Research-only, no network/API, no production or canonical collection changes. Additional policy model in `experiments/electroverse-v2/checkpoint_policy.mjs` and six unit tests. **Not wired into `runV2`**, and not a validated alternative collector. The existing V2 benchmark remains untouched; its published timings must not be treated as updated.

The existing prototype writes the full last-good state and checkpoint on each 5-station batch; on 24 stations this is 5 batches and 10 logical writes. The isolated policy model schedules checkpoints every 4 batches (and at the end). For 5 batches: points [4,5], **4 modeled logical writes instead of 10**. This is a calculation from the schedule, not a measured I/O speedup.

## Important trade-off
A crash after batch 2, before batch 4, has **no checkpoint** under the policy; the two processed batches would need replay. The original V2 demo avoided this replay. Therefore batching checkpoints cannot simultaneously guarantee the same fine-grained restart property without introducing a lightweight durable write-ahead log / atomic generation mechanism. Do not suggest that fewer writes necessarily means fewer network requests in a crash scenario.

The current V2 uses two separate atomic file renames (`last-good.json` and `checkpoint.json`) rather than a single atomic generation. A robust experiment should compare:
- small append-only WAL with verified hash and atomic committed offset;
- copy-on-write generation + single atomic pointer commit;
- batched checkpoints with explicit bounded replay.

These are architecture ideas only, **not implemented or benchmarked**.

## Larger archive and scheduling comparison
The historical national manifest records 22,818 cached stations, 128 shards, estimated 346 MB; this is not a benchmark fixture. To benchmark legitimately, stream a deterministic bounded sample of existing *publicly archived* shards, use immutable hashes, and avoid loading the entire archive into memory. Compare V1 behavior model, V2 actual prototype and any new candidate on identical samples, including skewed huge stations/pagination. Sample size and extraction proof must appear in outputs. No national parity claims are justified yet.

For scheduling, compare only deterministic simulated fault and latency distributions based on recorded operational evidence; do not assume increased concurrency reduces 429s or elapsed time. Report best-case, worst-case and cost of repeat work.

## Verification
The isolated 6-test policy suite was executed using Node.js in a separate local runtime and passed (6/6). This does **not** validate `runV2`, integration, national scale, or live API performance. The full suite of 16 V2 tests was not rerun in this iteration.

**Conclusion:** viable policy to investigate, but no demonstrated overall improvement; V1 remains unchanged. Do not merge experimental PR as a replacement.
