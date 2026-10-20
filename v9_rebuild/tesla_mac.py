#!/usr/bin/env python3
"""Import the existing immutable Tesla/Mac ingress into an isolated V9 artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.electroverse import ROOT

CATALOGUE = Path("data/tesla/mac/catalogue.json")
MANIFEST = Path("data/tesla/mac/last-good.json")
OWNER = "yass3705/tesla-charge-companion-production"
INGRESS_PATH = "data/tesla/mac/staging/catalogue.json"


def validate_output(out: Path) -> dict:
    raw = (out / CATALOGUE).read_bytes()
    manifest = json.loads((out / MANIFEST).read_text(encoding="utf-8"))
    rows = json.loads(raw)
    ids = [row.get("id") for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    if (not isinstance(rows, list) or manifest.get("schemaVersion") != 1
            or manifest.get("status") != "last-good"
            or manifest.get("cataloguePath") != str(CATALOGUE)
            or manifest.get("sourceRepository") != OWNER
            or manifest.get("sourcePath") != INGRESS_PATH
            or manifest.get("catalogueSha256") != hashlib.sha256(raw).hexdigest()
            or manifest.get("catalogueBytes") != len(raw)
            or manifest.get("stationCount") != len(rows)
            or len(ids) != len(rows) or len(ids) != len(set(ids)) or any(not item for item in ids)
            or any(not row.get("countryCode") or not isinstance(row.get("pricing"), dict)
                   or not row.get("chargingConfigurations") for row in rows)):
        raise ValueError("Tesla/Mac isolated catalogue or immutable pin invalid")
    return manifest


def run(out: Path, *, source: Path = ROOT, ready_file: Path | None = None,
        catalogue_file: Path | None = None, runner=subprocess.run) -> None:
    out = out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise ValueError("Tesla/Mac output must be outside checkout")
    validate_output(source)
    for relative in (CATALOGUE, MANIFEST):
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, destination)
    command = [sys.executable, str(ROOT / "scripts/import_tesla_mac_ingress.py"), "--root", str(out)]
    if ready_file is not None:
        command.extend(["--ready-file", str(ready_file)])
    if catalogue_file is not None:
        command.extend(["--catalogue-file", str(catalogue_file)])
    result = runner(command, cwd=out, capture_output=True, text=True, timeout=900, check=False)
    if result.returncode:
        raise RuntimeError("Historical Tesla/Mac ingress import failed")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()
    run(args.out, source=args.source)


if __name__ == "__main__":
    main()
