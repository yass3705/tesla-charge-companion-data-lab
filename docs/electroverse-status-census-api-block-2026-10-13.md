# Electroverse France EVSE status census: repeated API stop (13 October 2026)

The V9 France overlay requires a complete EVSE status census before rebuilding. The incremental collector uses at most two locations per GraphQL batch, retries individual aliases and checkpoints partial partitions. It stops at 49 persistent errors rather than treating unknown status as active.

| Run | Partition | Verified / expected | Requests | Persistent errors | Remaining in partition |
| --- | ---: | ---: | ---: | ---: | ---: |
| [38218495333](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38218495333) | 12 | 985 / 1,426 | 768 | 49 | 441 |
| [38323475271](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38323475271) | 1 | 319 / 1,427 | 328 | 49 | 1,108 |

The second run saved a checkpoint as `ebd398d42`. The finalization report then counted 1,550 verified of 22,818 source locations, with 21,268 unverified and no national manifest. Six partition checkpoint files exist, all incomplete. The source cache fingerprint was `f84052a8ac6eade4e00ab45ad6238452850b8ccb41992fc04f96d980b8317549` in both runs. A successful GitHub Actions job means the checkpoint was saved, **not** that the census or tariff overlay is valid.

Before another large collection, ask the Electroverse API team whether `chargingLocation(pk)` GraphQL status queries have a documented per-client request or complexity limit, whether a supported paginated status export exists, and which response fields or correlation IDs should be supplied to diagnose the persistent errors. The current collector already reduces failed batches to individual requests. Do not raise the error budget, mark unknown EVSEs available or merge the connector-filter overlay [#219](https://github.com/yass3705/tesla-charge-companion-data-lab/pull/219) on partial status data. No V9 pin or Pages deployment changed.
