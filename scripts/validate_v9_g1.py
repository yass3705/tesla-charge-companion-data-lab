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
    exceptions = json.loads((ROOT / "migration/v9/legacy-method-exceptions.json").read_text())
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
    # Inline YAMLs have their own complete, hash-checked disposition registry.
    # Only script-backed workflows still need a final destination here.
    unavailable_workflows = {entry["workflow"] for entry in exceptions["exceptions"]}
    pending_workflows = [w["workflow"] for w in inv["workflows"] if w["scripts"] and w["workflow"] not in unavailable_workflows and (w["migration_status"] == "unreviewed" or not w["destination_module"])]
    if pending_workflows:
        errors.append(f"script-backed workflows without final disposition/destination: {len(pending_workflows)}")
    pending_scripts = [r["script"] for r in destinations if r["review_status"] in {"candidate_destination_pending_review", "ambiguous_shared_method"}]
    if pending_scripts:
        errors.append(f"historical scripts without final review: {len(pending_scripts)}")
    pending_priority = [m for module in registry for m in module["methods"] if m["migration_status"] == "method_review_pending" and m.get("workflow") not in unavailable_workflows]
    if pending_priority:
        errors.append(f"priority methods without final review: {len(pending_priority)}")
    if any(module["status"] == "provisional_method_destination" for module in registry):
        errors.append("source registry still provisional")
    result = {
        "gate": "G1",
        "status": "pass" if not errors else "fail",
        "historical_workflows_registered": len(registered_workflows),
        "historical_scripts_with_candidate_destination": len(mapped_scripts),
        "inline_methods_registered": len(registered_inline),
        "scope": sorted(scope),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
