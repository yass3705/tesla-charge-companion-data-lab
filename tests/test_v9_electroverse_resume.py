import unittest
from scripts.select_v9_electroverse_checkpoint import (choose, WINDOW, COMPLETE, FAILURE, BRANCH,
    APPROVED_FAILURE_ID, APPROVED_FAILURE_RUN, APPROVED_FAILURE_HEAD, APPROVED_FAILURE_SHA)


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

    def test_pinned_failed_run_supersedes_old_success_without_replay(self):
        failed=item(FAILURE, APPROVED_FAILURE_ID, "2026-11-21T23:08:18Z")
        failed["digest"]="sha256:"+APPROVED_FAILURE_SHA
        failed["workflow_run"].update(id=APPROVED_FAILURE_RUN,head_sha=APPROVED_FAILURE_HEAD)
        chosen=choose([item(WINDOW,1,"2026-11-21T22:14:34Z")],[],[failed])
        self.assertEqual(chosen["id"], APPROVED_FAILURE_ID)

    def test_wrong_failure_digest_or_unknown_recent_run_fails_closed(self):
        failed=item(FAILURE, APPROVED_FAILURE_ID, "2026-11-21T23:08:18Z")
        failed["digest"]="sha256:"+"b"*64
        failed["workflow_run"].update(id=APPROVED_FAILURE_RUN,head_sha=APPROVED_FAILURE_HEAD)
        with self.assertRaisesRegex(ValueError,"unverified"):
            choose([item(WINDOW,1,"2026-11-21T22:14:34Z")],[],[failed])
        unknown=item(FAILURE, 99999999, "2026-11-22T01:00:00Z")
        with self.assertRaisesRegex(ValueError,"unverified"):
            choose([],[],[unknown])

    def test_future_successful_window_beats_older_reviewed_failure(self):
        failed=item(FAILURE, APPROVED_FAILURE_ID, "2026-11-21T23:08:18Z")
        failed["digest"]="sha256:"+APPROVED_FAILURE_SHA
        failed["workflow_run"].update(id=APPROVED_FAILURE_RUN,head_sha=APPROVED_FAILURE_HEAD)
        valid=item(WINDOW,1,"2026-11-22T02:00:00Z")
        self.assertEqual(choose([valid],[],[failed])["id"],1)


if __name__ == "__main__":
    unittest.main()
