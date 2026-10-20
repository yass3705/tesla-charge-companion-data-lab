#!/usr/bin/env python3
"""Fail closed when a historical method lacks its code or module destination."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCOPE = {"FR", "IT", "CH", "DE", "ES", "NL", "UK", "MA", "BE", "TESLA"}


def main() -> None:
    inv = json.loads((ROOT / "migration/v9/legacy-inventory.json").read_text())
    destinations = json.loads((ROOT / "migration/v9/script-destinations.json").read_text())["rows"]
    registry = json.loads((ROOT / "migration/v9/source-registry.json").read_text())["modules"]
    inline = json.loads((ROOT / "migration/v9/inline-methods.json").read_text())["rows"]
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
    missing_code = sorted({s for w in inv["workflows"] for s in w["missing_script_references"]})
    if missing_code:
        errors.append(f"historical workflow references missing code: {missing_code}")
    expected_inline = {w["workflow"] for w in inv["workflows"] if not w["scripts"]}
    registered_inline = {r["workflow"] for r in inline}
    if expected_inline != registered_inline:
        errors.append(f"inline method inventory mismatch: missing={sorted(expected_inline - registered_inline)}, extra={sorted(registered_inline - expected_inline)}")
    changed_inline = [r["workflow"] for r in inline if hashlib.sha256((ROOT / r["workflow"]).read_bytes()).hexdigest() != r["yaml_sha256"]]
    if changed_inline:
        errors.append(f"inline method YAML hash mismatch: {changed_inline}")
    pending_inline = sum(r["method_status"] == "inline_yaml_review_pending" for r in inline)
    if pending_inline:
        errors.append(f"inline methods not yet classified: {pending_inline}")
    scope = {country for module in registry for country in module["country_scope_hints"]}
    if REQUIRED_SCOPE - scope:
        errors.append(f"country/source scope absent: {sorted(REQUIRED_SCOPE - scope)}")
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
