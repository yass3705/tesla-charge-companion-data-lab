#!/usr/bin/env python3
"""Preserve exact provenance of legacy methods embedded in YAML workflows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from v9_scheduled_methods import proposed_destination


ARCHIVE_COMMIT = "0b1b9d75463121b6ff86f94764b32d3349ee3e3c"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    workflows = json.loads((root / "migration/v9/legacy-inventory.json").read_text())["workflows"]
    production_linked = {
        row["workflow"]
        for row in json.loads((root / "migration/v9/production-linked-manual-workflows.json").read_text())["rows"]
    }
    rows = []
    for item in workflows:
        if item["scripts"]:
            continue
        path = root / item["workflow"]
        priority = (
            "critical" if item["scheduled"] or item["workflow"] in production_linked
            else "data_candidate" if any(p.startswith("data/") for p in item["data_paths"])
            else "historical_reference"
        )
        rows.append({
            "workflow": item["workflow"],
            "archive_commit": ARCHIVE_COMMIT,
            "yaml_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "triggers": item["triggers"],
            "secret_names": item["secrets"],
            "literal_data_paths": item["data_paths"],
            "country_hint": item["country_hint"],
            "proposed_destination_module": proposed_destination(path.name),
            "review_priority": priority,
            "method_status": "inline_yaml_review_pending",
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "rows": rows}, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(rows)} inline-only workflows with immutable YAML hashes")


if __name__ == "__main__":
    main()
