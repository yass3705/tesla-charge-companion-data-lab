#!/usr/bin/env python3
"""Resolve the next unvalidated operator in config/operator_batch.json."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/operator_batch.json")
    ap.add_argument("--github-output", default=None)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    enabled = bool(cfg.get("enabled", False))
    queue = list(cfg.get("queue") or [])
    next_key = ""
    completed: list[str] = []

    if enabled:
        for item in queue:
            marker = Path(item["marker"])
            if marker.exists():
                completed.append(item["key"])
                continue
            next_key = item["key"]
            break

    result = {
        "batchId": cfg.get("batchId"),
        "enabled": enabled,
        "completed": completed,
        "next": next_key or None,
        "done": enabled and not next_key and len(completed) == len(queue),
    }
    print(json.dumps(result, ensure_ascii=False))

    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as f:
            f.write(f"enabled={'1' if enabled else '0'}\n")
            f.write(f"next={next_key}\n")
            f.write(f"done={'1' if result['done'] else '0'}\n")
            f.write(f"completed_count={len(completed)}\n")
            f.write(f"queue_count={len(queue)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
