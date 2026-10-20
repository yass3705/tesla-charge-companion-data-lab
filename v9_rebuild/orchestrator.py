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
        elif spec.get("module") == "nl_dotnl" and source_id == "NL:dotnl":
            script = root / "v9_rebuild/nl_dotnl.py"
            if not script.is_file() or spec["secret_names"]:
                raise ValueError("DOT-NL module or authentication contract invalid")
            spec["output_file"] = "data/national/netherlands_dotnl/runtime/manifest.json"
            spec["manifest_sha256"] = sha256(script)
        elif spec.get("module") == "electroverse" and source_id in {"FR:electroverse_daily", "FR:electroverse_full"}:
            from v9_rebuild.electroverse import CACHE, MAPPING
            if spec["secret_names"] != ["ELECTROVERSE_API_KEY"] or spec.get("mode") != source_id.rsplit("_", 1)[-1]:
                raise ValueError("Electroverse source/mode/authentication mismatch")
            if spec["mode"] == "full" and spec.get("max_chunks") != 1:
                raise ValueError("Electroverse full must be bounded to one legacy chunk per run")
            for method in ("electroverse_daily_delta_selector.mjs", "electroverse_force_chunk_selection.mjs", "electroverse_hybrid_refresh.mjs"):
                if not (root / "scripts" / method).is_file():
                    raise ValueError(f"Missing preserved Electroverse method: {method}")
            if not (root / MAPPING).is_file() or not (root / CACHE / "manifest.json").is_file():
                raise ValueError("Missing Electroverse mapping or cached state")
            spec["output_file"] = (CACHE / "manifest.json").as_posix()
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/electroverse.py")
        elif spec.get("module") == "electroverse_status" and source_id == "FR:electroverse_status":
            if spec["secret_names"] != ["ELECTROVERSE_API_KEY"]:
                raise ValueError("Electroverse status authentication contract changed")
            for name in ("electroverse_status_incremental.mjs", "electroverse_merge_status_partitions.mjs"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing preserved Electroverse status method: {name}")
            spec["output_file"] = "data/electroverse/live_statuses/manifest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/electroverse_status.py")
        elif spec.get("module") == "electroverse_overlay" and source_id == "FR:electroverse_overlay":
            if spec["secret_names"] or not (root / "scripts/build_electroverse_france_evse_overlay.mjs").is_file() or not (root / "scripts/audit_electroverse_status_gate_postbuild.mjs").is_file():
                raise ValueError("Electroverse overlay historical method missing or unexpected secret")
            spec["output_file"] = "data/platforms/electroverse/france-evse/manifest.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/electroverse_overlay.py")
        elif spec.get("module") == "isolated_script" and source_id == "FR:atlante_direct":
            script = safe_relative(spec.get("script", ""))
            if script.as_posix() != "scripts/atlante_station_tariffs.py" or spec["secret_names"] != ["ATLANTE_API_SUBSCRIPTION_KEY"]:
                raise ValueError("Atlante direct historical method changed")
            spec["output_file"] = "data/national/atlante_direct_stations_france.json.gz"
            spec["manifest_sha256"] = sha256(root / script)
        elif spec.get("module") == "belib_chain" and source_id == "FR:belib":
            if spec["secret_names"]:
                raise ValueError("Belib historical collection has no secret")
            for name in ("belib_official.py", "belib_station_base.py"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing historical Belib script: {name}")
            spec["output_file"] = "data/national/belib_stations_paris.json"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/belib.py")
        elif spec.get("module") == "ionity_family" and source_id == "FR:ionity_direct_family":
            if spec["secret_names"]:
                raise ValueError("IONITY Direct historical method has no secret")
            for name in ("ionity_station_tariffs.py", "ionity_station_tariffs_uk.py"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing historical IONITY script: {name}")
            spec["output_file"] = "data/national/ionity_direct_stations_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/ionity.py")
        elif spec.get("module") == "fastned_family" and source_id == "FR:fastned_inventory_family":
            if spec["secret_names"]:
                raise ValueError("Fastned historical inventory has no secret")
            for name in ("fastned_station_inventory.py", "fastned_station_inventory_uk.py"):
                if not (root / "scripts" / name).is_file():
                    raise ValueError(f"Missing historical Fastned script: {name}")
            spec["output_file"] = "data/national/fastned_direct_stations_france.json.gz"
            spec["manifest_sha256"] = sha256(root / "v9_rebuild/fastned.py")
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


def previous_electroverse_state(out_root: Path, source_id: str, module: str = "electroverse") -> Path | None:
    """Use a previously validated immutable artifact as the next collection seed."""
    from v9_rebuild.electroverse import validate_state
    from v9_rebuild.electroverse_status import validate_partial
    for base in (out_root / "input_state", out_root):
        manifest_path = base / "manifest.json"
        if not manifest_path.is_file():
            if base.name == "input_state" and base.exists():
                raise ValueError("Provided Electroverse state has no collection manifest")
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            if base.name == "input_state":
                raise ValueError("Provided Electroverse state manifest is unreadable")
            continue
        rows = [row for row in payload.get("sources", []) if row.get("status") == "ok" and row.get("module") == module]
        if base.name == "input_state" and not rows:
            raise ValueError("Provided artifact contains no validated source for this module")
        rows.sort(key=lambda row: row.get("source") != source_id)
        for row in rows:
            try:
                artifact = base / safe_relative(row["artifact"])
                if not artifact.resolve().is_relative_to(base.resolve()) or sha256(artifact) != row["sha256"]:
                    continue
                state = artifact.parents[3]
                if module == "electroverse_status":
                    validate_partial(state)
                else:
                    validate_state(state)
                digest, files = artifact_digest(state)
                if digest != row.get("artifact_set_sha256") or files != row.get("files"):
                    continue
                return state
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if rows:
            raise ValueError("Previous Electroverse artifact failed immutable integrity checks")
    return None


def validated_dependency(bundle: Path, source_id: str, module: str) -> Path:
    """Resolve one exact source from a downloaded immutable collection bundle."""
    from v9_rebuild.electroverse import validate_state
    from v9_rebuild.electroverse_status import validate_complete
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise ValueError("Dependency collection manifest is incomplete")
    rows = [row for row in manifest.get("sources", []) if row.get("source") == source_id
            and row.get("module") == module and row.get("status") == "ok"]
    if len(rows) != 1:
        raise ValueError(f"Missing validated dependency: {source_id}")
    row = rows[0]
    relative = safe_relative(row["artifact"])
    if (len(relative.parts) < 5 or relative.parts[:2] != ("objects", source_id.replace(":", "_"))):
        raise ValueError(f"Dependency object path invalid: {source_id}")
    artifact = bundle / relative
    if not artifact.resolve().is_relative_to(bundle.resolve()) or sha256(artifact) != row.get("sha256"):
        raise ValueError(f"Dependency manifest SHA mismatch: {source_id}")
    state = bundle / Path(*relative.parts[:3])
    if module == "electroverse_status":
        validate_complete(state, require_fresh_parts=False)
    elif module == "belib_chain":
        from v9_rebuild.belib import validate_output
        validate_output(state)
    elif module == "electroverse":
        validate_state(state)
    else:
        raise ValueError(f"Unsupported dependency module: {module}")
    digest, files = artifact_digest(state)
    if digest != row.get("artifact_set_sha256") or files != row.get("files"):
        raise ValueError(f"Dependency file integrity mismatch: {source_id}")
    return state


def validate_isolated_script_output(spec: dict, output: Path) -> bool:
    with gzip.open(output, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if spec["id"] == "FR:atlante_direct":
        scope = data.get("scope") or {}
        locations = data.get("locations")
        if (data.get("dataset") != "atlante-direct-operated-stations-france" or data.get("operator") != "Atlante"
                or data.get("country") != "FR" or scope.get("requiredCpo") != "FRATL"
                or scope.get("onlyOperatedLocations") is not True or scope.get("partnerLocationsIncluded") is not False
                or not isinstance(locations, list) or data.get("counts", {}).get("franceLocationCount") != len(locations)):
            return False
        ids = set()
        for row in locations:
            key = row.get("id")
            if (not key or key in ids or row.get("countryCode") != "FR" or row.get("partyId") != "ATL"
                    or row.get("operatorName") != "Atlante" or not isinstance(row.get("connectors"), list)):
                return False
            ids.add(key)
        return True
    return False


def run_source(spec: dict, out_root: Path, *, root: Path = ROOT, attempts: int = 2, timeout_s: int = 2400, runner=subprocess.run) -> dict:
    source_id = spec["id"]
    missing = [name for name in spec["secret_names"] if not os.environ.get(name)]
    if missing:
        return {"source": source_id, "status": "failed", "reason": "missing_required_secret", "missing_secret_names": missing}
    source_dir = out_root / "objects" / source_id.replace(":", "_")
    source_dir.mkdir(parents=True, exist_ok=True)
    electroverse_module = spec["module"] == "electroverse"
    status_module = spec["module"] == "electroverse_status"
    overlay_module = spec["module"] == "electroverse_overlay"
    belib_module = spec["module"] == "belib_chain"
    ionity_module = spec["module"] == "ionity_family"
    fastned_module = spec["module"] == "fastned_family"
    checkpoint_module = electroverse_module or status_module
    checkpoint = out_root / "checkpoints" / source_id.replace(":", "_")
    previous_state = previous_electroverse_state(out_root, source_id, spec["module"]) if checkpoint_module else None
    belib_prior = None
    if belib_module and (out_root / "input_state").is_dir():
        try:
            belib_prior = validated_dependency(out_root / "input_state", source_id, "belib_chain")
        except (OSError, ValueError, KeyError, TypeError):
            return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
    operator_module = spec["module"] == "operator_manifest"
    nl_module = spec["module"] == "nl_dotnl"
    isolated_script = spec["module"] == "isolated_script"
    reason = "collector_failed"
    for attempt in range(1, attempts + 1):
        if checkpoint_module and checkpoint.is_dir():
            from v9_rebuild.electroverse import validate_state
            from v9_rebuild.electroverse_status import validate_partial
            try:
                validate_partial(checkpoint) if status_module else validate_state(checkpoint, require_complete=False)
            except (OSError, ValueError, KeyError, TypeError):
                return {"source": source_id, "status": "failed", "reason": "collector_checkpoint_invalid", "attempts": attempt - 1}
        staged = checkpoint if checkpoint_module and checkpoint.is_dir() else Path(tempfile.mkdtemp(prefix="attempt-", dir=source_dir))
        try:
            if overlay_module:
                dependencies = out_root / "input_dependencies"
                status_bundle = dependencies / "FR_electroverse_status"
                tariff_bundles = [(source, dependencies / source.replace(":", "_")) for source in ("FR:electroverse_daily", "FR:electroverse_full")]
                present_tariffs = [(source, path) for source, path in tariff_bundles if path.is_dir()]
                if not status_bundle.is_dir() or len(present_tariffs) != 1:
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_missing", "attempts": 0}
                try:
                    tariff_id, tariff_bundle = present_tariffs[0]
                    tariff_input = validated_dependency(tariff_bundle, tariff_id, "electroverse")
                    status_input = validated_dependency(status_bundle, "FR:electroverse_status", "electroverse_status")
                except (OSError, ValueError, KeyError, TypeError, RuntimeError, gzip.BadGzipFile):
                    return {"source": source_id, "status": "failed", "reason": "validated_dependency_invalid", "attempts": 0}
            command = ([sys.executable, str(root / safe_relative(spec["script"])), "--out", str(staged / spec["output_file"])]
                       if isolated_script else [sys.executable, str(root / "scripts/operator_manifest_runner.py"), "--operator", spec["operator"], "--out", str(staged)]
                       if operator_module else [sys.executable, str(root / "v9_rebuild/nl_dotnl.py"), "--out", str(staged)]
                       if nl_module else [sys.executable, str(root / "v9_rebuild/electroverse.py"), "--out", str(staged), "--mode", spec["mode"]]
                       if electroverse_module else [sys.executable, str(root / "v9_rebuild/electroverse_status.py"), "--out", str(staged)]
                       if status_module else [sys.executable, str(root / "v9_rebuild/electroverse_overlay.py"), "--out", str(staged), "--source", str(tariff_input), "--status-source", str(status_input)]
                       if overlay_module else [sys.executable, str(root / "v9_rebuild/belib.py"), "--out", str(staged)]
                       if belib_module else [sys.executable, str(root / "v9_rebuild/ionity.py"), "--out", str(staged)]
                       if ionity_module else [sys.executable, str(root / "v9_rebuild/fastned.py"), "--out", str(staged)]
                       if fastned_module else [sys.executable, str(root / "scripts/belgium_nap_full_country.py")])
            if previous_state is not None:
                command.extend(["--source" if status_module else "--resume", str(previous_state)])
            if belib_prior is not None:
                command.extend(["--source", str(belib_prior)])
            if electroverse_module and spec["mode"] == "full":
                command.extend(["--max-chunks", "1"])
            completed = runner(command, cwd=staged if spec["module"] == "belgium_nap" else root,
                               capture_output=True, text=True, timeout=timeout_s, check=False)
            output = staged / spec["output_file"]
            if completed.returncode != 0:
                reason = "collector_exit_nonzero"
                if checkpoint_module and (output.is_file() or status_module):
                    from v9_rebuild.electroverse import validate_state
                    from v9_rebuild.electroverse_status import validate_partial
                    try:
                        validate_partial(staged) if status_module else validate_state(staged, require_complete=False)
                        if staged != checkpoint:
                            checkpoint.parent.mkdir(parents=True, exist_ok=True)
                            if checkpoint.exists():
                                shutil.rmtree(checkpoint)
                            staged.rename(checkpoint)
                            staged = checkpoint
                    except (OSError, ValueError, KeyError, TypeError):
                        reason = "collector_checkpoint_invalid"
                continue
            if not output.is_file():
                reason = "collector_output_missing"
                continue
            try:
                if (isolated_script or ionity_module or fastned_module) and output.suffix == ".gz":
                    with gzip.open(output, "rt", encoding="utf-8") as handle:
                        payload = json.load(handle)
                else:
                    payload = json.loads(output.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError, gzip.BadGzipFile):
                reason = "collector_output_invalid_json"
                continue
            if operator_module:
                source_evidence = payload.get("sourceEvidence") if isinstance(payload, dict) else None
                valid = (isinstance(payload, dict) and payload.get("operator") == spec["expected_operator"]
                         and payload.get("dataset") == spec["expected_dataset"]
                         and payload.get("country") == spec["expected_country"]
                         and isinstance(source_evidence, dict) and source_evidence.get("officialOnly") is True)
            elif nl_module:
                from v9_rebuild.nl_dotnl import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif electroverse_module:
                from v9_rebuild.electroverse import validate_state
                try:
                    validate_state(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                    valid = False
            elif status_module:
                from v9_rebuild.electroverse_status import validate_complete
                try:
                    validate_complete(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                    valid = False
            elif overlay_module:
                from v9_rebuild.electroverse_overlay import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, RuntimeError, gzip.BadGzipFile):
                    valid = False
            elif isolated_script:
                try:
                    valid = validate_isolated_script_output(spec, output)
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif belib_module:
                from v9_rebuild.belib import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError):
                    valid = False
            elif ionity_module:
                from v9_rebuild.ionity import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
            elif fastned_module:
                from v9_rebuild.fastned import validate_output
                try:
                    validate_output(staged)
                    valid = True
                except (OSError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
                    valid = False
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
            elif checkpoint_module and staged == checkpoint:
                shutil.rmtree(checkpoint)
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
                if belib_module and (staged / "reports/belib/latest_diagnostic.json").is_file():
                    diagnostic = out_root / "failures" / source_id.replace(":", "_") / "latest_diagnostic.json"
                    diagnostic.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(staged / "reports/belib/latest_diagnostic.json", diagnostic)
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
