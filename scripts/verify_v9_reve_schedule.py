"""Verify a real hourly REVE run against its parent checkpoint without provider calls."""
import argparse
import json
from pathlib import Path
import tempfile

from scheduled_v9_reve import FILES, NAME, REPO, TITLE, WORKFLOW, api, previous_run, read, restore
from v9_rebuild.reve_stream import validate_checkpoint


def cursor(state):
    return [state["nextTariffPage"], state["nextStatusPage"]]


def verify(run_id):
    run = json.loads(api(f"actions/runs/{run_id}"))
    if (run["id"] != run_id or run["repository"]["full_name"] != REPO or run["workflow_id"] != WORKFLOW
            or run["event"] != "schedule" or run["head_branch"] != "main" or run["status"] != "completed"
            or run["conclusion"] != "success" or run["display_title"] != TITLE):
        raise ValueError("Expected completed scheduled REVE run")
    prior = previous_run(run)
    if not prior:
        raise ValueError("Expected prior REVE checkpoint")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        parent = restore(prior, base / "parent")
        current = restore(run, base / "current")
        if current["parentRunId"] != prior["id"] or current["parentGeneration"] != parent["generation"]:
            raise ValueError("REVE checkpoint ancestry mismatch")
        before, after = (validate_checkpoint(base / name) for name in ["parent", "current"])
        old, new = read(before / FILES[0]), read(after / FILES[0])
        report = read(after / FILES[3])
        attempts = report["requestsAttempted"]
        if current["state"] == "already_complete":
            attempts = 0  # copied report dates back to the run that completed acquisition
        if attempts == 0 and any((before / f).read_bytes() != (after / f).read_bytes() for f in FILES[1:3]):
            raise ValueError("REVE records changed without a request")
        if attempts == 0 and cursor(old) != cursor(new):
            raise ValueError("REVE cursor changed without a request")
        artifacts = json.loads(api(f"actions/runs/{run_id}/artifacts?per_page=100"))["artifacts"]
        artifact = next(a for a in artifacts if a["name"] == NAME)
        return dict(current, artifactId=artifact["id"], zipDigest=artifact["digest"], event=run["event"],
                    requestsAttempted=attempts, previousCursor=cursor(old), currentCursor=cursor(new),
                    quotaUntil=new.get("quotaUntil"), sourceComplete=new["complete"], published=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=int, required=True)
    print(json.dumps(verify(parser.parse_args().run), indent=2))
