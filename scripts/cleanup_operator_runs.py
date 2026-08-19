#!/usr/bin/env python3
"""Prune obsolete GitHub Actions runs for validated operator workflows.

Policy:
- Never clean an operator until its validated marker JSON exists in the repo.
- Keep the latest successful run of the active workflow as the reference.
- Preserve any active-workflow run newer than that reference success.
- Delete older completed active-workflow runs.
- Once an operator has migrated to a replacement workflow, delete completed runs
  from explicitly listed legacy workflows. In-progress legacy runs are preserved.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TARGETS = {
    "lidl": {"workflow": "lidl-plus-official-tariff.yml", "marker": "data/operator_direct/lidl_plus_france.json", "legacy_workflows": []},
    "izivia": {"workflow": "izivia-official-tariffs.yml", "marker": "data/operator_direct/izivia_official_france.json", "legacy_workflows": []},
    "fastned": {"workflow": "fastned-official-tariffs.yml", "marker": "data/operator_direct/fastned_official_france.json", "legacy_workflows": []},
    "allego": {
        "workflow": "allego-official-tariffs-v2.yml",
        "marker": "data/operator_direct/allego_official_france.json",
        "legacy_workflows": ["allego-official-tariffs.yml", "allego-render-diagnostic.yml", "allego-static-pricing-hotfix.yml"],
    },
    "totalenergies": {"workflow": "totalenergies-official-tariffs.yml", "marker": "data/operator_direct/totalenergies_official_france.json", "legacy_workflows": []},
    "ionity": {"workflow": "ionity-official-tariffs.yml", "marker": "data/operator_direct/ionity_official_france.json", "legacy_workflows": []},
    "powerdot": {"workflow": "powerdot-official-tariffs.yml", "marker": "data/operator_direct/powerdot_official_france.json", "legacy_workflows": []},
    "vianeo": {"workflow": "vianeo-official-tariffs.yml", "marker": "data/operator_direct/vianeo_official_france.json", "legacy_workflows": []},
}

API = "https://api.github.com"


def api_request(method: str, path: str):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token:
        raise RuntimeError("GH_TOKEN/GITHUB_TOKEN is required")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is required")
    url = f"{API}/repos/{repo}/{path.lstrip('/')}"
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tesla-charge-companion-data-lab-run-cleanup",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return None if not raw else json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed: HTTP {exc.code}: {detail[:500]}") from exc


def list_runs(workflow_file: str) -> list[dict]:
    encoded = urllib.parse.quote(workflow_file, safe="")
    runs: list[dict] = []
    page = 1
    while page <= 10:
        data = api_request("GET", f"actions/workflows/{encoded}/runs?per_page=100&page={page}")
        batch = list((data or {}).get("workflow_runs") or [])
        runs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return runs


def delete_run(run_id: int) -> None:
    api_request("DELETE", f"actions/runs/{run_id}")


def choose_reference_success(runs: list[dict], keep_run_id: int | None) -> dict | None:
    successes = [r for r in runs if r.get("status") == "completed" and r.get("conclusion") == "success"]
    if not successes:
        return None
    if keep_run_id is not None:
        for run in successes:
            if int(run.get("id")) == keep_run_id:
                return run
    successes.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return successes[0]


def cleanup_legacy_workflows(key: str, workflows: list[str]) -> int:
    deleted = 0
    for workflow in workflows:
        try:
            runs = list_runs(workflow)
        except Exception as exc:
            print(f"[{key}] legacy workflow {workflow}: unable to list ({exc}); skipping")
            continue
        workflow_deleted = 0
        for run in runs:
            if run.get("status") != "completed":
                continue
            run_id = int(run.get("id"))
            try:
                delete_run(run_id)
                workflow_deleted += 1
                deleted += 1
                print(f"[{key}] deleted legacy run {run_id} from {workflow} ({run.get('conclusion')}, {run.get('created_at') or ''})")
            except Exception as exc:
                print(f"[{key}] could not delete legacy run {run_id}: {exc}")
        print(f"[{key}] legacy workflow {workflow}: deleted {workflow_deleted} completed run(s)")
    return deleted


def cleanup_target(key: str, keep_run_id: int | None = None) -> tuple[int, int | None]:
    cfg = TARGETS[key]
    marker = Path(cfg["marker"])
    workflow = cfg["workflow"]
    if not marker.exists():
        print(f"[{key}] marker missing ({marker}); operator not validated yet -> preserving all runs")
        return 0, None
    runs = list_runs(workflow)
    reference = choose_reference_success(runs, keep_run_id)
    if not reference:
        print(f"[{key}] no successful completed run found -> preserving active and legacy runs")
        return 0, None
    ref_id = int(reference["id"])
    ref_created = reference.get("created_at") or ""
    deleted = 0
    for run in runs:
        run_id = int(run.get("id"))
        if run_id == ref_id or run.get("status") != "completed":
            continue
        created = run.get("created_at") or ""
        if created >= ref_created:
            continue
        delete_run(run_id)
        deleted += 1
        print(f"[{key}] deleted old active run {run_id} ({run.get('conclusion')}, {created})")
    legacy = list(cfg.get("legacy_workflows") or [])
    if legacy:
        deleted += cleanup_legacy_workflows(key, legacy)
    print(f"[{key}] kept reference success run {ref_id}; deleted {deleted} obsolete run(s)")
    return deleted, ref_id


def prune_cleanup_workflow(current_run_id: int | None) -> int:
    try:
        runs = list_runs("cleanup-operator-runs.yml")
    except Exception as exc:
        print(f"[cleanup] unable to list cleanup workflow history: {exc}")
        return 0
    deleted = 0
    for run in runs:
        run_id = int(run.get("id"))
        if current_run_id is not None and run_id == current_run_id:
            continue
        if run.get("status") != "completed":
            continue
        try:
            delete_run(run_id)
            deleted += 1
            print(f"[cleanup] deleted previous cleanup run {run_id}")
        except Exception as exc:
            print(f"[cleanup] could not delete previous cleanup run {run_id}: {exc}")
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["all", *TARGETS.keys()], default="all")
    parser.add_argument("--keep-run-id", type=int, default=None)
    parser.add_argument("--current-cleanup-run-id", type=int, default=None)
    parser.add_argument("--prune-self", action="store_true")
    args = parser.parse_args()
    keys = list(TARGETS) if args.target == "all" else [args.target]
    total = 0
    for key in keys:
        keep = args.keep_run_id if len(keys) == 1 else None
        deleted, _ = cleanup_target(key, keep_run_id=keep)
        total += deleted
    if args.prune_self:
        total += prune_cleanup_workflow(args.current_cleanup_run_id)
    print(f"Cleanup complete: {total} run(s) deleted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
