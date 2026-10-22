"""Choose an Electroverse checkpoint or validated state from existing Actions artifacts.

Only GitHub Actions metadata is consulted. The returned run ID is for a
subsequent read-only download; no workflow is dispatched from here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path


SAFE_SOURCE = re.compile(r"^[A-Z]{2}:[a-z0-9_]+$")
SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def source_slug(source_id: str) -> str:
    if not SAFE_SOURCE.fullmatch(source_id):
        raise ValueError("Invalid source ID")
    return source_id.replace(":", "_")


def latest(rows: list[dict], name: str, branch: str) -> dict | None:
    valid = [row for row in rows if row.get("name") == name and row.get("expired") is False
             and (row.get("workflow_run") or {}).get("head_branch") == branch
             and isinstance((row.get("workflow_run") or {}).get("id"), int)]
    return max(valid, key=lambda row: (row.get("created_at") or "", row.get("id") or 0), default=None)


def choose(checkpoints: list[dict], states: list[dict], source_id: str, branch: str) -> tuple[str, int | None]:
    slug = source_slug(source_id)
    checkpoint = latest(checkpoints, f"tcc-v9-checkpoints-{slug}", branch)
    state = latest(states, f"tcc-v9-collection-{slug}", branch)
    if checkpoint and (not state or checkpoint.get("created_at", "") > state.get("created_at", "")):
        return "checkpoint", checkpoint["workflow_run"]["id"]
    if state:
        return "state", state["workflow_run"]["id"]
    return "baseline", None


def choose_overlay_dependencies(tariff_daily: list[dict], tariff_full: list[dict], statuses: list[dict], branch: str) -> tuple[str | None, int | None, int | None]:
    """Select two independent validated collections; never use checkpoints."""
    daily = latest(tariff_daily, "tcc-v9-collection-FR_electroverse_daily", branch)
    full = latest(tariff_full, "tcc-v9-collection-FR_electroverse_full", branch)
    status = latest(statuses, "tcc-v9-collection-FR_electroverse_status", branch)
    tariff = max((row for row in (daily, full) if row), key=lambda row: (row.get("created_at") or "", row.get("id") or 0), default=None)
    return (("FR_electroverse_daily" if tariff is daily else "FR_electroverse_full") if tariff else None,
            tariff["workflow_run"]["id"] if tariff else None,
            status["workflow_run"]["id"] if status else None)


def fetch(repo: str, name: str, token: str) -> list[dict]:
    query = urllib.parse.urlencode({"name": name, "per_page": 100})
    url = f"https://api.github.com/repos/{repo}/actions/artifacts?{query}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                                    "Accept": "application/vnd.github+json",
                                                    "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload.get("artifacts"), list):
        raise ValueError("Unexpected GitHub artifact response")
    return payload["artifacts"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    if not SAFE_REPO.fullmatch(args.repo) or not args.branch or "\n" in args.branch:
        parser.error("Invalid repository or branch")
    slug = source_slug(args.source)
    token = os.environ.get("GH_TOKEN")
    if not token:
        parser.error("GH_TOKEN is required")
    if args.source == "FR:electroverse_overlay":
        daily = fetch(args.repo, "tcc-v9-collection-FR_electroverse_daily", token)
        full = fetch(args.repo, "tcc-v9-collection-FR_electroverse_full", token)
        statuses = fetch(args.repo, "tcc-v9-collection-FR_electroverse_status", token)
        tariff_slug, tariff_run, status_run = choose_overlay_dependencies(daily, full, statuses, args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id=\nstate_run_id=\n")
            handle.write(f"tariff_slug={tariff_slug or ''}\ntariff_run_id={tariff_run or ''}\nstatus_run_id={status_run or ''}\n")
        print(json.dumps({"source": args.source, "tariff_run_id": tariff_run, "status_run_id": status_run}))
        return
    if args.source in {"FR:waat_monta_sharded", "FR:waat_monta_public"}:
        rows = fetch(args.repo, "tcc-v9-collection-FR_waat_inventory", token)
        dependency = latest(rows, "tcc-v9-collection-FR_waat_inventory", args.branch)
        checkpoints = fetch(args.repo, f"tcc-v9-checkpoints-{slug}", token)
        states = fetch(args.repo, f"tcc-v9-collection-{slug}", token)
        kind, run_id = choose(checkpoints, states, args.source, args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id={run_id if kind == 'checkpoint' else ''}\n")
            handle.write(f"state_run_id={run_id if kind == 'state' else ''}\n")
            handle.write(f"inventory_run_id={dependency['workflow_run']['id'] if dependency else ''}\n")
        print(json.dumps({"source": args.source, "inventory_run_id": dependency["workflow_run"]["id"] if dependency else None}))
        return
    if args.source == "GB:connected_kerb_app":
        rows = fetch(args.repo, "tcc-v9-collection-GB_connected_kerb_operator", token)
        dependency = latest(rows, "tcc-v9-collection-GB_connected_kerb_operator", args.branch)
        states = fetch(args.repo, f"tcc-v9-collection-{slug}", token)
        state = latest(states, f"tcc-v9-collection-{slug}", args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id=\n")
            handle.write(f"state_run_id={state['workflow_run']['id'] if state else ''}\n")
            handle.write(f"operator_run_id={dependency['workflow_run']['id'] if dependency else ''}\n")
        print(json.dumps({"source": args.source, "operator_run_id": dependency["workflow_run"]["id"] if dependency else None}))
        return
    if args.source == "CH:ecarup_coordinate":
        rows = fetch(args.repo, "tcc-v9-collection-CH_ecarup_owner", token)
        dependency = latest(rows, "tcc-v9-collection-CH_ecarup_owner", args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id=\nstate_run_id=\n")
            handle.write(f"ecarup_owner_run_id={dependency['workflow_run']['id'] if dependency else ''}\n")
        print(json.dumps({"source": args.source, "ecarup_owner_run_id": dependency["workflow_run"]["id"] if dependency else None}))
        return
    if args.source == "CH:ecarup_finalization":
        rows = fetch(args.repo, "tcc-v9-collection-CH_ecarup_coordinate", token)
        dependency = latest(rows, "tcc-v9-collection-CH_ecarup_coordinate", args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id=\nstate_run_id=\n")
            handle.write(f"ecarup_coordinate_run_id={dependency['workflow_run']['id'] if dependency else ''}\n")
        print(json.dumps({"source": args.source, "ecarup_coordinate_run_id": dependency["workflow_run"]["id"] if dependency else None}))
        return
    if args.source == "CH:plenitude_closeout":
        rows = fetch(args.repo, "tcc-v9-collection-CH_plenitude_official", token)
        dependency = latest(rows, "tcc-v9-collection-CH_plenitude_official", args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id=\nstate_run_id=\n")
            handle.write(f"plenitude_run_id={dependency['workflow_run']['id'] if dependency else ''}\n")
        print(json.dumps({"source": args.source, "plenitude_run_id": dependency["workflow_run"]["id"] if dependency else None}))
        return
    if args.source in {"MA:kilowatt_reconcile", "MA:kilowatt_tariff_overlay"}:
        rows = fetch(args.repo, "tcc-v9-collection-MA_kilowatt_inventory", token)
        dependency = latest(rows, "tcc-v9-collection-MA_kilowatt_inventory", args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id=\nstate_run_id=\n")
            handle.write(f"kilowatt_run_id={dependency['workflow_run']['id'] if dependency else ''}\n")
        print(json.dumps({"source": args.source, "kilowatt_run_id": dependency["workflow_run"]["id"] if dependency else None}))
        return
    if args.source == "CH:ebs_closeout":
        rows = fetch(args.repo, "tcc-v9-collection-CH_ebs_ecarup", token)
        dependency = latest(rows, "tcc-v9-collection-CH_ebs_ecarup", args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id=\nstate_run_id=\n")
            handle.write(f"ebs_run_id={dependency['workflow_run']['id'] if dependency else ''}\n")
        print(json.dumps({"source": args.source, "ebs_run_id": dependency["workflow_run"]["id"] if dependency else None}))
        return
    if args.source == "CH:powerup_closeout":
        rows = fetch(args.repo, "tcc-v9-collection-CH_powerup_monta", token)
        dependency = latest(rows, "tcc-v9-collection-CH_powerup_monta", args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id=\nstate_run_id=\n")
            handle.write(f"powerup_run_id={dependency['workflow_run']['id'] if dependency else ''}\n")
        print(json.dumps({"source": args.source, "powerup_run_id": dependency["workflow_run"]["id"] if dependency else None}))
        return
    if args.source == "CH:swiss_integration":
        rows = fetch(args.repo, "tcc-v9-collection-CH_swiss_bundle", token)
        dependency = latest(rows, "tcc-v9-collection-CH_swiss_bundle", args.branch)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"slug={slug}\ncheckpoint_run_id=\nstate_run_id=\n")
            handle.write(f"swiss_bundle_run_id={dependency['workflow_run']['id'] if dependency else ''}\n")
        print(json.dumps({"source": args.source, "swiss_bundle_run_id": dependency["workflow_run"]["id"] if dependency else None}))
        return
    checkpoints = fetch(args.repo, f"tcc-v9-checkpoints-{slug}", token)
    states = fetch(args.repo, f"tcc-v9-collection-{slug}", token)
    kind, run_id = choose(checkpoints, states, args.source, args.branch)
    with args.github_output.open("a", encoding="utf-8") as handle:
        handle.write(f"slug={slug}\ncheckpoint_run_id={run_id if kind == 'checkpoint' else ''}\n")
        handle.write(f"state_run_id={run_id if kind == 'state' else ''}\n")
    print(json.dumps({"source": args.source, "state_kind": kind, "run_id": run_id}))


if __name__ == "__main__":
    main()
