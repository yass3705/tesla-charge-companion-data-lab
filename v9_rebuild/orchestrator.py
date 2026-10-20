#!/usr/bin/env python3
"""Run approved collector modules into isolated, content-addressed artifacts.

No Git command, branch write, or Production mutation occurs in this process.
The legacy operator-manifest runner is the first migrated module family.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path(__file__).with_name("sources.json")
SAFE_ID = re.compile(r"^[A-Z]{2}:[a-z0-9_]+$")
SAFE_SECRET = re.compile(r"^[A-Z][A-Z0-9_]*$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"Unsafe registry path: {raw}")
    return path


def read_sources(root: Path = ROOT, registry: Path = REGISTRY) -> list[dict]:
    payload = json.loads(registry.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported source registry schema")
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("Source registry must contain a list")
    ids = set()
    for spec in sources:
        source_id = spec.get("id", "")
        if not SAFE_ID.fullmatch(source_id) or source_id in ids:
            raise ValueError(f"Invalid or duplicate source ID: {source_id}")
        ids.add(source_id)
        if not isinstance(spec.get("secret_names"), list) or any(not SAFE_SECRET.fullmatch(name) for name in spec["secret_names"]):
            raise ValueError(f"Invalid secret name list: {source_id}")
        if spec.get("module") == "operator_manifest":
            manifest_path = root / safe_relative(spec.get("manifest", ""))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("key") != spec.get("operator") or source_id != f"{manifest.get('country', 'FR')}:{manifest.get('key')}":
                raise ValueError(f"Source/manifest identity mismatch: {source_id}")
            output = safe_relative(manifest.get("outputFile", ""))
            if len(output.parts) != 1:
                raise ValueError(f"Manifest output must be a filename: {source_id}")
            spec["output_file"] = output.name
            spec["manifest_sha256"] = sha256(manifest_path)
            spec["expected_operator"] = manifest["operator"]
            spec["expected_dataset"] = manifest["dataset"]
            spec["expected_country"] = manifest.get("country", "FR")
        elif spec.get("module") == "belgium_nap" and source_id == "BE:nap":
            script = safe_relative(spec.get("script", ""))
            if script.as_posix() != "scripts/belgium_nap_full_country.py" or not (root / script).is_file():
                raise ValueError("Belgium NAP source script differs from the preserved method")
            if spec["secret_names"] != ["BELGIUM_NAP_TOKEN"]:
                raise ValueError("Belgium NAP authentication contract changed")
            spec["output_file"] = "data/belgium/nap-belgium-manifest.json"
            spec["manifest_sha256"] = sha256(root / script)
        else:
            raise ValueError(f"Unmigrated module cannot execute: {source_id}")
    return sources


def validate_belgium_output(staged: Path, manifest: dict) -> bool:
    pages = manifest.get("pages")
    if manifest.get("country") != "BE" or not isinstance(pages, list) or not pages or manifest.get("pageCount") != len(pages):
        return False
    offsets = [page.get("offset") for page in pages if isinstance(page, dict)]
    if (len(offsets) != len(pages) or any(not isinstance(offset, int) or offset < 0 for offset in offsets)
            or len(set(offsets)) != len(offsets) or pages[-1].get("nextOffset") is not None):
        return False
    for index, page in enumerate(pages):
        if index + 1 < len(pages) and page.get("nextOffset") != pages[index + 1].get("offset"):
            return False
        try:
            path = staged / safe_relative(page["canonicalPath"])
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                if not isinstance(json.load(handle), dict):
                    return False
        except (KeyError, OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            return False
    report_path = staged / "reports/belgium-national-full-extraction-2026-09-28.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    integrity = report.get("integrity") if isinstance(report, dict) else None
    pagination = report.get("pagination") if isinstance(report, dict) else None
    return (isinstance(integrity, dict) and integrity.get("paginationEndedNormally") is True
            and isinstance(pagination, dict) and pagination.get("pageCount") == len(pages))


def artifact_digest(staged: Path) -> tuple[str, list[dict]]:
    files = []
    digest = hashlib.sha256()
    for path in sorted(p for p in staged.rglob("*") if p.is_file()):
        relative = path.relative_to(staged).as_posix()
        file_sha = sha256(path)
        digest.update(relative.encode("utf-8") + b"\0" + file_sha.encode("ascii") + b"\n")
        files.append({"path": relative, "sha256": file_sha, "bytes": path.stat().st_size})
    return digest.hexdigest(), files


def run_source(spec: dict, out_root: Path, *, root: Path = ROOT, attempts: int = 2, timeout_s: int = 2400, runner=subprocess.run) -> dict:
    source_id = spec["id"]
    missing = [name for name in spec["secret_names"] if not os.environ.get(name)]
    if missing:
        return {"source": source_id, "status": "failed", "reason": "missing_required_secret", "missing_secret_names": missing}
    source_dir = out_root / "objects" / source_id.replace(":", "_")
    source_dir.mkdir(parents=True, exist_ok=True)
    operator_module = spec["module"] == "operator_manifest"
    reason = "collector_failed"
    for attempt in range(1, attempts + 1):
        staged = Path(tempfile.mkdtemp(prefix="attempt-", dir=source_dir))
        try:
            command = ([sys.executable, str(root / "scripts/operator_manifest_runner.py"), "--operator", spec["operator"], "--out", str(staged)]
                       if operator_module else [sys.executable, str(root / "scripts/belgium_nap_full_country.py")])
            completed = runner(command, cwd=root if operator_module else staged, capture_output=True, text=True, timeout=timeout_s, check=False)
            output = staged / spec["output_file"]
            if completed.returncode != 0:
                reason = "collector_exit_nonzero"
                continue
            if not output.is_file():
                reason = "collector_output_missing"
                continue
            try:
                payload = json.loads(output.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                reason = "collector_output_invalid_json"
                continue
            if operator_module:
                source_evidence = payload.get("sourceEvidence") if isinstance(payload, dict) else None
                valid = (isinstance(payload, dict) and payload.get("operator") == spec["expected_operator"]
                         and payload.get("dataset") == spec["expected_dataset"]
                         and payload.get("country") == spec["expected_country"]
                         and isinstance(source_evidence, dict) and source_evidence.get("officialOnly") is True)
            else:
                valid = isinstance(payload, dict) and validate_belgium_output(staged, payload)
            if not valid:
                reason = "collector_output_contract_mismatch"
                continue
            digest, files = artifact_digest(staged)
            target = source_dir / digest
            if not target.exists():
                try:
                    staged.rename(target)
                    staged = target
                except OSError:
                    if not target.exists():
                        raise
            return {
                "source": source_id,
                "status": "ok",
                "attempts": attempt,
                "module": spec["module"],
                "manifest_sha256": spec["manifest_sha256"],
                "artifact": str((target / spec["output_file"]).relative_to(out_root)),
                "sha256": sha256(target / spec["output_file"]),
                "artifact_set_sha256": digest,
                "files": files,
            }
        except subprocess.TimeoutExpired:
            reason = "collector_timeout"
        finally:
            if staged.exists() and staged.name.startswith("attempt-"):
                shutil.rmtree(staged)
    return {"source": source_id, "status": "failed", "reason": reason, "attempts": attempts}


def run_batch(sources: list[dict], out_root: Path, *, root: Path = ROOT, workers: int = 2, attempts: int = 2, runner=subprocess.run) -> dict:
    out_root = out_root.resolve()
    if out_root == root.resolve() or root.resolve() in out_root.parents:
        raise ValueError("Artifact directory must be outside the source checkout")
    out_root.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_source, spec, out_root, root=root, attempts=attempts, runner=runner) for spec in sources]
        results = []
        for spec, future in zip(sources, futures):
            try:
                results.append(future.result())
            except Exception:
                results.append({"source": spec["id"], "status": "failed", "reason": "collector_exception"})
        results.sort(key=lambda row: row["source"])
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "complete" if all(row["status"] == "ok" for row in results) else "partial_failure",
        "sources": results,
    }
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="manifest-", suffix=".tmp", dir=out_root, delete=False) as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(out_root / "manifest.json")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", help="Exact source ID; omit to run every migrated source")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.attempts < 1:
        parser.error("workers and attempts must be positive")
    sources = read_sources()
    requested = set(args.source or [])
    known = {spec["id"] for spec in sources}
    if requested - known:
        parser.error(f"Unknown sources: {sorted(requested - known)}")
    selected = [spec for spec in sources if not requested or spec["id"] in requested]
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "sources": [spec["id"] for spec in selected]}))
        return 0
    result = run_batch(selected, args.out, workers=args.workers, attempts=args.attempts)
    print(json.dumps({"status": result["status"], "sources": result["sources"]}, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
