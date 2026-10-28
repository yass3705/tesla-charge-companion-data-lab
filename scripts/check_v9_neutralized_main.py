#!/usr/bin/env python3
"""Read-only proof that archived main workflows can be restored byte for byte."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "def205b0de51dd55bd36a2e7fa672031364e6f75"
NEUTRALIZED = "9243cf290a66ead623d32b7513ad1ebe8fe93001"
PILOT_REMOVED = "c7204b3ef35fd28fdc9bfbd7f8cc7f5a4a64494d"
BACKUP = "migration/v9/main-workflow-backup-20261026/"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def check() -> dict:
    current = git("rev-parse", "origin/main")
    if current != PILOT_REMOVED:
        raise ValueError("Data Lab origin/main changed since the reviewed pilot teardown")
    if git("rev-list", "--parents", "-n", "1", NEUTRALIZED).split() != [NEUTRALIZED, BASE]:
        raise ValueError("Neutralization is not based on the reviewed main SHA")
    if git("rev-list", "--parents", "-n", "1", PILOT_REMOVED).split() != [PILOT_REMOVED, NEUTRALIZED]:
        raise ValueError("Pilot teardown is not based on the neutralized main SHA")
    old = [path for path in git("ls-tree", "-r", "--name-only", BASE, ".github/workflows").splitlines()
           if path.endswith((".yml", ".yaml"))]
    active = [path for path in git("ls-tree", "-r", "--name-only", current, ".github/workflows").splitlines()
              if path.endswith((".yml", ".yaml"))]
    if active or len(old) != 1207:
        raise ValueError("Unexpected active or archived workflow set")
    backups = git("ls-tree", "-r", "--name-only", current, BACKUP).splitlines()
    if len(backups) != len(old):
        raise ValueError("Workflow archive is incomplete")
    for path in old:
        backup = BACKUP + Path(path).name
        if git("rev-parse", BASE + ":" + path) != git("rev-parse", current + ":" + backup):
            raise ValueError("Workflow archive differs from original: " + path)
    return {"status": "PASS", "currentMainSha": current, "reviewedBaseSha": BASE,
            "archivedWorkflows": len(old), "activeMainWorkflows": len(active),
            "exactBlobRestorationPossible": True}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
