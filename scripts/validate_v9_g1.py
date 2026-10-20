#!/usr/bin/env python3
"""Fail closed on unclassified historical methods and unlisted missing code."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCOPE = {"FR", "IT", "CH", "DE", "ES", "NL", "UK", "MA", "BE", "TESLA"}
ALLOWED_UNAVAILABLE = {
    ".github/workflows/ubitricity-nl-payg-refresh.yml": {
        "scripts/audit_nl_ubitricity_payg_portal.py",
        "scripts/reconcile_nl_ubitricity_payg_overlay.py",
    },
}
FINAL_DISPOSITIONS = {
    "archive_experimental_method", "archive_historical_reference", "archive_validation_reference",
    "legacy_method_unavailable", "retain_as_validation_reference", "retain_dormant_data_method",
    "retain_dormant_partial_method", "retain_method_for_module", "retain_production_dependency",
    "retain_scheduled_data_method", "retain_scheduled_partial_method", "retain_validation_reference",
    "retire_legacy_wrapper",
}


def validate_missing_code(root: Path, inventory: dict, exceptions: dict) -> list[str]:
    """Allow only exact, archived, explicitly disabled historical exceptions."""
    errors: list[str] = []
    workflows = {row["workflow"]: row for row in inventory["workflows"]}
    missing = {row["workflow"]: set(row["missing_script_references"]) for row in inventory["workflows"] if row["missing_script_references"]}
    registered: set[str] = set()
    for entry in exceptions.get("exceptions", []):
        workflow = entry.get("workflow")
        if workflow in registered:
            errors.append(f"duplicate missing-method exception: {workflow}")
            continue
        registered.add(workflow)
        expected = set(entry.get("missing_scripts", []))
        if ALLOWED_UNAVAILABLE.get(workflow) != expected:
            errors.append(f"unapproved missing-method exception: {workflow}")
        if workflow not in workflows or not expected or missing.get(workflow) != expected:
            errors.append(f"missing-method exception does not match inventory: {workflow}")
            continue
        if entry.get("status") != "legacy_method_unavailable" or entry.get("disposition") != "acquisition_disabled_last_good_retained":
            errors.append(f"missing-method exception is not disabled: {workflow}")
        if not entry.get("reason") or not entry.get("module_destination") or not entry.get("reactivation_condition"):
            errors.append(f"missing-method exception lacks justification/destination: {workflow}")
        if hashlib.sha256((root / workflow).read_bytes()).hexdigest() != entry.get("workflow_sha256"):
            errors.append(f"missing-method workflow changed: {workflow}")
        candidate = entry.get("last_good_candidate")
        if not candidate or not (root / candidate).is_file() or hashlib.sha256((root / candidate).read_bytes()).hexdigest() != entry.get("last_good_candidate_sha256"):
            errors.append(f"missing-method last-good candidate changed: {workflow}")
        integrator = entry.get("preserved_integrator")
        if not integrator or not (root / integrator).is_file():
            errors.append(f"missing-method integrator absent: {workflow}")
        for script in expected:
            if (root / script).exists():
                errors.append(f"disabled exception references restored script: {script}")
    unlisted = sorted(set(missing) - registered)
    if unlisted:
        errors.append(f"historical workflow references unlisted missing code: {unlisted}")
    extra = sorted(registered - set(missing))
    if extra:
        errors.append(f"stale missing-method exceptions: {extra}")
    return errors


def main() -> None:
    inv = json.loads((ROOT / "migration/v9/legacy-inventory.json").read_text())
    destinations = json.loads((ROOT / "migration/v9/script-destinations.json").read_text())["rows"]
    registry = json.loads((ROOT / "migration/v9/source-registry.json").read_text())["modules"]
    inline = json.loads((ROOT / "migration/v9/inline-methods.json").read_text())["rows"]
    data_reviews = json.loads((ROOT / "migration/v9/inline-data-review.json").read_text())["rows"]
    historical_reviews = json.loads((ROOT / "migration/v9/inline-historical-review.json").read_text())["rows"]
    script_evidence = json.loads((ROOT / "migration/v9/script-workflow-evidence.json").read_text())["rows"]
    exceptions = json.loads((ROOT / "migration/v9/legacy-method-exceptions.json").read_text())
    final = json.loads((ROOT / "migration/v9/method-dispositions.json").read_text())
    errors = []
    expected_workflows = {str(p.relative_to(ROOT)) for p in (ROOT / ".github/workflows").glob("*.y*ml")}
    registered_workflows = {w["workflow"] for w in inv["workflows"]}
    if expected_workflows != registered_workflows:
        errors.append(f"workflow inventory mismatch: missing={sorted(expected_workflows - registered_workflows)}, extra={sorted(registered_workflows - expected_workflows)}")
    historic_scripts = {s["path"] for s in inv["scripts"]}
    mapped_scripts = {r["script"] for r in destinations}
    if historic_scripts != mapped_scripts:
        errors.append(f"script destination mismatch: missing={sorted(historic_scripts - mapped_scripts)}, extra={sorted(mapped_scripts - historic_scripts)}")
    bad_modules = [r["script"] for r in destinations if len(r["candidate_modules"]) != 1]
    if bad_modules:
        errors.append(f"scripts without one candidate module: {bad_modules}")
    errors.extend(validate_missing_code(ROOT, inv, exceptions))
    expected_script_workflows = {w["workflow"] for w in inv["workflows"] if w["scripts"]}
    evidenced_script_workflows = {row["workflow"] for row in script_evidence}
    if len(script_evidence) != len(evidenced_script_workflows) or evidenced_script_workflows != expected_script_workflows:
        errors.append("script-workflow evidence coverage mismatch")
    for row in script_evidence:
        if hashlib.sha256((ROOT / row["workflow"]).read_bytes()).hexdigest() != row["workflow_sha256"]:
            errors.append(f"script-workflow evidence YAML changed: {row['workflow']}")
        for script in row["scripts"]:
            path = ROOT / script["path"]
            if path.is_file() != script["present"] or (path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != script["sha256"]):
                errors.append(f"script-workflow evidence code changed: {script['path']}")
    expected_inline = {w["workflow"] for w in inv["workflows"] if not w["scripts"]}
    registered_inline = {r["workflow"] for r in inline}
    if expected_inline != registered_inline:
        errors.append(f"inline method inventory mismatch: missing={sorted(expected_inline - registered_inline)}, extra={sorted(registered_inline - expected_inline)}")
    changed_inline = [r["workflow"] for r in inline if hashlib.sha256((ROOT / r["workflow"]).read_bytes()).hexdigest() != r["yaml_sha256"]]
    if changed_inline:
        errors.append(f"inline method YAML hash mismatch: {changed_inline}")
    expected_data = {r["workflow"]: r for r in inline if r["review_priority"] == "data_candidate"}
    reviewed_data = {r["workflow"]: r for r in data_reviews}
    if expected_data.keys() != reviewed_data.keys():
        errors.append(f"data method review mismatch: missing={sorted(expected_data.keys() - reviewed_data.keys())}, extra={sorted(reviewed_data.keys() - expected_data.keys())}")
    mismatched_data = [path for path, row in expected_data.items() if path in reviewed_data and (row["yaml_sha256"], row["method_role"], row["disposition"]) != (reviewed_data[path]["yaml_sha256"], reviewed_data[path]["role"], reviewed_data[path]["disposition"])]
    if mismatched_data:
        errors.append(f"data method role/hash mismatch: {mismatched_data}")
    expected_historical = {r["workflow"]: r for r in inline if r["review_priority"] == "historical_reference"}
    reviewed_historical = {r["workflow"]: r for r in historical_reviews}
    if expected_historical.keys() != reviewed_historical.keys():
        errors.append(f"historical method review mismatch: missing={sorted(expected_historical.keys() - reviewed_historical.keys())}, extra={sorted(reviewed_historical.keys() - expected_historical.keys())}")
    mismatched_historical = [path for path, row in expected_historical.items() if path in reviewed_historical and (row["yaml_sha256"], row["method_role"], row["disposition"]) != (reviewed_historical[path]["yaml_sha256"], reviewed_historical[path]["role"], reviewed_historical[path]["disposition"])]
    if mismatched_historical:
        errors.append(f"historical method role/hash mismatch: {mismatched_historical}")
    pending_inline = sum(r["method_status"] == "inline_yaml_review_pending" for r in inline)
    if pending_inline:
        errors.append(f"inline methods not yet classified: {pending_inline}")
    scope = {country for module in registry for country in module["country_scope_hints"]}
    if REQUIRED_SCOPE - scope:
        errors.append(f"country/source scope absent: {sorted(REQUIRED_SCOPE - scope)}")
    final_workflows = {row["workflow"]: row for row in final["workflow_rows"]}
    final_scripts = {row["script"]: row for row in final["script_rows"]}
    evidence_by_workflow = {row["workflow"]: row for row in script_evidence}
    inline_by_workflow = {row["workflow"]: row for row in inline}
    if len(final_workflows) != len(final["workflow_rows"]) or set(final_workflows) != registered_workflows:
        errors.append("final workflow disposition coverage mismatch")
    if len(final_scripts) != len(final["script_rows"]) or set(final_scripts) != historic_scripts:
        errors.append("final script disposition coverage mismatch")
    priority_workflows = {method["workflow"] for module in registry for method in module["methods"] if "workflow" in method}
    priority_scripts = {method["script"] for module in registry for method in module["methods"] if "script" in method}
    if priority_workflows - set(final_workflows) or priority_scripts - set(final_scripts):
        errors.append("priority methods absent from final disposition registry")
    unavailable_workflows = {entry["workflow"] for entry in exceptions["exceptions"]}
    for item in inv["workflows"]:
        row = final_workflows.get(item["workflow"])
        if not row:
            continue
        path = ROOT / item["workflow"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["workflow_sha256"]:
            errors.append(f"final workflow hash mismatch: {item['workflow']}")
        if row["source_scripts"] != item["scripts"] or row["secret_names"] != item["secrets"] or row["literal_paths_untyped"] != item["data_paths"]:
            errors.append(f"final workflow method inputs mismatch: {item['workflow']}")
        if not row["module_destination"] or not row["disposition"] or not row["decision_basis"]:
            errors.append(f"final workflow disposition incomplete: {item['workflow']}")
        if row["disposition"] not in FINAL_DISPOSITIONS or row["active_in_rebuild"] is not False:
            errors.append(f"invalid or prematurely activated method: {item['workflow']}")
        if item["workflow"] in inline_by_workflow and row["disposition"] != inline_by_workflow[item["workflow"]]["disposition"]:
            errors.append(f"inline final disposition differs from reviewed source: {item['workflow']}")
        evidence = evidence_by_workflow.get(item["workflow"])
        if evidence and (row["published_paths_in_git_add"] != evidence["git_add_literal_paths"] or row["upload_artifact_literal_paths"] != evidence["upload_artifact_literal_paths"] or row["literal_production_references"] != evidence["literal_production_references"]):
            errors.append(f"final workflow output/dependency evidence mismatch: {item['workflow']}")
        if row["disposition"].startswith(("archive_", "retire_")) and row["module_destination"] != "archive/legacy_workflows":
            errors.append(f"archived workflow has active module destination: {item['workflow']}")
        if row["disposition"] == "legacy_method_unavailable" and item["workflow"] not in unavailable_workflows:
            errors.append(f"unapproved unavailable final method: {item['workflow']}")
        if row["literal_production_references"] and row["disposition"].startswith(("archive_", "retire_")):
            errors.append(f"production-linked method archived: {item['workflow']}")
    for item in inv["scripts"]:
        row = final_scripts.get(item["path"])
        if not row:
            continue
        if hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() != row["sha256"]:
            errors.append(f"final script hash mismatch: {item['path']}")
        if not row["module_destination"] or row["disposition"] not in {"retain_module_code", "archive_historical_code"}:
            errors.append(f"final script disposition incomplete: {item['path']}")
        retained_uses = [use for use in row["workflow_references"] if final_workflows.get(use, {}).get("disposition", "").startswith("retain_")]
        if retained_uses and row["disposition"] != "retain_module_code":
            errors.append(f"script used by retained method was archived: {item['path']}")
    result = {
        "gate": "G1",
        "status": "pass" if not errors else "fail",
        "historical_workflows_registered": len(registered_workflows),
        "historical_scripts_with_candidate_destination": len(mapped_scripts),
        "inline_methods_registered": len(registered_inline),
        "final_workflow_dispositions": len(final_workflows),
        "final_script_dispositions": len(final_scripts),
        "scope": sorted(scope),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
