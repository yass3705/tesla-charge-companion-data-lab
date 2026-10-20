#!/usr/bin/env python3
"""Classify historical inline methods with data outputs for migration review."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


VALIDATION = re.compile(r"audit|validator|diagnostic|summary|oracle|classification|reconciliation|residuals-export|smoke", re.I)
EXPERIMENT = re.compile(r"probe|discovery|capture|browser|sample|key-validation|targeted-apif|deeplink|route|static-audit|map-api-context|targeted-assets", re.I)
STEP_NAME = re.compile(r"^\s+- name:\s*(.+)$", re.M)
EXPLICIT_ROLES = {
    "road-france-browser-national-exact.yml": ("collector_or_compiler", "retain_method_for_module"),
    "uk-shell-tariff-probe.yml": ("collector_or_compiler", "retain_method_for_module"),
    "after-minutes-staging-validation-20261011.yml": ("historical_validation", "retain_as_validation_reference"),
    "tcc-v9-after-minutes-production-verification.yml": ("historical_validation", "retain_as_validation_reference"),
    "chargepoint-oracle-setaside.yml": ("collector_or_compiler", "retain_method_for_module"),
    "chargepoint-oracle-top-unresolved.yml": ("collector_or_compiler", "retain_method_for_module"),
    "etotem-france-exact-api-inventory.yml": ("technical_experiment", "archive_experimental_method"),
    "extract-alize-bouygues-stratified.yml": ("technical_experiment", "archive_experimental_method"),
    "france-cpo-coverage-ranking.yml": ("historical_validation", "retain_as_validation_reference"),
    "france-cpo-queue-snapshot.yml": ("historical_validation", "retain_as_validation_reference"),
    "france-cpo-state-refresh.yml": ("historical_validation", "retain_as_validation_reference"),
    "france-v9-electra-schema-diag.yml": ("historical_validation", "retain_as_validation_reference"),
    "ionity-france-pan-inventory.yml": ("historical_validation", "retain_as_validation_reference"),
    "qwello-france-afir-api-resolve.yml": ("technical_experiment", "archive_experimental_method"),
    "switzerland-national-cpo-counts.yml": ("historical_validation", "retain_as_validation_reference"),
    "izivia-express-normalized-v1.yml": ("collector_or_compiler", "retain_method_for_module"),
    "izivia-express-compatibility-v2.yml": ("collector_or_compiler", "retain_method_for_module"),
}


def classify(name: str) -> tuple[str, str]:
    if name in EXPLICIT_ROLES:
        return EXPLICIT_ROLES[name]
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
        step_names = STEP_NAME.findall((args.root / row["workflow"]).read_text(encoding="utf-8", errors="replace"))
        if not step_names and Path(row["workflow"]).name == "ionity-france-pan-inventory.yml":
            step_names = ["unnamed inline collection and inventory"]
        if not step_names:
            raise ValueError(f"Inline method lacks named steps for review: {row['workflow']}")
        rows.append({
            "workflow": row["workflow"],
            "yaml_sha256": row["yaml_sha256"],
            "role": role,
            "disposition": disposition,
            "candidate_module": row["proposed_destination_module"],
            "literal_data_paths": row["literal_data_paths"],
            "step_names": step_names,
            "classification_basis": "reviewed workflow name, named YAML steps, and archived YAML data paths; technical role only",
            "classification_status": "classified_method_role",
        })
    if len(rows) != 147:
        raise ValueError(f"Data candidate baseline changed: {len(rows)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 1, "rows": rows}, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(rows)} inline data method roles classified")


if __name__ == "__main__":
    main()
