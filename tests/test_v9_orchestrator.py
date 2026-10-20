import gzip
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.orchestrator import ROOT, read_sources, run_batch, run_source


class OrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = read_sources()
        cls.sources = [source for source in registry if source["module"] == "operator_manifest"]
        cls.belgium = next(source for source in registry if source["id"] == "BE:nap")
        cls.output_names = {source["operator"]: source["output_file"] for source in cls.sources}
        cls.by_operator = {source["operator"]: source for source in cls.sources}

    def runner(self, command, **kwargs):
        operator = command[command.index("--operator") + 1]
        out = Path(command[command.index("--out") + 1])
        spec = self.by_operator[operator]
        (out / self.output_names[operator]).write_text(json.dumps({"operator": spec["expected_operator"], "dataset": spec["expected_dataset"], "country": spec["expected_country"], "sourceEvidence": {"officialOnly": True}}))
        return SimpleNamespace(returncode=0)

    def test_registry_and_independent_concurrent_outputs(self):
        self.assertEqual(len(self.sources), 10)
        with tempfile.TemporaryDirectory() as tmp:
            result = run_batch(self.sources[:2], Path(tmp), workers=2, runner=self.runner)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(len({row["artifact"] for row in result["sources"]}), 2)
            for row in result["sources"]:
                self.assertEqual(json.loads((Path(tmp) / row["artifact"]).read_text())["operator"], self.by_operator[row["source"].split(":", 1)[1]]["expected_operator"])
            self.assertTrue((Path(tmp) / "manifest.json").is_file())

    def test_retry_after_failure(self):
        calls = 0

        def flaky(command, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return SimpleNamespace(returncode=1)
            return self.runner(command, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            result = run_source(self.sources[0], Path(tmp), attempts=2, runner=flaky)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["attempts"], 2)

    def test_source_failure_does_not_corrupt_other_artifact(self):
        failed_operator = self.sources[0]["operator"]

        def selective(command, **kwargs):
            if command[command.index("--operator") + 1] == failed_operator:
                return SimpleNamespace(returncode=1)
            return self.runner(command, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            result = run_batch(self.sources[:2], Path(tmp), workers=2, runner=selective)
            self.assertEqual(result["status"], "partial_failure")
            self.assertEqual([row["status"] for row in result["sources"]], ["failed", "ok"])
            self.assertTrue((Path(tmp) / result["sources"][1]["artifact"]).is_file())

    def test_unexpected_collector_exception_is_isolated(self):
        failed_operator = self.sources[0]["operator"]

        def exceptional(command, **kwargs):
            if command[command.index("--operator") + 1] == failed_operator:
                raise RuntimeError("synthetic collector exception")
            return self.runner(command, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            result = run_batch(self.sources[:2], Path(tmp), workers=2, runner=exceptional)
            self.assertEqual(result["status"], "partial_failure")
            self.assertEqual([row["status"] for row in result["sources"]], ["failed", "ok"])
            self.assertEqual(result["sources"][0]["reason"], "collector_exception")

    def test_two_batches_share_content_addressed_output_without_corruption(self):
        with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_batch, self.sources[:1], Path(tmp), workers=1, runner=self.runner) for _ in range(2)]
            results = [future.result() for future in futures]
            self.assertTrue(all(result["status"] == "complete" for result in results))
            self.assertEqual(results[0]["sources"][0]["sha256"], results[1]["sources"][0]["sha256"])
            self.assertEqual(json.loads((Path(tmp) / "manifest.json").read_text())["status"], "complete")

    def test_required_secret_is_checked_by_name_only(self):
        spec = {**self.sources[0], "secret_names": ["TCC_G2_TEST_SECRET"]}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"TCC_G2_TEST_SECRET": ""}):
            result = run_source(spec, Path(tmp), runner=self.runner)
            self.assertEqual(result["reason"], "missing_required_secret")
            self.assertNotIn("value", json.dumps(result))

    def test_output_must_be_readable_json(self):
        def bad_json(command, **kwargs):
            operator = command[command.index("--operator") + 1]
            out = Path(command[command.index("--out") + 1])
            (out / self.output_names[operator]).write_text("{invalid")
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as tmp:
            result = run_source(self.sources[0], Path(tmp), attempts=1, runner=bad_json)
            self.assertEqual(result["reason"], "collector_output_invalid_json")

    def test_output_identity_must_match_existing_manifest(self):
        def wrong_source(command, **kwargs):
            operator = command[command.index("--operator") + 1]
            out = Path(command[command.index("--out") + 1])
            (out / self.output_names[operator]).write_text(json.dumps({"operator": "wrong", "dataset": "wrong", "country": "FR", "sourceEvidence": {"officialOnly": True}}))
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as tmp:
            result = run_source(self.sources[0], Path(tmp), attempts=1, runner=wrong_source)
            self.assertEqual(result["reason"], "collector_output_contract_mismatch")

    def test_checkout_cannot_be_artifact_directory(self):
        with self.assertRaises(ValueError):
            run_batch(self.sources[:1], ROOT / "data" / "forbidden", runner=self.runner)

    def belgium_runner(self, command, **kwargs):
        out = Path(kwargs["cwd"])
        pages_dir = out / "data/belgium/pages"
        pages_dir.mkdir(parents=True)
        pages = []
        for offset, following in ((0, 1000), (1000, None)):
            path = pages_dir / f"nap-belgium-{offset:06d}.json.gz"
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                json.dump({"locations": []}, handle)
            pages.append({"offset": offset, "nextOffset": following, "canonicalPath": str(path.relative_to(out))})
        manifest_path = out / "data/belgium/nap-belgium-manifest.json"
        manifest_path.write_text(json.dumps({"country": "BE", "pageCount": 2, "pages": pages}))
        report = out / "reports/belgium-national-full-extraction-2026-09-28.json"
        report.parent.mkdir(parents=True)
        report.write_text(json.dumps({"integrity": {"paginationEndedNormally": True}, "pagination": {"pageCount": 2}}))
        return SimpleNamespace(returncode=0)

    def test_existing_belgium_pagination_contract(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"BELGIUM_NAP_TOKEN": "fixture-token"}):
            result = run_source(self.belgium, Path(tmp), attempts=1, runner=self.belgium_runner)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(len([row for row in result["files"] if row["path"].endswith(".json.gz")]), 2)

    def test_incomplete_belgium_pagination_fails(self):
        def incomplete(command, **kwargs):
            result = self.belgium_runner(command, **kwargs)
            path = Path(kwargs["cwd"]) / "data/belgium/nap-belgium-manifest.json"
            payload = json.loads(path.read_text())
            payload["pages"][-1]["nextOffset"] = 2000
            path.write_text(json.dumps(payload))
            return result

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"BELGIUM_NAP_TOKEN": "fixture-token"}):
            result = run_source(self.belgium, Path(tmp), attempts=1, runner=incomplete)
            self.assertEqual(result["reason"], "collector_output_contract_mismatch")


if __name__ == "__main__":
    unittest.main()
