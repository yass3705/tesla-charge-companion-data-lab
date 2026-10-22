#!/usr/bin/env python3
"""Run the preserved Swiss bundle constructor from a signed offline input snapshot."""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from v9_rebuild.orchestrator import ROOT, safe_relative

SCRIPT = Path("scripts/build_swiss_tcc_v9_bundle.py")
GUARD = Path("scripts/guard_swiss_bundle_refresh.py")
NATIONAL = Path("data/national/switzerland_oicp_source.json.gz")
BUNDLE = Path("data/tcc_v9/switzerland.json")
REPORT = Path("docs/switzerland-v9-integration-2026-09-28.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allowed_inputs() -> set[str]:
    tree = ast.parse((ROOT / SCRIPT).read_text(encoding="utf-8"))
    paths = {str(NATIONAL), "docs/switzerland-cpo-progress-2026-09.json"}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {"sources", "classifications"} for t in node.targets):
            paths.update(path for _, path in ast.literal_eval(node.value))
    return paths


def verify_inputs(source: Path, *, built: bool = False) -> list[str]:
    manifest = json.loads((source / "input-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1 or manifest.get("source") != "CH:swiss_bundle_inputs" or manifest.get("branch") != "rebuild/v9-20261020":
        raise ValueError("Swiss input manifest identity or branch invalid")
    files = manifest.get("files")
    allowed = allowed_inputs()
    if not isinstance(files, dict) or str(NATIONAL) not in files or not set(files) <= allowed:
        raise ValueError("Swiss input manifest paths invalid")
    if manifest.get("fixtureMode") is not True and set(files) != allowed:
        raise ValueError("Swiss production inputs incomplete")
    for name, digest in files.items():
        path = source / (Path("input_snapshot") / NATIONAL if built and name == str(NATIONAL) else safe_relative(name))
        if not path.is_file() or len(digest) != 64 or sha(path) != digest:
            raise ValueError(f"Swiss input SHA mismatch: {name}")
        if path.suffix == ".json" and path.stat().st_size:
            json.loads(path.read_text(encoding="utf-8"))
    raw = gzip.decompress((source / NATIONAL).read_bytes())
    if not isinstance(json.loads(raw), (dict, list)):
        raise ValueError("Swiss national source schema invalid")
    return sorted(files)


def prepare_archived_inputs(out: Path, root: Path = ROOT) -> None:
    """Sign the preserved Git snapshot without contacting the national provider."""
    out, root = out.resolve(), root.resolve()
    if out == root or root in out.parents:
        raise ValueError("Swiss input snapshot must be outside checkout")
    files = {}
    for name in sorted(allowed_inputs()):
        source = root / name
        if not source.is_file():
            raise ValueError(f"Swiss archived input missing: {name}")
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files[name] = sha(target)
    (out / "input-manifest.json").write_text(json.dumps({
        "schemaVersion": 1, "source": "CH:swiss_bundle_inputs",
        "branch": "rebuild/v9-20261020", "origin": "archived_git_snapshot",
        "files": files,
    }, sort_keys=True) + "\n", encoding="utf-8")
    verify_inputs(out)


def validate_output(out: Path) -> dict:
    files = verify_inputs(out, built=True)
    payload = json.loads((out / BUNDLE).read_text(encoding="utf-8"))
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1 or payload.get("country") != "CH" or payload.get("dataset") != "tcc-v9-switzerland":
        raise ValueError("Swiss bundle schema invalid")
    from scripts.guard_swiss_bundle_refresh import validate_refresh
    validate_refresh(None, payload)
    if report.get("counts") != payload.get("counts") or report.get("sourceStats") != payload.get("sourceStats"):
        raise ValueError("Swiss bundle report inconsistent")
    missing = {row.get("file") for row in payload.get("sourceStats", []) if row.get("status") == "missing_or_empty"}
    fixture = json.loads((out / "input-manifest.json").read_text(encoding="utf-8")).get("fixtureMode") is True
    allowed_missing = {"data/switzerland/move-direct-tariffs.json", "data/switzerland/move-direct-tariffs-second-pass.json"}
    if not fixture and not missing <= allowed_missing:
        raise ValueError("Unexpected Swiss tariff overlay missing")
    if any(row.get("status") not in {"loaded", "missing_or_empty"} for row in payload.get("sourceStats", [])):
        raise ValueError("Swiss tariff overlay unreadable")
    raw = gzip.decompress((out / NATIONAL).read_bytes())
    snapshot = report.get("nationalSourceSnapshot") or {}
    if snapshot.get("rawSha256") != hashlib.sha256(raw).hexdigest() or snapshot.get("rawBytes") != len(raw):
        raise ValueError("Swiss national output SHA mismatch")
    if (out / NATIONAL).read_bytes() != gzip.compress(raw, compresslevel=9, mtime=0):
        raise ValueError("Swiss national output differs from verified input")
    if not files:
        raise ValueError("Swiss inputs missing")
    return report


def run(out: Path, source: Path) -> None:
    out, source = out.resolve(), source.resolve()
    if out == ROOT or ROOT in out.parents or source == ROOT or ROOT in source.parents or out == source:
        raise ValueError("Swiss bundle must run outside checkout with separate input")
    files = verify_inputs(source)
    for name in files:
        destination = out / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, destination)
    original_national = out / "input_snapshot" / NATIONAL
    original_national.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / NATIONAL, original_national)
    shutil.copy2(source / "input-manifest.json", out / "input-manifest.json")
    for path in (SCRIPT, GUARD):
        destination = out / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, destination)
    (out / REPORT).parent.mkdir(parents=True, exist_ok=True)
    # Preserve the constructor; redirect only its known national fetch to the signed snapshot.
    bootstrap = """import gzip, io, runpy, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path('scripts').resolve()))
source = Path('data/national/switzerland_oicp_source.json.gz')
def offline_open(request, timeout=None):
    if request.full_url != 'https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json':
        raise ValueError('Unexpected national URL')
    return io.BytesIO(gzip.decompress(source.read_bytes()))
urllib.request.urlopen = offline_open
runpy.run_path('scripts/build_swiss_tcc_v9_bundle.py', run_name='__main__')
"""
    result = subprocess.run([sys.executable, "-c", bootstrap], cwd=out, text=True, capture_output=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f"Historical Swiss bundle constructor failed: {result.stderr[-1000:]}")
    validate_output(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.source)


if __name__ == "__main__":
    main()
