"""Offline exact Swiss EBS official-location closeout from a signed first pass."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_v9_swiss_archived_finalizers import ReducedRunner
from v9_rebuild import swiss_ebs_closeout
from v9_rebuild.cwd_script import run as first_pass, validate_output as validate_initial
from v9_rebuild.orchestrator import artifact_digest, read_sources, run_source, sha256


def signed_initial(base: Path, *, full: bool = False) -> tuple[Path, Path]:
    stage = base / "initial-stage"
    first_pass(stage, "swiss_ebs", runner=subprocess.run if full else ReducedRunner("swiss_ebs"))
    validate_initial(stage, "swiss_ebs")
    digest, files = artifact_digest(stage)
    bundle = base / "bundle"
    state = bundle / "objects/CH_ebs_ecarup" / digest
    state.parent.mkdir(parents=True)
    shutil.copytree(stage, state)
    artifact = state / swiss_ebs_closeout.DATA
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": 1,
        "status": "complete", "sources": [{"source": "CH:ebs_ecarup", "module": "cwd_script",
        "status": "ok", "artifact": str(artifact.relative_to(bundle)),
        "sha256": sha256(artifact), "artifact_set_sha256": digest, "files": files}]}))
    return bundle, state


class SwissEbsCloseoutTests(unittest.TestCase):
    def test_full_archived_scope_keeps_sahli_exact_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            _, state = signed_initial(base, full=True)
            swiss_ebs_closeout.run(base / "full", state)
            payload = swiss_ebs_closeout.validate_output(base / "full")
            self.assertEqual(payload["counts"], {"nationalEvseCount": 6,
                "pricedEvseCount": 6, "unresolvedEvseCount": 0})
            sahli = next(row for row in payload["evses"] if row["evseId"] == swiss_ebs_closeout.SAHLI_ID)
            self.assertEqual(sahli["source"], str(swiss_ebs_closeout.SAHLI_PROOF))
            self.assertEqual(len(sahli["matchedPublicConnectors"]), 2)

    def test_exact_official_location_and_signed_orchestration(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle, state = signed_initial(base)
            swiss_ebs_closeout.run(base / "direct", state)
            payload = swiss_ebs_closeout.validate_output(base / "direct")
            self.assertEqual(payload["counts"], {"nationalEvseCount": 2,
                "pricedEvseCount": 2, "unresolvedEvseCount": 0})
            official = next(row for row in payload["evses"] if row["evseId"] == "CH*EBS*E123*0004")
            self.assertEqual(official["classificationSource"], "official location website")
            self.assertEqual(official["tariff"]["currency"], "CHF")
            spec = next(x for x in read_sources() if x["id"] == "CH:ebs_closeout")
            artifacts = base / "artifacts"
            shutil.copytree(bundle, artifacts / "input_dependencies/CH_ebs_ecarup")

            def process(command, **_):
                swiss_ebs_closeout.run(Path(command[command.index("--out") + 1]),
                                       Path(command[command.index("--source") + 1]))
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(spec, artifacts, runner=process)["status"], "ok")
            self.assertEqual(run_source(spec, base / "missing")["reason"], "validated_dependency_missing")
            bad = base / "bad/input_dependencies/CH_ebs_ecarup"
            shutil.copytree(bundle, bad)
            (bad / json.loads((bad / "manifest.json").read_text())["sources"][0]["artifact"]).write_bytes(b"bad")
            self.assertEqual(run_source(spec, base / "bad")["reason"], "validated_dependency_invalid")

    def test_builder_failure_and_price_scope_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            _, state = signed_initial(base)
            def fail(command, **_):
                return subprocess.CompletedProcess(command, 2)
            with self.assertRaisesRegex(RuntimeError, "closeout failed"):
                swiss_ebs_closeout.run(base / "failed", state, runner=fail)
            swiss_ebs_closeout.run(base / "good", state)
            path = base / "good" / swiss_ebs_closeout.DATA
            payload = json.loads(path.read_text())
            payload["evses"][0]["tariff"]["currency"] = "EUR"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "scope invalid"):
                swiss_ebs_closeout.validate_output(base / "good")


if __name__ == "__main__":
    unittest.main()
