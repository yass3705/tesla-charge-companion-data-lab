#!/usr/bin/env python3
"""Create a review matrix for scheduled legacy methods without running them."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


COMMAND_RE = re.compile(r"^\s*(?:(?:-\s*)?run:\s*)?(?:python(?:3)?|node|bash|sh|npx)\s+[^#\n]+")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    inventory = json.loads((root / "migration/v9/legacy-inventory.json").read_text())
    reviewed = json.loads((root / "migration/v9/scheduled-scope-review.json").read_text())["workflows"]
    rows = []
    seen_overrides = set()
    for item in inventory["workflows"]:
        if not item["scheduled"]:
            continue
        name = Path(item["workflow"]).name
        override = reviewed.get(name)
        if item["country_hint"] is None:
            if override is None:
                raise ValueError(f"Scheduled workflow lacks scope review: {name}")
            seen_overrides.add(name)
        elif override is not None:
            raise ValueError(f"Unexpected override for unambiguous country: {name}")
        body = (root / item["workflow"]).read_text(encoding="utf-8", errors="replace")
        commands = sorted({line.strip() for line in body.splitlines() if COMMAND_RE.match(line)})
        rows.append({
            "workflow": item["workflow"],
            "scope": override["scope"] if override else [item["country_hint"]],
            "role": override["role"] if override else "requires_role_review",
            "commands": commands,
            "scripts": item["scripts"],
            "missing_script_references": item["missing_script_references"],
            "secret_names": item["secrets"],
            "literal_data_paths": item["data_paths"],
            "destination_module": None,
            "review_status": "pending_method_and_output_review",
        })
    if seen_overrides != set(reviewed):
        raise ValueError(f"Unused scope reviews: {sorted(set(reviewed) - seen_overrides)}")
    if len(rows) != 117:
        raise ValueError(f"Expected current baseline of 117 scheduled workflows, found {len(rows)}")
    payload = {"schema_version": 1, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} scheduled methods; {sum(bool(r['commands']) for r in rows)} with parsed commands")


if __name__ == "__main__":
    main()
