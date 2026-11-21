"""Advance the archived REVE cursor once and retain a verified, isolated generation."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v9_rebuild.orchestrator import artifact_digest, read_sources, run_batch, safe_relative
from v9_rebuild.reve_stream import DATA, FILES, save_checkpoint, seed_archived_checkpoint, validate_checkpoint

REPO = "yass3705/tesla-charge-companion-data-lab"
WORKFLOW = 425938005
TITLE = "V9 REVE bounded stream"
NAME = "tcc-v9-REVE-generation"
ID = "ES:reve_stream"


def api(path):
    return subprocess.check_output(["gh", "api", f"repos/{REPO}/" + path])


def read(path):
    return json.loads(path.read_bytes())


def previous_run(current, get=api):
    """Never skip a failed or expired generation in favor of older pages."""
    for page in range(1, 11):
        runs = json.loads(get(f"actions/workflows/{WORKFLOW}/runs?branch=main&per_page=100&page={page}"))["workflow_runs"]
        for run in runs:
            if run["run_number"] >= current["run_number"] or run["display_title"] != TITLE:
                continue
            if (run["status"] != "completed" or run["event"] not in {"schedule", "workflow_dispatch"}
                    or run["workflow_id"] != WORKFLOW or run["head_branch"] != "main"
                    or run["repository"]["full_name"] != REPO):
                raise ValueError("Previous REVE execution cannot be trusted")
            return run
        if len(runs) < 100:
            return None
    raise ValueError("REVE history incomplete; refusing to rewind")


def restore(run, checkpoint, get=api):
    artifacts = json.loads(get(f"actions/runs/{run['id']}/artifacts?per_page=100"))["artifacts"]
    matches = [a for a in artifacts if a["name"] == NAME]
    if len(matches) != 1 or matches[0]["expired"]:
        raise ValueError("Previous REVE checkpoint unavailable; refusing to rewind")
    a = matches[0]
    parent = a["workflow_run"]
    if parent["id"] != run["id"] or parent["head_sha"] != run["head_sha"] or parent["head_branch"] != "main":
        raise ValueError("Previous REVE checkpoint origin mismatch")
    raw = get(f"actions/artifacts/{a['id']}/zip")
    if a["digest"] != "sha256:" + hashlib.sha256(raw).hexdigest() or len(raw) != a["size_in_bytes"]:
        raise ValueError("REVE checkpoint ZIP integrity mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or any(stat.S_ISLNK(i.external_attr >> 16) for i in z.infolist()):
            raise ValueError("Invalid REVE checkpoint ZIP")
        receipt = json.loads(z.read("receipt.json"))
        pointer = json.loads(z.read("current.json"))
        generation = pointer["generation"]
        expected = {"current.json", "receipt.json"} | {f"generations/{generation}/{f}" for f in FILES}
        if (set(names) != expected or receipt["runId"] != run["id"] or receipt["head"] != run["head_sha"]
                or receipt["generation"] != generation or receipt["source"] != ID):
            raise ValueError("Previous REVE generation provenance mismatch")
        for name in sorted(expected - {"receipt.json"}):
            target = checkpoint / safe_relative(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
    folder = validate_checkpoint(checkpoint)
    if folder is None or folder.name != generation:
        raise ValueError("REVE state missing")
    if receipt["state"] not in {"partial", "quota", "supplier_error", "complete", "already_complete"}:
        raise ValueError("Unknown previous REVE state")
    return receipt


def collect(out):
    if out.exists() or out.resolve() == ROOT or ROOT in out.resolve().parents:
        raise ValueError("New isolated REVE working directory required")
    current = json.loads(api("actions/runs/" + os.environ["GITHUB_RUN_ID"]))
    if (current["head_sha"] != os.environ["GITHUB_SHA"] or current["workflow_id"] != WORKFLOW
            or current["repository"]["full_name"] != REPO or current["head_branch"] != "main"
            or current["display_title"] != TITLE or current["run_attempt"] != 1):
        raise ValueError("Untrusted REVE execution or duplicate run attempt")
    out.mkdir()
    work = out / "work"
    checkpoint = work / "checkpoints/ES_reve_stream"
    prior = previous_run(current)
    prior_receipt = restore(prior, checkpoint) if prior else None
    os.environ.pop("GH_TOKEN", None)
    before = seed_archived_checkpoint(checkpoint)
    if before is None:
        raise ValueError("Initial REVE checkpoint unavailable")
    state_before = read(before / FILES[0])
    if prior_receipt and prior_receipt["state"] == "supplier_error":
        state_folder, status = before, "supplier_error"
    elif state_before["complete"]:
        # Never claim that a completed snapshot was renewed at a later check.
        state_folder, status = before, "already_complete"
    else:
        spec = next(s for s in read_sources() if s["id"] == ID)
        batch = run_batch([spec], work, attempts=1, workers=1)
        if batch["status"] == "complete":
            row = batch["sources"][0]
            state = work.joinpath(*safe_relative(row["artifact"]).parts[:3])
            if artifact_digest(state) != (row["artifact_set_sha256"], row["files"]):
                raise ValueError("Complete REVE object integrity mismatch")
            save_checkpoint(state / DATA, checkpoint)
        state_folder = validate_checkpoint(checkpoint)
        if not state_folder or state_folder.name == before.name:
            raise ValueError("No new verified generation after requested collector execution")
        report = read(state_folder / FILES[3])
        if report.get("stoppedAfterError"):
            status = "quota" if report["requests"][-1]["status"] == 429 else "supplier_error"
        else:
            status = "complete" if report["stateAfter"]["complete"] else "partial"
        if (status == "complete") != (batch["status"] == "complete"):
            raise ValueError("Collector and checkpoint completion disagree")
    target = out / "retained"
    save_checkpoint(state_folder, target)
    (target / "receipt.json").write_text(json.dumps({
        "source": ID, "runId": current["id"], "head": current["head_sha"], "state": status,
        "parentRunId": prior["id"] if prior else None, "parentGeneration": before.name,
        "generation": state_folder.name, "published": False,
    }, indent=2) + "\n")
    if status == "supplier_error":
        raise RuntimeError("Supplier batch failed; verified generation retained")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    collect(parser.parse_args().out)
