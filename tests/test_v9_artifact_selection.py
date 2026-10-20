"""Read-only GitHub artifact handoff selection for the isolated collector."""

import unittest

from v9_rebuild.artifact_selection import choose, choose_overlay_dependencies, source_slug


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


if __name__ == "__main__":
    unittest.main()
