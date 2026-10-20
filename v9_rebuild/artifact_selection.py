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
    checkpoints = fetch(args.repo, f"tcc-v9-checkpoints-{slug}", token)
    states = fetch(args.repo, f"tcc-v9-collection-{slug}", token)
    kind, run_id = choose(checkpoints, states, args.source, args.branch)
    with args.github_output.open("a", encoding="utf-8") as handle:
        handle.write(f"slug={slug}\ncheckpoint_run_id={run_id if kind == 'checkpoint' else ''}\n")
        handle.write(f"state_run_id={run_id if kind == 'state' else ''}\n")
    print(json.dumps({"source": args.source, "state_kind": kind, "run_id": run_id}))


if __name__ == "__main__":
    main()
