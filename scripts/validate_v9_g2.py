#!/usr/bin/env python3
"""Report G2 readiness without treating a partial collector migration as PASS."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1_COMMIT = "15657f4a89c98e5e7c1d119c91c6cb55a891a913"
REQUIRED_METHOD_DISPOSITIONS = {
    "retain_scheduled_data_method",
    "retain_scheduled_partial_method",
    "retain_production_dependency",
}


def main() -> None:
    errors = []
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml"))
    expected = {"v9-check.yml", "v9-collect.yml"}
    if {path.name for path in workflows} != expected:
        errors.append("active workflow set differs from the two approved read-only workflows")
    for path in workflows:
        body = path.read_text(encoding="utf-8")
        forbidden = ("contents: write", "git push", "workflow_run:", "repository_dispatch:", "push:", "pull_request_target:")
        if any(token in body for token in forbidden) or "contents: read" not in body:
            errors.append(f"workflow write/trigger risk: {path.name}")
    if not (ROOT / "scripts/operator_manifest_runner.py").is_file():
        errors.append("migrated operator module missing")
    archived = subprocess.run(["git", "cat-file", "-t", G1_COMMIT], cwd=ROOT, capture_output=True, text=True, check=False)
    if archived.returncode != 0 or archived.stdout.strip() != "commit":
        errors.append("G1 workflow archive commit unavailable")
    sources = json.loads((ROOT / "v9_rebuild/sources.json").read_text())["sources"]
    original = {row["workflow"]: row for row in json.loads((ROOT / "migration/v9/legacy-inventory.json").read_text())["workflows"]}
    final = json.loads((ROOT / "migration/v9/method-dispositions.json").read_text())
    migrated = set()
    for spec in sources:
        method = ("scripts/operator_manifest_runner.py" if spec["module"] == "operator_manifest"
                  else "scripts/dotnl_netherlands_build.py" if spec["module"] == "nl_dotnl"
                  else spec["script"])
        source_code = ROOT / (spec["manifest"] if spec["module"] == "operator_manifest" else method)
        if not source_code.is_file():
            errors.append(f"source method/config missing: {spec['id']}")
        for workflow in spec.get("legacy_workflows", []):
            if workflow not in original or workflow in migrated:
                errors.append(f"invalid or duplicate legacy workflow mapping: {workflow}")
            elif method not in original[workflow]["scripts"]:
                errors.append(f"legacy workflow uses a different extraction method: {workflow}")
            else:
                migrated.add(workflow)
    required = {row["workflow"] for row in final["workflow_rows"] if row["disposition"] in REQUIRED_METHOD_DISPOSITIONS}
    pending = sorted(required - migrated)
    if pending:
        errors.append(f"useful historical methods not yet migrated: {len(pending)}")
    if json.loads((ROOT / "v9_rebuild/sources.json").read_text()).get("status") != "complete_g2_migration":
        errors.append("execution registry remains explicitly partial")
    result = {
        "gate": "G2",
        "status": "pass" if not errors else "fail",
        "legacy_active_workflows_removed": len(expected) == len(workflows),
        "new_workflows": [path.name for path in workflows],
        "migrated_legacy_workflows": len(migrated),
        "registered_source_instances": len(sources),
        "pending_useful_methods": len(pending),
        "pending_sample": pending[:12],
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
