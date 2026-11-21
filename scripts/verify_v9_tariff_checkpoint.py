"""Download a failed tariff job's resumable state and verify it before reuse."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.pilot_v9_tariff_chunks import BRANCH, ROOT, SOURCE, verify_checkpoint
from v9_rebuild.electroverse import CACHE, CHUNK_SIZE, MAPPING, read_json
from v9_rebuild.orchestrator import safe_relative

REPO = "yass3705/tesla-charge-companion-data-lab"


def api(path):
    return subprocess.check_output(["gh", "api", f"repos/{REPO}/" + path])


def verify_download(run_id, head, destination):
    destination = destination.resolve()
    if destination == ROOT or ROOT in destination.parents or destination.exists():
        raise ValueError("New isolated checkpoint directory required")
    run = json.loads(api(f"actions/runs/{run_id}"))
    if (run["id"] != run_id or run["repository"]["full_name"] != REPO or run["head_sha"] != head
            or run["head_branch"] != BRANCH or run["path"] != ".github/workflows/v9-tariff-restoration-pilot.yml"
            or run["conclusion"] != "failure" or run["status"] != "completed"):
        raise ValueError("Expected the reviewed failed reconstruction run")
    jobs = json.loads(api(f"actions/runs/{run_id}/jobs?per_page=100"))["jobs"]
    jobs = [j for j in jobs if j["name"] == f"collect ({SOURCE})" and j["conclusion"] == "failure"]
    artifacts = json.loads(api(f"actions/runs/{run_id}/artifacts?per_page=100"))["artifacts"]
    matches = [a for a in artifacts if a["name"] == "tcc-v9-tariff-renewal-failure-0" and not a["expired"]]
    if len(jobs) != 1 or len(matches) != 1:
        raise ValueError("Unique failed job and retained checkpoint required")
    job, artifact = jobs[0], matches[0]
    parent = artifact["workflow_run"]
    if (parent["id"], parent["head_sha"], parent["head_branch"]) != (run_id, head, BRANCH):
        raise ValueError("Checkpoint artifact origin mismatch")
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        stage = Path(tmp) / "verified"
        stage.mkdir()
        archive = stage / "artifact.zip"
        raw = api(f"actions/artifacts/{artifact['id']}/zip")
        digest = hashlib.sha256(raw).hexdigest()
        if artifact["digest"] != "sha256:" + digest or len(raw) != artifact["size_in_bytes"]:
            raise ValueError("Checkpoint ZIP mismatch")
        archive.write_bytes(raw)
        folder = stage / "retained"
        with zipfile.ZipFile(archive) as z:
            seen = set()
            for entry in z.infolist():
                name = safe_relative(entry.filename)
                if name in seen or stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError("Unsafe checkpoint archive")
                seen.add(name)
            z.extractall(folder)
        manifest = read_json(folder / "checkpoint-manifest.json")
        state = verify_checkpoint(folder, expected_sha=manifest["sha256"], expected_head=head, expected_run=run_id)
        result = read_json(folder / "manifest.json")
        if len(result["sources"]) != 1 or result["sources"][0]["source"] != SOURCE or result["sources"][0]["status"] != "failed":
            raise ValueError("Invalid failed source manifest")
        parse = lambda t: datetime.fromisoformat(t.replace("Z", "+00:00"))
        start, end = parse(job["started_at"]), parse(job["completed_at"])
        mapped = {str(m["electroverseLocationPk"]) for m in read_json(state / MAPPING)["mappings"]}
        checked = read_json(state / CACHE / "checked-at.json")["checkedAt"]
        renewed = sorted(pk for pk in mapped if pk in checked and start <= parse(checked[pk]) <= end)
        checkpoint = read_json(state / "v9-electroverse-checkpoint.json")
        pending = checkpoint.get("pending") or {}
        completed = checkpoint["completed"]
        pks = pending.get("pks", [])
        if (checkpoint.get("mode") != "full" or completed != list(range(0, len(completed)*CHUNK_SIZE, CHUNK_SIZE))
                or (pending and pending.get("offset") != len(completed)*CHUNK_SIZE)
                or not isinstance(pks, list) or len(set(pks)) != len(pks) or not set(pks) <= mapped):
            raise ValueError("Inconsistent offsets or unknown identities in checkpoint")
        receipt = dict(source=SOURCE, runId=run_id, head=head, jobId=job["id"], artifactId=artifact["id"],
                       jobStartedAt=job["started_at"], jobCompletedAt=job["completed_at"],
                       reason=result["sources"][0].get("reason"), zipSHA256=digest, fileSetSHA256=manifest["sha256"],
                       filesVerified=len(manifest["files"]), shardsVerified=128, completedChunks=checkpoint["completed"],
                       pendingOffset=pending.get("offset"), pendingLocations=len(pending.get("pks", [])),
                       mappedLocationsCheckedInJob=len(renewed), complete=False)
        (stage / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        stage.rename(destination)
        return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=int)
    parser.add_argument("--head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_download(args.run, args.head, args.out)))
