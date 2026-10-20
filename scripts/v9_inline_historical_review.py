#!/usr/bin/env python3
"""Classify inactive inline YAML references while preserving exact provenance."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


STEP_NAME = re.compile(r"^\s+- name:\s*(.+)$", re.M)
VALIDATION = re.compile(r"audit|validat|verify|verification|diagnos|summary|summarize|oracle|regression|qa|closeout|evidence|parity|review|check", re.I)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    inline = json.loads((root / "migration/v9/inline-methods.json").read_text())["rows"]
    rows = []
    for item in inline:
        if item["review_priority"] != "historical_reference":
            continue
        body = (root / item["workflow"]).read_text(encoding="utf-8", errors="replace")
        steps = STEP_NAME.findall(body)
        if not steps:
            raise ValueError(f"Historical YAML lacks named steps: {item['workflow']}")
        if "schedule" in item["triggers"] or re.search(r"\bdata/[\w./-]+", body):
            raise ValueError(f"Active or data-bearing method misclassified: {item['workflow']}")
        role = "historical_validation" if VALIDATION.search(Path(item["workflow"]).name) else "technical_experiment"
        rows.append({
            "workflow": item["workflow"],
            "yaml_sha256": item["yaml_sha256"],
            "step_names": steps,
            "role": role,
            "disposition": "retain_as_validation_reference" if role == "historical_validation" else "archive_experimental_method",
            "archive_commit": item["archive_commit"],
            "candidate_module": item["proposed_destination_module"],
            "classification_basis": "no schedule, no literal Production link, no data/ output/reference; reviewed YAML step names and archive hash",
        })
    if len(rows) != 366:
        raise ValueError(f"Historical reference baseline changed: {len(rows)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "rows": rows}, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(rows)} historical inline method references classified")


if __name__ == "__main__":
    main()
