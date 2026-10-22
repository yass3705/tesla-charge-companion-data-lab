"""Read-only GitHub artifact handoff selection for the isolated collector."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v9_rebuild.artifact_selection import choose, choose_overlay_dependencies, main, source_slug


def artifact(kind: str, run_id: int, created: str, *, branch: str = "rebuild/v9-20261020", expired: bool = False) -> dict:
    return {"id": run_id, "name": f"tcc-v9-{kind}-FR_electroverse_full", "created_at": created,
            "expired": expired, "workflow_run": {"id": run_id, "head_branch": branch}}


class ArtifactSelectionTests(unittest.TestCase):
    def test_overlay_uses_two_independent_validated_sources_on_same_branch(self):
        daily = {**artifact("collection", 21, "2026-10-20T01:00:00Z"), "name": "tcc-v9-collection-FR_electroverse_daily"}
        full = artifact("collection", 22, "2026-10-20T02:00:00Z")
        status = {**artifact("collection", 23, "2026-10-20T03:00:00Z"), "name": "tcc-v9-collection-FR_electroverse_status"}
        self.assertEqual(choose_overlay_dependencies([daily], [full], [status], "rebuild/v9-20261020"),
                         ("FR_electroverse_full", 22, 23))
        wrong = {**status, "workflow_run": {"id": 23, "head_branch": "main"}}
        self.assertEqual(choose_overlay_dependencies([daily], [full], [wrong], "rebuild/v9-20261020"),
                         ("FR_electroverse_full", 22, None))

    def test_newer_checkpoint_takes_precedence(self):
        old = artifact("collection", 11, "2026-10-20T01:00:00Z")
        progress = artifact("checkpoints", 12, "2026-10-20T02:00:00Z")
        self.assertEqual(choose([progress], [old], "FR:electroverse_full", "rebuild/v9-20261020"), ("checkpoint", 12))

    def test_newer_validated_state_supersedes_old_checkpoint(self):
        old = artifact("checkpoints", 12, "2026-10-20T02:00:00Z")
        complete = artifact("collection", 13, "2026-10-20T03:00:00Z")
        self.assertEqual(choose([old], [complete], "FR:electroverse_full", "rebuild/v9-20261020"), ("state", 13))

    def test_wrong_branch_and_expired_are_ignored(self):
        wrong = artifact("checkpoints", 15, "2026-10-20T04:00:00Z", branch="main")
        expired = artifact("collection", 16, "2026-10-20T05:00:00Z", expired=True)
        self.assertEqual(choose([wrong], [expired], "FR:electroverse_full", "rebuild/v9-20261020"), ("baseline", None))

    def test_source_id_rejects_unsafe_name(self):
        with self.assertRaises(ValueError):
            source_slug("FR:evil/../../other")

    def test_connected_kerb_app_selects_operator_collection_on_same_branch(self):
        operator = {**artifact("collection", 31, "2026-10-22T00:00:00Z"),
                    "name": "tcc-v9-collection-GB_connected_kerb_operator"}
        wrong = {**operator, "id": 32, "created_at": "2026-10-22T01:00:00Z",
                 "workflow_run": {"id": 32, "head_branch": "main"}}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "github-output"
            args = ["selector", "--repo", "owner/data-lab", "--branch", "rebuild/v9-20261020",
                    "--source", "GB:connected_kerb_app", "--github-output", str(output)]
            with patch("sys.argv", args), patch.dict("os.environ", {"GH_TOKEN": "fixture-token"}), \
                 patch("v9_rebuild.artifact_selection.fetch", side_effect=[[operator, wrong], []]), \
                 patch("builtins.print"):
                main()
            self.assertIn("operator_run_id=31", output.read_text())

    def test_ecarup_coordinate_selects_exact_owner_on_same_branch(self):
        owner = {**artifact("collection", 41, "2026-10-22T00:00:00Z"),
                 "name": "tcc-v9-collection-CH_ecarup_owner"}
        wrong = {**owner, "id": 42, "created_at": "2026-10-22T01:00:00Z",
                 "workflow_run": {"id": 42, "head_branch": "main"}}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "github-output"
            args = ["selector", "--repo", "owner/data-lab", "--branch", "rebuild/v9-20261020",
                    "--source", "CH:ecarup_coordinate", "--github-output", str(output)]
            with patch("sys.argv", args), patch.dict("os.environ", {"GH_TOKEN": "fixture-token"}), \
                 patch("v9_rebuild.artifact_selection.fetch", return_value=[owner, wrong]), \
                 patch("builtins.print"):
                main()
            self.assertIn("ecarup_owner_run_id=41", output.read_text())

    def test_ecarup_finalizer_selects_coordinate_collection_on_same_branch(self):
        coordinate = {**artifact("collection", 51, "2026-10-22T00:00:00Z"),
                      "name": "tcc-v9-collection-CH_ecarup_coordinate"}
        wrong = {**coordinate, "id": 52, "created_at": "2026-10-22T01:00:00Z",
                 "workflow_run": {"id": 52, "head_branch": "main"}}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "github-output"
            args = ["selector", "--repo", "owner/data-lab", "--branch", "rebuild/v9-20261020",
                    "--source", "CH:ecarup_finalization", "--github-output", str(output)]
            with patch("sys.argv", args), patch.dict("os.environ", {"GH_TOKEN": "fixture-token"}), \
                 patch("v9_rebuild.artifact_selection.fetch", return_value=[coordinate, wrong]), \
                 patch("builtins.print"):
                main()
            self.assertIn("ecarup_coordinate_run_id=51", output.read_text())

    def test_plenitude_closeout_selects_official_collection_on_same_branch(self):
        official = {**artifact("collection", 61, "2026-10-22T00:00:00Z"),
                    "name": "tcc-v9-collection-CH_plenitude_official"}
        wrong = {**official, "id": 62, "created_at": "2026-10-22T01:00:00Z",
                 "workflow_run": {"id": 62, "head_branch": "main"}}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "github-output"
            args = ["selector", "--repo", "owner/data-lab", "--branch", "rebuild/v9-20261020",
                    "--source", "CH:plenitude_closeout", "--github-output", str(output)]
            with patch("sys.argv", args), patch.dict("os.environ", {"GH_TOKEN": "fixture-token"}), \
                 patch("v9_rebuild.artifact_selection.fetch", return_value=[official, wrong]), \
                 patch("builtins.print"):
                main()
            self.assertIn("plenitude_run_id=61", output.read_text())


if __name__ == "__main__":
    unittest.main()
