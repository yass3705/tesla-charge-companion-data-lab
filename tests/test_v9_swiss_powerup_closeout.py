"""Offline exact two-EVSE Swiss PowerUp residual closeout."""

import io
import json
import os
import runpy
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.test_v9_swiss_powerup import offline_runner
from v9_rebuild import swiss_powerup, swiss_powerup_closeout
from v9_rebuild.orchestrator import artifact_digest, read_sources, run_source, sha256


def signed_initial(base: Path):
    stage = base / "initial-stage"
    national = {"stations": [{"evseId": "CH*POW*E1"},
                             {"evseId": "CH*POW*E137808"}]}
    monta = {"data": [{"evse_id": "CH*POW*E1", "currency": "CHF", "price_kw": 0.50}]}
    with patch("tests.test_v9_swiss_powerup.NATIONAL", national), \
         patch("tests.test_v9_swiss_powerup.MONTA", monta):
        swiss_powerup.run(stage, runner=offline_runner)
    digest, files = artifact_digest(stage)
    bundle = base / "bundle"
    state = bundle / "objects/CH_powerup_monta" / digest
    state.parent.mkdir(parents=True)
    shutil.copytree(stage, state)
    artifact = state / swiss_powerup.DATA
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": 1,
        "status": "complete", "sources": [{"source": "CH:powerup_monta",
        "module": "swiss_powerup", "status": "ok",
        "artifact": str(artifact.relative_to(bundle)), "sha256": sha256(artifact),
        "artifact_set_sha256": digest, "files": files}]}))
    return bundle, state


def direct_runner(command, **kwargs):
    html = b'<p class="text-lg font-bold">PowerUp 137808</p> 0.55 CHF<span>/kWh</span>'
    old = Path.cwd()
    try:
        os.chdir(kwargs["cwd"])
        with patch("urllib.request.urlopen", return_value=io.BytesIO(html)), \
             redirect_stdout(io.StringIO()):
            runpy.run_path(command[1], run_name="__main__")
    finally:
        os.chdir(old)
    return subprocess.CompletedProcess(command, 0)


class SwissPowerupCloseoutTests(unittest.TestCase):
    def test_exact_target_and_signed_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle, state = signed_initial(base)
            swiss_powerup_closeout.run(base / "direct", state, runner=direct_runner)
            result = swiss_powerup_closeout.validate_output(base / "direct")
            self.assertEqual(result["counts"]["nationalEvseCount"], 2)
            self.assertEqual(result["counts"]["currentPricedEvseCount"], 2)
            self.assertEqual(result["resolvedByDirectPageEvidence"], ["CH*POW*E137808"])
            spec = next(x for x in read_sources() if x["id"] == "CH:powerup_closeout")
            artifacts = base / "artifacts"
            shutil.copytree(bundle, artifacts / "input_dependencies/CH_powerup_monta")

            def process(command, **_):
                swiss_powerup_closeout.run(Path(command[command.index("--out") + 1]),
                                            Path(command[command.index("--source") + 1]),
                                            runner=direct_runner)
                return subprocess.CompletedProcess(command, 0)

            self.assertEqual(run_source(spec, artifacts, runner=process)["status"], "ok")
            self.assertEqual(run_source(spec, base / "missing")["reason"], "validated_dependency_missing")
            bad = base / "bad/input_dependencies/CH_powerup_monta"
            shutil.copytree(bundle, bad)
            (bad / json.loads((bad / "manifest.json").read_text())["sources"][0]["artifact"]).write_bytes(b"bad")
            self.assertEqual(run_source(spec, base / "bad")["reason"], "validated_dependency_invalid")

    def test_failure_and_unpriced_other_evse(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            _, state = signed_initial(base)
            def fail(command, **_):
                return subprocess.CompletedProcess(command, 2)
            with self.assertRaisesRegex(RuntimeError, "closeout failed"):
                swiss_powerup_closeout.run(base / "failed", state, runner=fail)
            swiss_powerup_closeout.run(base / "good", state, runner=direct_runner)
            path = base / "good" / swiss_powerup.DATA
            payload = json.loads(path.read_text())
            payload["resolvedByDirectPageEvidence"] = ["CH*POW*EOTHER"]
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "scope invalid"):
                swiss_powerup_closeout.validate_output(base / "good")


if __name__ == "__main__":
    unittest.main()
