import hashlib
import gzip
import json
import os
import tempfile
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.orchestrator import ROOT, read_sources, run_batch, run_source, run_isolated_process
from v9_rebuild.electroverse import IncompleteCollection, run as run_electroverse, validate_state as validate_electroverse
from tests.test_v9_electroverse import SimulatedCollector, fixture
from tests.test_v9_electroverse_status import fixture as status_fixture, part as status_part
from v9_rebuild.electroverse_status import cache_fingerprint, part_path, validate_partial


class OrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = read_sources()
        cls.sources = [source for source in registry if source["module"] == "operator_manifest"]
        cls.belgium = next(source for source in registry if source["id"] == "BE:nap")
        cls.electroverse_daily = next(source for source in registry if source["id"] == "FR:electroverse_daily")
        cls.electroverse_status = next(source for source in registry if source["id"] == "FR:electroverse_status")
        cls.output_names = {source["operator"]: source["output_file"] for source in cls.sources}
        cls.by_operator = {source["operator"]: source for source in cls.sources}

    def runner(self, command, **kwargs):
        operator = command[command.index("--operator") + 1]
        out = Path(command[command.index("--out") + 1])
        spec = self.by_operator[operator]
        manifest = json.loads((ROOT / spec["manifest"]).read_bytes())
        facts = manifest["facts"]
        fingerprint = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        evidence = [{"key": r["key"], "url": r["url"], "httpStatus": 200, "rawSha256": "a"*64} for r in manifest["sources"]]
        (out / self.output_names[operator]).write_text(json.dumps({
            "operator": spec["expected_operator"], "dataset": spec["expected_dataset"], "country": spec["expected_country"],
            "generatedAt": "2026-11-21T12:00:00Z", **facts, "sourceEvidence": {"officialOnly": True,
            "sources": evidence, "relevantTariffFingerprintSha256": fingerprint}}))
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

    def test_real_belgium_builder_finalizes_in_empty_isolated_workspace(self):
        code = """
import importlib.util, pathlib, sys
path=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(path.parent))
spec=importlib.util.spec_from_file_location('legacy_nap_fixture',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
payload={'locations':[{'idG':'fixture-location','energyInfrastructureStation':[
 {'idG':'fixture-station','refillPoint':[{'aegiElectricChargingPoint':{'idG':'fixture-evse'}}]}]}]}
m.fetch_page=lambda offset:(payload,{})
raise SystemExit(m.main())
"""
        def offline(command, **kwargs):
            return subprocess.run([sys.executable, '-c', code, str(ROOT / 'scripts/belgium_nap_full_country.py')],
                cwd=kwargs['cwd'], env=kwargs['env'], capture_output=True, text=True, check=False)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BELGIUM_NAP_TOKEN':'fixture-token'}):
            result=run_source(self.belgium, Path(tmp), attempts=1, runner=offline)
            self.assertEqual(result['status'],'ok')
            self.assertTrue(any(row['path']=='docs/belgium-cpo-progress-2026-09.json' for row in result['files']))

    def test_failed_belgium_keeps_pages_and_safe_diagnostic_outside_last_good(self):
        def failed(command, **kwargs):
            out = Path(kwargs["cwd"])
            raw = out / "artifacts/belgium-nap-raw-pages/page-000000.json.gz"
            raw.parent.mkdir(parents=True)
            raw.write_bytes(gzip.compress(b'{"locations": []}', mtime=0))
            return SimpleNamespace(returncode=1, stdout='{"page":0,"offset":0,"nextOffset":1000}',
                stderr='urllib.error.HTTPError: HTTP Error 429: confidential-provider-text')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"BELGIUM_NAP_TOKEN": "fixture-token"}):
            out = Path(tmp)
            good = run_source(self.belgium, out, attempts=1, runner=self.belgium_runner)
            before = (out / good["artifact"]).read_bytes()
            result = run_source(self.belgium, out, attempts=1, runner=failed)
            self.assertEqual(result["status"], "failed")
            self.assertEqual((out / good["artifact"]).read_bytes(), before)
            failure = out / "failures/BE_nap/attempt-1"
            report = json.loads((failure / "process.json").read_text())
            self.assertEqual(report["httpStatuses"], [429])
            self.assertNotIn("confidential", json.dumps(report))
            self.assertTrue((failure / "unvalidated-output/artifacts/belgium-nap-raw-pages/page-000000.json.gz").is_file())
            self.assertEqual(len(list((out / "objects/BE_nap").iterdir())), 1)

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

    def test_electroverse_failed_checkpoint_is_not_versioned_and_can_resume(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            source, out = Path(temp) / "source", Path(temp) / "artifacts"
            fixture(source, ["a", "b"])
            collector = SimulatedCollector(fail_once="b")

            def adapter(command, **kwargs):
                staged = Path(command[command.index("--out") + 1])
                try:
                    run_electroverse(staged, "daily", source=source, runner=collector)
                except IncompleteCollection:
                    return SimpleNamespace(returncode=1)
                return SimpleNamespace(returncode=0)

            failed = run_source(self.electroverse_daily, out, attempts=1, runner=adapter)
            self.assertEqual(failed["status"], "failed")
            checkpoint = out / "checkpoints/FR_electroverse_daily"
            self.assertTrue(checkpoint.is_dir())
            self.assertFalse(list((out / "objects/FR_electroverse_daily").glob("[0-9a-f]" * 64)))
            self.assertEqual(validate_electroverse(checkpoint, require_complete=False)["totalStations"], 1)

            resumed = run_source(self.electroverse_daily, out, attempts=1, runner=adapter)
            self.assertEqual(resumed["status"], "ok")
            self.assertFalse(checkpoint.exists())
            self.assertEqual(collector.selections, [["a", "b"], ["b"]])
            self.assertEqual(validate_electroverse((out / resumed["artifact"]).parents[3])["totalStations"], 2)

    def test_electroverse_next_run_seeds_from_validated_object(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            source, out = Path(temp) / "source", Path(temp) / "artifacts"
            fixture(source, ["a"])
            collector = SimulatedCollector()
            commands = []

            def adapter(command, **kwargs):
                commands.append(command)
                staged = Path(command[command.index("--out") + 1])
                resume = Path(command[command.index("--resume") + 1]) if "--resume" in command else None
                run_electroverse(staged, "daily", source=source, resume=resume, runner=collector)
                return SimpleNamespace(returncode=0)

            first = run_source(self.electroverse_daily, out, attempts=1, runner=adapter)
            self.assertEqual(first["status"], "ok")
            (out / "manifest.json").write_text(json.dumps({"sources": [first]}))
            second = run_source(self.electroverse_daily, out, attempts=1, runner=adapter)
            self.assertEqual(second["status"], "ok")
            self.assertNotIn("--resume", commands[0])
            self.assertIn("--resume", commands[1])
            self.assertEqual(validate_electroverse(source)["totalStations"], 0)
            state_root = (out / first["artifact"]).parents[3]
            shard = state_root / "data/electroverse/tariff_cache/shard-000.json"
            shard.write_text(shard.read_text() + " ")
            with self.assertRaises(ValueError):
                run_source(self.electroverse_daily, out, attempts=1, runner=adapter)

    def test_status_partial_checkpoint_survives_failed_runs_without_public_object(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            out = Path(temp) / "artifacts"
            calls = 0

            def partial(command, **kwargs):
                nonlocal calls
                calls += 1
                staged = Path(command[command.index("--out") + 1])
                if calls == 1:
                    status_fixture(staged, [])
                    from tests.test_v9_electroverse import save
                    save(part_path(staged, 0), status_part(0, cache_fingerprint(staged),
                                                           {"A": {"EVSE-A": "AVAILABLE"}}, expected=2))
                self.assertEqual(validate_partial(staged)["verified_locations"], 1)
                return SimpleNamespace(returncode=2)

            first = run_source(self.electroverse_status, out, attempts=1, runner=partial)
            second = run_source(self.electroverse_status, out, attempts=1, runner=partial)
            self.assertEqual((first["status"], second["status"]), ("failed", "failed"))
            self.assertEqual(calls, 2)
            self.assertEqual(validate_partial(out / "checkpoints/FR_electroverse_status")["verified_locations"], 1)
            self.assertFalse(list((out / "objects/FR_electroverse_status").glob("[0-9a-f]" * 64)))

    def test_timeout_retains_valid_status_checkpoint_and_resumes(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
            out = Path(temp) / "artifacts"
            calls = 0
            def interrupted(command, **kwargs):
                nonlocal calls
                calls += 1
                staged = Path(command[command.index("--out") + 1])
                if calls == 1:
                    status_fixture(staged, [])
                    from tests.test_v9_electroverse import save
                    save(part_path(staged, 0), status_part(0, cache_fingerprint(staged),
                         {"A": {"EVSE-A": "AVAILABLE"}}, expected=2))
                    raise subprocess.TimeoutExpired(command, 1)
                self.assertEqual(validate_partial(staged)["verified_locations"], 1)
                return SimpleNamespace(returncode=2)
            first = run_source(self.electroverse_status, out, attempts=1, runner=interrupted)
            self.assertEqual(first["reason"], "collector_timeout")
            self.assertEqual(validate_partial(out / "checkpoints/FR_electroverse_status")["verified_locations"], 1)
            second = run_source(self.electroverse_status, out, attempts=1, runner=interrupted)
            self.assertEqual(second["reason"], "collector_exit_nonzero")
            self.assertEqual(calls, 2)
            self.assertFalse(any(p.is_file() for p in (out / "objects").rglob("*")))

    def test_timeout_stops_descendant_before_checkpoint_inspection(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "writes.txt"
            child = ("import signal,time,pathlib; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                     f"p=pathlib.Path({str(marker)!r}); "
                     "exec(\"while True:\\n with p.open('a') as f: f.write('x')\\n time.sleep(.03)\")")
            parent = ("import subprocess,sys,time; "
                      f"subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
                      "time.sleep(60)")
            with self.assertRaises(subprocess.TimeoutExpired):
                run_isolated_process([sys.executable, "-c", parent], timeout=1, text=True)
            self.assertTrue(marker.exists())
            size = marker.stat().st_size
            time.sleep(.2)
            self.assertEqual(marker.stat().st_size, size)


if __name__ == "__main__":
    unittest.main()
