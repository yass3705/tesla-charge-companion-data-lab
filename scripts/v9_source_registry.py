#!/usr/bin/env python3
"""Build the provisional source-to-module migration registry."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from v9_scheduled_methods import proposed_destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    scheduled = json.loads((root / "migration/v9/scheduled-methods.json").read_text())["rows"]
    manual = json.loads((root / "migration/v9/production-linked-manual-workflows.json").read_text())["rows"]
    groups: dict[str, dict] = defaultdict(lambda: {"methods": [], "country_scope": set(), "secrets": set(), "data_paths": set(), "production_linked_paths": set()})
    for row in scheduled:
        module = row["proposed_destination_module"]
        group = groups[module]
        group["methods"].append({"workflow": row["workflow"], "kind": "scheduled", "migration_status": "method_review_pending"})
        group["country_scope"].update(row["scope"])
        group["secrets"].update(row["secret_names"])
        group["data_paths"].update(row["literal_data_paths"])
    for row in manual:
        module = proposed_destination(Path(row["workflow"]).name)
        group = groups[module]
        group["methods"].append({"workflow": row["workflow"], "kind": "manual_or_indirect_production_linked", "migration_status": "method_review_pending"})
        if row["country_hint"]:
            group["country_scope"].add(row["country_hint"])
        group["secrets"].update(row["secret_names"])
        group["production_linked_paths"].update(p["path"] for p in row["production_linked_paths"])
        group["data_paths"].update(p["path"] for p in row["production_linked_paths"])
    modules = []
    for name, group in sorted(groups.items()):
        modules.append({
            "candidate_module": name,
            "status": "provisional_method_destination",
            "country_scope_hints": sorted(group["country_scope"]),
            "methods": sorted(group["methods"], key=lambda row: row["workflow"]),
            "secret_names": sorted(group["secrets"]),
            "literal_data_paths": sorted(group["data_paths"]),
            "literal_production_linked_paths": sorted(group["production_linked_paths"]),
        })
    payload = {
        "schema_version": 1,
        "status": "provisional; not a G1 signoff",
        "coverage": "117 scheduled workflows plus 61 manual/indirect workflows with literal Production references; all others remain in legacy-inventory.json",
        "modules": modules,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(modules)} candidate modules, {sum(len(m['methods']) for m in modules)} methods")


if __name__ == "__main__":
    main()
