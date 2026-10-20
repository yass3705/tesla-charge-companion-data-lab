#!/usr/bin/env python3
"""Prioritize manual legacy workflows with literal Production data references."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    workflows = json.loads((root / "migration/v9/legacy-inventory.json").read_text())["workflows"]
    consumers = json.loads((root / "migration/v9/production-consumers.json").read_text())["rows"]
    referenced = {row["data_lab_path"]: row["production_references"] for row in consumers if row["production_references"]}
    rows = []
    for w in workflows:
        if w["scheduled"]:
            continue
        paths = sorted(set(w["data_paths"]) & referenced.keys())
        if not paths:
            continue
        rows.append({
            "workflow": w["workflow"],
            "country_hint": w["country_hint"],
            "triggers": w["triggers"],
            "scripts": w["scripts"],
            "secret_names": w["secrets"],
            "missing_script_references": w["missing_script_references"],
            "production_linked_paths": [{"path": path, "references": referenced[path]} for path in paths],
            "migration_status": "priority_review_pending",
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "rows": rows}, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(rows)} manual workflows with a literal Production reference")


if __name__ == "__main__":
    main()
