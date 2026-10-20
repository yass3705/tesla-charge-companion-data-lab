#!/usr/bin/env python3
"""Classify historical inline methods with data outputs for migration review."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


VALIDATION = re.compile(r"audit|validator|diagnostic|summary|oracle|classification|reconciliation|residuals-export|smoke", re.I)
EXPERIMENT = re.compile(r"probe|discovery|capture|browser|sample|key-validation|targeted-apif|deeplink|route|static-audit|map-api-context|targeted-assets", re.I)


def classify(name: str) -> tuple[str, str]:
    if VALIDATION.search(name):
        return "historical_validation", "retain_as_validation_reference"
    if EXPERIMENT.search(name):
        return "technical_experiment", "archive_experimental_method"
    return "collector_or_compiler", "retain_method_for_module"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads((args.root / "migration/v9/inline-methods.json").read_text())["rows"]
    rows = []
    for row in source:
        if row["review_priority"] != "data_candidate":
            continue
        role, disposition = classify(Path(row["workflow"]).name)
        rows.append({
            "workflow": row["workflow"],
            "yaml_sha256": row["yaml_sha256"],
            "role": role,
            "disposition": disposition,
            "candidate_module": row["proposed_destination_module"],
            "literal_data_paths": row["literal_data_paths"],
            "classification_basis": "workflow name and archived YAML paths; technical role only",
            "classification_status": "provisional_pending_yaml_method_review",
        })
    if len(rows) != 106:
        raise ValueError(f"Data candidate baseline changed: {len(rows)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "rows": rows}, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(rows)} data candidates provisionally triaged")


if __name__ == "__main__":
    main()
