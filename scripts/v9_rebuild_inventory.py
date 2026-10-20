#!/usr/bin/env python3
"""Static inventory of legacy workflow references; never executes collectors."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


COUNTRY_PREFIXES = {
    "france": "FR", "fr": "FR", "italy": "IT", "italia": "IT", "it": "IT",
    "switzerland": "CH", "swiss": "CH", "ch": "CH", "germany": "DE", "de": "DE",
    "spain": "ES", "es": "ES", "netherlands": "NL", "nl": "NL", "dotnl": "NL",
    "uk": "UK", "gb": "UK", "britain": "UK", "morocco": "MA", "ma": "MA",
    "belgium": "BE", "be": "BE", "tesla": "TESLA", "suc": "TESLA",
}
SCRIPT_RE = re.compile(r"(?<![\w./-])(?:scripts|src)/[\w./-]+\.(?:py|js|mjs|sh|ts)")
SECRET_RE = re.compile(r"secrets\.([A-Z][A-Z0-9_]+)")
PATH_RE = re.compile(r"(?<![\w./-])(?:data|reports|config)/[\w./-]+\.(?:json|jsonl|csv|gz|parquet|yaml|yml)")
WRITE_RE = re.compile(r"\bgit push\b|\bgh api\b|\bcontents:\s*write\b", re.I)
TRIGGER_RE = re.compile(r"^\s{2}(push|pull_request|workflow_run|repository_dispatch|schedule|workflow_dispatch|workflow_call):", re.M)


def country_for(name: str, scripts: list[str], paths: list[str]) -> str | None:
    tokens = re.split(r"[^a-z0-9]+", " ".join([name, *scripts, *paths]).lower())
    matches = {COUNTRY_PREFIXES[t] for t in tokens if t in COUNTRY_PREFIXES}
    return next(iter(matches)) if len(matches) == 1 else None


def inventory(root: Path) -> dict:
    workflows = []
    for path in sorted((root / ".github/workflows").glob("*.y*ml")):
        body = path.read_text(encoding="utf-8", errors="replace")
        scripts = sorted(set(SCRIPT_RE.findall(body)))
        paths = sorted(set(PATH_RE.findall(body)))
        triggers = sorted(set(TRIGGER_RE.findall(body)))
        workflows.append({
            "workflow": str(path.relative_to(root)),
            "country_hint": country_for(path.stem, scripts, paths),
            "scripts": scripts,
            "secrets": sorted(set(SECRET_RE.findall(body))),
            "data_paths": paths,
            "triggers": triggers,
            "scheduled": "schedule" in triggers,
            "indirect_trigger": "workflow_run" in triggers,
            "contains_write_command_or_permission": bool(WRITE_RE.search(body)),
            "missing_script_references": [s for s in scripts if not (root / s).is_file()],
            "migration_status": "unreviewed",
            "destination_module": None,
        })
    all_scripts = sorted(str(p.relative_to(root)) for p in (root / "scripts").rglob("*") if p.is_file())
    referenced = {s for workflow in workflows for s in workflow["scripts"]}
    return {
        "schema_version": 1,
        "purpose": "static migration inventory, not evidence that a method is valid or a collector is active",
        "workflows": workflows,
        "scripts": [{"path": s, "referenced_by_workflow": s in referenced} for s in all_scripts],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(result['workflows'])} workflows, {len(result['scripts'])} scripts")


if __name__ == "__main__":
    main()
