#!/usr/bin/env python3
"""Check the reviewed proposal offline, using only a disposable Git index.

Does not install workflows, modify refs, enable Actions or execute the pilot.
The reviewed hashes deliberately fail closed after any proposal edit.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "docs/v9-rebuild/pilot"


def check():
    review = json.loads((PROPOSAL / "REVIEW_20261026.json").read_text())
    draft = PROPOSAL / "v9-ionity-pilot.yml.example"
    patch = PROPOSAL / "MAIN_NEUTRALIZATION_PROPOSAL.patch"
    for path, key in ((draft, "draftSha256"), (patch, "patchSha256")):
        if hashlib.sha256(path.read_bytes()).hexdigest() != review[key]:
            raise ValueError("Proposal changed: a new review is required: " + path.name)

    def git(*args, env=None):
        return subprocess.check_output(["git", *args], cwd=ROOT, env=env)

    base = review["baseMainSha"]
    if git("rev-parse", "origin/main").decode().strip() != base:
        raise ValueError("Local origin/main changed: refresh the proposal review")
    before = git("status", "--porcelain=v1", "-z")
    refs = git("show-ref")
    old_files = git("ls-tree", "-r", "--name-only", base, ".github/workflows").decode().splitlines()
    workflows = [p for p in old_files if p.endswith((".yml", ".yaml"))]
    with tempfile.TemporaryDirectory(prefix="tcc-v9-pilot-index-") as temp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / "index"))
        git("read-tree", base, env=env)
        git("apply", "--cached", "--check", str(patch), env=env)
        git("apply", "--cached", str(patch), env=env)
        active = git("ls-files", ".github/workflows", env=env).decode().splitlines()
        if active != review["proposedActiveWorkflowFiles"]:
            raise ValueError("Unexpected proposed active workflow set")
        if git("show", ":" + active[0], env=env) != draft.read_bytes():
            raise ValueError("Installed proposal differs from reviewed draft")
        for old in workflows:
            backup = "migration/v9/main-workflow-backup-20261026/" + Path(old).name
            if git("rev-parse", base + ":" + old) != git("rev-parse", ":" + backup, env=env):
                raise ValueError("Legacy workflow archive changed: " + old)
        git("apply", "--cached", "--reverse", str(patch), env=env)
        if git("write-tree", env=env) != git("rev-parse", base + "^{tree}"):
            raise ValueError("Proposal rollback does not restore the base tree")
    if before != git("status", "--porcelain=v1", "-z") or refs != git("show-ref"):
        raise ValueError("Repository state changed during offline check")
    return {"status": "PASS", "archivedWorkflows": len(workflows),
            "baseMainSha": base, "realIndexAndRefsUnchanged": True,
            "pilotExecuted": False, "remoteStateChecked": False}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
