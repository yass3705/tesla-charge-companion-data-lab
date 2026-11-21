import unittest
from scripts.select_v9_electroverse_checkpoint import choose, WINDOW, COMPLETE, BRANCH


def item(name, number, stamp, branch=BRANCH, expired=False):
    return {"id": number, "name": name, "expired": expired,
            "created_at": stamp, "digest": "sha256:" + "a"*64,
            "workflow_run": {"id": number+100, "head_branch": branch}}


class CheckpointSelectorTests(unittest.TestCase):
    def test_empty_or_foreign_branch_uses_reviewed_root(self):
        self.assertIsNone(choose([], []))
        self.assertIsNone(choose([item(WINDOW, 1, "2026-11-22", "main")], []))

    def test_chooses_latest_checkpoint_only(self):
        self.assertEqual(choose([item(WINDOW, 1, "2026-11-21"),
                                 item(WINDOW, 2, "2026-11-22")], [])["id"], 2)

    def test_complete_blocks_replay_of_old_partial(self):
        self.assertEqual(choose([item(WINDOW, 1, "2026-11-21")],
                                [item(COMPLETE, 2, "2026-11-22")])["name"], COMPLETE)

    def test_expired_corrupt_or_foreign_artifacts_rejected(self):
        bad=item(WINDOW, 1, "2026-11-23"); bad["digest"]="invalid"
        self.assertIsNone(choose([item(WINDOW, 2, "2026-11-23", expired=True),
                                  bad, item("other", 3, "2026-11-23")], []))


if __name__ == "__main__":
    unittest.main()
