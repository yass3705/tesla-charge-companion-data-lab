#!/usr/bin/env python3
"""Read-only, branch-scoped Electroverse checkpoint selector (no provider calls)."""
import argparse
import json
import re
import subprocess
from pathlib import Path

REPO = "yass3705/tesla-charge-companion-data-lab"
BRANCH = "rebuild/v9-20261020"
WORKFLOW = ".github/workflows/v9-electroverse-resume.yml"
ROOT_RUN = 44912790561
ROOT_ARTIFACT = 14711673559
ROOT_HEAD = "2d19e361530f5a66072a56b6491f16779a9a823f"
ROOT_ZIP_SHA = "a31e1630c39271e7f912a5d4e3262aa95a924a1f0d5dbb291f61d337b82c2879"
WINDOW = "tcc-v9-electroverse-window"
COMPLETE = "tcc-v9-electroverse-complete"
FAILURE = "tcc-v9-electroverse-failure"
# No generic failed run is trusted. This one failed run was independently
# compared with its parent across every mapped identity and shard.
APPROVED_FAILURE_ID = 14729002853
APPROVED_FAILURE_RUN = 44956526554
APPROVED_FAILURE_HEAD = "1edd310ebbad1d554f7bbe3c8599678dacbd440f"
APPROVED_FAILURE_SHA = "2e1c1b9c4a8feeb3049f99db8e4df9ef9a1a24cc890359d0ea2aa1bb1a42ecf7"


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", f"repos/{REPO}/{path}"]))


def eligible(rows, name):
    return [a for a in rows if a.get("name") == name and a.get("expired") is False
            and (a.get("workflow_run") or {}).get("head_branch") == BRANCH
            and isinstance((a.get("workflow_run") or {}).get("id"), int)
            and re.fullmatch(r"sha256:[a-f0-9]{64}", str(a.get("digest", "")))]


def approved_failure(row):
    origin = row.get("workflow_run") or {}
    return (row.get("id") == APPROVED_FAILURE_ID
            and row.get("name") == FAILURE
            and row.get("expired") is False
            and row.get("digest") == "sha256:" + APPROVED_FAILURE_SHA
            and origin.get("id") == APPROVED_FAILURE_RUN
            and origin.get("head_sha") == APPROVED_FAILURE_HEAD
            and origin.get("head_branch") == BRANCH)


def choose(windows, completions, failures=None):
    rows = eligible(windows, WINDOW) + eligible(completions, COMPLETE)
    failed = [a for a in failures or [] if a.get("name") == FAILURE
              and a.get("expired") is False]
    approved = [a for a in failed if approved_failure(a)]
    rows.extend(approved)
    selected = max(rows, key=lambda a: (a.get("created_at") or "", a.get("id") or 0),
                   default=None)
    # An unknown more recent failed run cannot silently fall back to an old
    # checkpoint and repeat a whole provider window. Review it first.
    if any(not approved_failure(a) and
           (selected is None or (a.get("created_at") or "") >= (selected.get("created_at") or ""))
           for a in failed):
        raise ValueError("Newer unverified Electroverse failure requires audit")
    return selected


def resolve():
    windows = api(f"actions/artifacts?name={WINDOW}&per_page=100")
    completions = api(f"actions/artifacts?name={COMPLETE}&per_page=100")
    failures = api(f"actions/artifacts?name={FAILURE}&per_page=100")
    if any(x.get("total_count", 0) > 100 for x in (windows, completions, failures)):
        raise ValueError("Paginated checkpoint history needs explicit review")
    selected = choose(windows["artifacts"], completions["artifacts"], failures["artifacts"])
    if selected:
        origin = selected["workflow_run"]
        run_id = origin["id"]
        run = api(f"actions/runs/{run_id}")
        head = origin.get("head_sha")
        recovery = selected["name"] == FAILURE
        expected_conclusion = "failure" if recovery else "success"
        if (run.get("id") != run_id or run.get("path") != WORKFLOW
                or run.get("head_branch") != BRANCH or run.get("head_sha") != head
                or run.get("status") != "completed" or run.get("conclusion") != expected_conclusion
                or run.get("repository", {}).get("full_name") != REPO
                or not re.fullmatch(r"[a-f0-9]{40}", str(head))):
            raise ValueError("Untrusted Electroverse checkpoint run")
        if recovery:
            if not approved_failure(selected):
                raise ValueError("Unapproved failed checkpoint")
            jobs = api(f"actions/runs/{run_id}/jobs?per_page=100")["jobs"]
            if len(jobs) != 1 or jobs[0].get("name") != "resume" or jobs[0].get("conclusion") != "failure":
                raise ValueError("Untrusted failed source job")
        return {"state": ("recovered_failure" if recovery else
                          "complete" if selected["name"] == COMPLETE else "checkpoint"),
                "run": run_id, "artifact": selected["id"], "head": head,
                "zip_sha": selected["digest"].removeprefix("sha256:")}
    run = api(f"actions/runs/{ROOT_RUN}")
    root = api(f"actions/artifacts/{ROOT_ARTIFACT}")
    if (run.get("id") != ROOT_RUN
            or run.get("path") != ".github/workflows/v9-tariff-restoration-pilot.yml"
            or run.get("head_branch") != BRANCH or run.get("head_sha") != ROOT_HEAD
            or run.get("conclusion") != "success" or run.get("status") != "completed"
            or run.get("repository", {}).get("full_name") != REPO
            or root.get("expired") is not False
            or root.get("digest") != "sha256:" + ROOT_ZIP_SHA
            or (root.get("workflow_run") or {}).get("id") != ROOT_RUN):
        raise ValueError("Pinned checkpoint expired or changed; no silent baseline reset")
    return {"state": "checkpoint", "run": ROOT_RUN, "artifact": ROOT_ARTIFACT,
            "head": ROOT_HEAD, "zip_sha": ROOT_ZIP_SHA}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", required=True, type=Path)
    args = parser.parse_args()
    result = resolve()
    with args.github_output.open("a", encoding="utf-8") as out:
        for key, value in result.items():
            print(f"{key}={value}", file=out)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
