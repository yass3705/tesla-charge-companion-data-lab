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
SCHEDULE_INSTALLED = "50c46bf1843560b9b06090c803ef80065f984dc6"
IMPORT_INSTALLED = "83e59ba6a3b1c62a0c729685c2b5da65cbe604e3"
DIRECT_INSTALLED = "56b4a615d82d24f95095e42be7f9a2965ca432b3"
REVE_INSTALLED = "7d5e23ba1ce4037d09bcc94524ca3e48ab0e1a98"
EXTENDED_INSTALLED = "157f7e86f77c69221854e0532eb5d6048228f254"
FX_INSTALLED = "669c53ce877ff1d042061c4722793f38476ae6c5"
SCHEDULE_PATH = ".github/workflows/v9-scheduled.yml"
BACKUP = "migration/v9/main-workflow-backup-20261026/"


def reviewed_scheduled_source(source, head, workflow_id, event):
    if workflow_id != 425938005 or head not in {
        SCHEDULE_INSTALLED, IMPORT_INSTALLED, DIRECT_INSTALLED, REVE_INSTALLED, EXTENDED_INSTALLED, FX_INSTALLED
    }:
        return False
    if source == "GL:fx":
        return head == FX_INSTALLED and event == "schedule"
    if source == "FR:ionity_direct_family":
        return event in {"workflow_dispatch", "schedule"}
    if event != "schedule" or head not in {DIRECT_INSTALLED, REVE_INSTALLED, EXTENDED_INSTALLED, FX_INSTALLED}:
        return False
    cadence = ROOT / "docs/v9-rebuild/evidence/restoration-20261121/direct-cadences.json"
    if head in {EXTENDED_INSTALLED, FX_INSTALLED}:
        cadence = cadence.with_name("direct-cadences-extended.json")
    return any(row["source"] == source for row in json.loads(cadence.read_bytes())["sources"])


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def check() -> dict:
    current = git("rev-parse", "origin/main")
    if current not in (PILOT_REMOVED, SCHEDULE_INSTALLED, IMPORT_INSTALLED, DIRECT_INSTALLED, REVE_INSTALLED, EXTENDED_INSTALLED, FX_INSTALLED):
        raise ValueError("Data Lab origin/main changed since the reviewed pilot teardown")
    if git("rev-list", "--parents", "-n", "1", NEUTRALIZED).split() != [NEUTRALIZED, BASE]:
        raise ValueError("Neutralization is not based on the reviewed main SHA")
    if git("rev-list", "--parents", "-n", "1", PILOT_REMOVED).split() != [PILOT_REMOVED, NEUTRALIZED]:
        raise ValueError("Pilot teardown is not based on the neutralized main SHA")
    old = [path for path in git("ls-tree", "-r", "--name-only", BASE, ".github/workflows").splitlines()
           if path.endswith((".yml", ".yaml"))]
    active = [path for path in git("ls-tree", "-r", "--name-only", current, ".github/workflows").splitlines()
              if path.endswith((".yml", ".yaml"))]
    allowed = [SCHEDULE_PATH] if current in (SCHEDULE_INSTALLED, IMPORT_INSTALLED, DIRECT_INSTALLED, REVE_INSTALLED, EXTENDED_INSTALLED, FX_INSTALLED) else []
    if active != allowed or len(old) != 1207:
        raise ValueError("Unexpected active or archived workflow set")
    if allowed:
        approved = ROOT / "docs/v9-rebuild/evidence/restoration-20261121/v9-scheduled.yml.reviewed"
        if current == IMPORT_INSTALLED:
            approved = approved.with_name("v9-scheduled-import.yml.reviewed")
        if current == DIRECT_INSTALLED:
            approved = approved.with_name("v9-scheduled-direct.yml.reviewed")
        if current == EXTENDED_INSTALLED:
            approved = approved.with_name("v9-scheduled-extended.yml.reviewed")
        if current == FX_INSTALLED:
            approved = approved.with_name("v9-scheduled-fx.yml.reviewed")
        if current == REVE_INSTALLED:
            approved = approved.with_name("v9-scheduled-reve.yml.reviewed")
        if (git("hash-object", str(approved)) != git("rev-parse", current + ":" + SCHEDULE_PATH)
                or git("diff", "--name-only", PILOT_REMOVED, current) != SCHEDULE_PATH):
            raise ValueError("Unreviewed main change")
    # Compare all original and backup blob IDs in two tree reads.
    def blobs(ref, directory):
        rows = git("ls-tree", "-r", ref, directory).splitlines()
        result = {}
        for row in rows:
            meta, name = row.split("\t", 1)
            if not name.endswith((".yml", ".yaml")):
                continue
            result[name.removeprefix(directory.rstrip("/") + "/")] = meta
        return result
    if blobs(BASE, ".github/workflows") != blobs(current, BACKUP):
        raise ValueError("Workflow archive differs from originals")
    return {"status": "PASS", "currentMainSha": current, "reviewedBaseSha": BASE,
            "archivedWorkflows": len(old), "activeMainWorkflows": len(active),
            "exactBlobRestorationPossible": True}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
