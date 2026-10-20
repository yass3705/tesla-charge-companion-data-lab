#!/usr/bin/env python3
"""Find literal Data Lab file references in a pinned Production checkout."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


CODE_ROOTS = ("scripts", "config", "runtime-overrides", "v9-production-shell", ".github/workflows")
SUFFIXES = {".py", ".js", ".mjs", ".json", ".yml", ".yaml", ".sh", ".html"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datalab", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lab = args.datalab
    prod = args.production
    inventory = json.loads((lab / "migration/v9/legacy-inventory.json").read_text())
    paths = sorted({p for w in inventory["workflows"] for p in w["data_paths"]})
    refs: dict[str, list[str]] = defaultdict(list)
    checked = 0
    for code_root in CODE_ROOTS:
        base = prod / code_root
        if not base.is_dir():
            continue
        for file in base.rglob("*"):
            if not file.is_file() or file.suffix not in SUFFIXES:
                continue
            try:
                content = file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            checked += 1
            for path in paths:
                if path in content:
                    refs[path].append(str(file.relative_to(prod)))
    result = {
        "schema_version": 1,
        "scope": "literal path references in Production code/config only; absence does not prove a source is unused",
        "production_files_checked": checked,
        "rows": [{"data_lab_path": path, "production_references": refs.get(path, [])} for path in paths],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{checked} Production files; {len(paths)} Data Lab paths; {sum(bool(refs.get(p)) for p in paths)} referenced literally")


if __name__ == "__main__":
    main()
