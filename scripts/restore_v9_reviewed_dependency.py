"""Restore a registered, verified GitHub collection into isolated downstream inputs."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v9_rebuild.orchestrator import safe_relative, validated_dependency

REPO = "yass3705/tesla-charge-companion-data-lab"


def restore(source_id, out):
    specs = json.loads((ROOT / "v9_rebuild/sources.json").read_bytes())["sources"]
    spec, = [s for s in specs if s["id"] == source_id]
    receipt = json.loads((ROOT / safe_relative(spec["evidence"])).read_bytes())
    if receipt["sourceId"] != source_id or not spec["github_handoff"].startswith("verified_"):
        raise ValueError("Reviewed source handoff required")
    endpoint = f"repos/{REPO}/actions/artifacts/{receipt['artifactId']}"
    api = lambda path: subprocess.check_output(["gh", "api", path])
    metadata = json.loads(api(endpoint))
    parent = metadata["workflow_run"]
    if (metadata["expired"] or parent["head_branch"] != "rebuild/v9-20261020"
            or parent["id"] != receipt["runId"] or parent["head_sha"] != receipt["runHeadSha"]
            or metadata["digest"] != "sha256:" + receipt["artifactZipSha256"]):
        raise ValueError("Dependency GitHub origin or digest changed")
    out = out.resolve()
    if out == ROOT or ROOT in out.parents or out.exists():
        raise ValueError("Fresh isolated dependency required")
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = api(endpoint + "/zip")
    if len(raw) != metadata["size_in_bytes"] or hashlib.sha256(raw).hexdigest() != receipt["artifactZipSha256"]:
        raise ValueError("Dependency ZIP integrity failed")
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        stage = Path(tmp) / "dependency"
        stage.mkdir()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            seen = set()
            for member in archive.infolist():
                path = safe_relative(member.filename)
                if path in seen or stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("Invalid dependency ZIP member")
                seen.add(path)
            archive.extractall(stage)
        validated_dependency(stage, source_id, spec["module"])
        stage.rename(out)
    return {"source": source_id, "run": parent["id"], "artifact": metadata["id"], "sha256": receipt["artifactZipSha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(restore(args.source, args.out)))
