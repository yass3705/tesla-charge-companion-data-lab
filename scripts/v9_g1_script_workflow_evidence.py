#!/usr/bin/env python3
"""Collect reproducible source evidence for script-backed legacy workflows.

This is an evidence index, not a verdict about active collection. Paths in a
workflow may be inputs rather than outputs; the distinction is left explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


PATH_RE = re.compile(r"(?:data|reports|config|docs|artifacts)/[A-Za-z0-9_./*${}\-]+")
OUTPUT_RE = re.compile(r"(?:--(?:out|output|report|manifest|snapshot|checkpoint|dest|destination)\b|\bgit\s+add\b|write_text\b|write_bytes\b|writeFile\b)")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workflow_evidence(root: Path, item: dict, production_refs: dict[str, list[str]]) -> dict:
    body = (root / item["workflow"]).read_text(encoding="utf-8", errors="replace")
    lines = body.splitlines()
    output_lines = [line.strip() for line in lines if OUTPUT_RE.search(line)]
    # YAML shell blocks often continue `git add` on subsequent lines. Preserve
    # the relevant neighbouring lines so a reviewer can distinguish inputs.
    git_add_lines: list[str] = []
    for index, line in enumerate(lines):
        if re.search(r"\bgit\s+add\b", line):
            git_add_lines.append(line.strip())
            cursor = index
            while lines[cursor].rstrip().endswith("\\") and cursor + 1 < len(lines):
                cursor += 1
                git_add_lines.append(lines[cursor].strip())
    git_add_paths = sorted({path for line in git_add_lines for path in PATH_RE.findall(line)})
    artifact_paths: set[str] = set()
    for index, line in enumerate(lines):
        if "actions/upload-artifact@" in line:
            for following in lines[index + 1 : min(index + 12, len(lines))]:
                if re.match(r"\s*path:\s*", following):
                    artifact_paths.update(PATH_RE.findall(following))
                    break
    linked = {path: production_refs[path] for path in item["data_paths"] if production_refs.get(path)}
    scripts = []
    code_literal_paths: set[str] = set()
    for name in item["scripts"]:
        path = root / name
        if path.is_file():
            code_literal_paths.update(PATH_RE.findall(path.read_text(encoding="utf-8", errors="replace")))
        scripts.append({"path": name, "present": path.is_file(), "sha256": sha(path) if path.is_file() else None, "bytes": path.stat().st_size if path.is_file() else None})
    return {
        "workflow": item["workflow"],
        "workflow_sha256": sha(root / item["workflow"]),
        "scheduled": item["scheduled"],
        "indirect_trigger": item["indirect_trigger"],
        "triggers": item["triggers"],
        "country_hint": item["country_hint"],
        "scripts": scripts,
        "secret_names": item["secrets"],
        "literal_paths_untyped": item["data_paths"],
        "code_literal_paths_untyped": sorted(code_literal_paths),
        "git_add_literal_paths": git_add_paths,
        "upload_artifact_literal_paths": sorted(artifact_paths),
        "git_add_lines": git_add_lines,
        "output_command_lines": output_lines,
        "literal_production_references": linked,
        "classification": "evidence_only_pending_review",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    inventory = json.loads((root / "migration/v9/legacy-inventory.json").read_text())
    consumers = json.loads((root / "migration/v9/production-consumers.json").read_text())
    production_refs = {row["data_lab_path"]: row["production_references"] for row in consumers["rows"]}
    rows = [workflow_evidence(root, item, production_refs) for item in inventory["workflows"] if item["scripts"]]
    payload = {
        "schema_version": 1,
        "purpose": "source and workflow evidence for method review; no active-collector verdict",
        "production_reference_scope": consumers["scope"],
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"script_backed_workflows": len(rows), "with_literal_git_add_paths": sum(bool(r["git_add_literal_paths"]) for r in rows), "with_literal_production_refs": sum(bool(r["literal_production_references"]) for r in rows)}))


if __name__ == "__main__":
    main()
