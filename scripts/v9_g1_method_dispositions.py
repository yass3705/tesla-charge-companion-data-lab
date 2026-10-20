#!/usr/bin/env python3
"""Group preserved legacy methods by evidence and decide migration disposition.

The result is an inventory decision. It never claims a collector executes or
that a source price is valid; G2 is responsible for runtime compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    from scripts.v9_scheduled_methods import proposed_destination
except ModuleNotFoundError:  # direct execution from scripts/
    from v9_scheduled_methods import proposed_destination

RETAIN_ARTIFACT_STAGES = {
    ".github/workflows/electroverse-uk-national-details.yml",
    ".github/workflows/emsp-national-staging.yml",
    ".github/workflows/electra-nl-emsp-national-stage.yml",
}
RETAIN_SHARED_VALIDATIONS = {
    ".github/workflows/france-irve-public-access-audit.yml",
    ".github/workflows/watch-fixed-tariff-sources.yml",
}


def material(path: str) -> bool:
    return path.startswith("data/") and not path.startswith(("data/reports/", "data/station_verifications/", "data/manual_verification/"))


def classify_workflow(row: dict, inline: dict, unavailable: set[str]) -> tuple[str, list[str]]:
    workflow = row["workflow"]
    if workflow in unavailable:
        return "legacy_method_unavailable", ["named_missing_code_exception"]
    if workflow in inline:
        disposition = inline[workflow]["disposition"]
        return disposition, ["reviewed_inline_yaml_with_sha256"]
    output_paths = row["git_add_literal_paths"]
    if row["literal_production_references"]:
        return "retain_production_dependency", ["literal_production_reference"]
    if workflow in RETAIN_ARTIFACT_STAGES:
        return "retain_dormant_partial_method", ["reviewed_artifact_stage_in_workflow_source"]
    if workflow in RETAIN_SHARED_VALIDATIONS:
        return "retain_validation_reference", ["reviewed_shared_validation_in_workflow_source"]
    if row["scheduled"] and any(map(material, output_paths)):
        return "retain_scheduled_data_method", ["schedule", "material_path_in_git_add"]
    if row["scheduled"] and any(map(material, row["literal_paths_untyped"])):
        return "retain_scheduled_partial_method", ["schedule", "material_path_role_unresolved"]
    if row["scheduled"] and any(map(material, row.get("code_literal_paths_untyped", []))):
        return "retain_scheduled_partial_method", ["schedule", "material_path_in_source_code_role_unresolved"]
    if any(map(material, output_paths)):
        return "retain_dormant_data_method", ["material_path_in_git_add"]
    if output_paths and all(path.startswith(("reports/", "data/reports/", "docs/")) for path in output_paths):
        return "archive_validation_reference", ["only_report_paths_in_git_add", "no_schedule_or_production_reference"]
    if any(map(material, row["literal_paths_untyped"])):
        return "retain_dormant_partial_method", ["material_path_role_unresolved"]
    if row["literal_paths_untyped"] and all(path.startswith(("reports/", "data/reports/", "docs/")) for path in row["literal_paths_untyped"]):
        return "archive_validation_reference", ["only_report_paths_in_workflow", "no_schedule_or_production_reference"]
    if not row["literal_paths_untyped"] and not row.get("upload_artifact_literal_paths"):
        return "archive_historical_reference", ["no_persisted_output_in_workflow", "no_schedule_or_production_reference"]
    if any(map(material, row.get("code_literal_paths_untyped", []))):
        return "retain_dormant_partial_method", ["material_path_in_source_code_role_unresolved"]
    if row["scheduled"]:
        return "retain_validation_reference", ["schedule_without_material_output"]
    return "archive_historical_reference", ["no_schedule_production_reference_or_material_path"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    evidence = json.loads((root / "migration/v9/script-workflow-evidence.json").read_text())["rows"]
    inline_rows = json.loads((root / "migration/v9/inline-methods.json").read_text())["rows"]
    destinations = json.loads((root / "migration/v9/script-destinations.json").read_text())["rows"]
    priorities = json.loads((root / "migration/v9/source-registry.json").read_text())["modules"]
    exceptions = json.loads((root / "migration/v9/legacy-method-exceptions.json").read_text())["exceptions"]
    inv = json.loads((root / "migration/v9/legacy-inventory.json").read_text())
    by_workflow = {row["workflow"]: row for row in evidence}
    by_inline = {row["workflow"]: row for row in inline_rows}
    unavailable = {row["workflow"] for row in exceptions}
    script_module = {row["script"]: row["candidate_modules"][0] for row in destinations}
    priority_module = {method["workflow"]: group["candidate_module"] for group in priorities for method in group["methods"] if "workflow" in method}
    rows = []
    for item in inv["workflows"]:
        workflow = item["workflow"]
        source = by_workflow.get(workflow) or {
            "workflow": workflow,
            "workflow_sha256": by_inline[workflow]["yaml_sha256"],
            "git_add_literal_paths": [],
            "literal_paths_untyped": by_inline[workflow]["literal_data_paths"],
            "code_literal_paths_untyped": [],
            "literal_production_references": {},
            "upload_artifact_literal_paths": [],
            "scheduled": item["scheduled"],
            "secret_names": item["secrets"],
            "scripts": [],
        }
        disposition, basis = classify_workflow(source, by_inline, unavailable)
        modules = {script_module[script] for script in item["scripts"] if script in script_module and not script_module[script].startswith("shared/")}
        module = priority_module.get(workflow) or (next(iter(modules)) if len(modules) == 1 else proposed_destination(Path(workflow).name))
        if disposition in {"archive_historical_reference", "archive_validation_reference", "archive_experimental_method", "retire_legacy_wrapper"}:
            module = "archive/legacy_workflows"
        rows.append({
            "workflow": workflow,
            "workflow_sha256": source["workflow_sha256"],
            "module_destination": module,
            "disposition": disposition,
            "decision_basis": basis,
            "source_scripts": item["scripts"],
            "secret_names": item["secrets"],
            "literal_paths_untyped": item["data_paths"],
            "code_literal_paths_untyped": source["code_literal_paths_untyped"],
            "published_paths_in_git_add": source["git_add_literal_paths"],
            "upload_artifact_literal_paths": source["upload_artifact_literal_paths"],
            "literal_production_references": source["literal_production_references"],
            "active_in_rebuild": False,
        })
    refs: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        for script in row["source_scripts"]:
            refs[script].append(row)
    scripts = []
    for row in destinations:
        path = row["script"]
        uses = refs.get(path, [])
        retained = any(use["disposition"].startswith("retain_") for use in uses)
        disposition = "retain_module_code" if retained or not uses else "archive_historical_code"
        scripts.append({
            "script": path,
            "sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
            "module_destination": row["candidate_modules"][0],
            "disposition": disposition,
            "workflow_references": sorted(use["workflow"] for use in uses),
        })
    modules: dict[str, dict] = defaultdict(lambda: {"dispositions": Counter(), "workflows": [], "scripts": []})
    for row in rows:
        group = modules[row["module_destination"]]
        group["dispositions"][row["disposition"]] += 1
        group["workflows"].append(row["workflow"])
    for row in scripts:
        modules[row["module_destination"]]["scripts"].append(row["script"])
    payload = {
        "schema_version": 1,
        "scope": "G1 method dispositions only; no collector declared runnable or price revalidated",
        "workflow_rows": rows,
        "script_rows": scripts,
        "modules": [{"module": name, "dispositions": dict(group["dispositions"]), "workflow_count": len(group["workflows"]), "script_count": len(group["scripts"])} for name, group in sorted(modules.items())],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"workflows": len(rows), "scripts": len(scripts), "modules": len(modules), "workflow_dispositions": dict(Counter(row["disposition"] for row in rows)), "script_dispositions": dict(Counter(row["disposition"] for row in scripts))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
