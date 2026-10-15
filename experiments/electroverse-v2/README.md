# Electroverse V2 research — offline only

This directory contains an isolated simulator and 24 public archived station records from Data Lab `2d4a0ebe` shard 000. It has no HTTP client or canonical collector import.

Run from the Data Lab root:

```sh
node --test experiments/electroverse-v2/test/model.test.mjs
node experiments/electroverse-v2/benchmark.mjs
```

The benchmark writes only `reports/electroverse-v2/{benchmark,regression}.json`. All simulated collector state uses fresh `/tmp/electroverse-v2-*` directories. The output guard rejects canonical cache paths. Do not use the prototype for live collection or V9 pricing/publication.
