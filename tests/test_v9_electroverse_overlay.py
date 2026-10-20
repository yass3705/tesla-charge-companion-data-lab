"""Offline overlay gate tests; no Electroverse endpoint is contacted."""

import gzip
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_v9_electroverse_status import fixture, part
from tests.test_v9_electroverse import save
from v9_rebuild.electroverse_overlay import OUT, REPORT, run, validate_output
from v9_rebuild.electroverse import CACHE, MAPPING, ROOT, shard_index, stage_state
from v9_rebuild.electroverse_status import cache_fingerprint, part_path, validate_complete
from v9_rebuild.orchestrator import artifact_digest, sha256, validated_dependency


class ElectroverseOverlayTests(unittest.TestCase):
    def test_dependency_manifest_sha_source_and_completeness(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "bundle"
            state = bundle / "objects/FR_electroverse_daily/immutable"
            fixture(state, [])
            artifact = state / CACHE / "manifest.json"
            digest, files = artifact_digest(state)
            row = {"source": "FR:electroverse_daily", "module": "electroverse", "status": "ok",
                   "artifact": artifact.relative_to(bundle).as_posix(), "sha256": sha256(artifact),
                   "artifact_set_sha256": digest, "files": files}
            save(bundle / "manifest.json", {"schema_version": 1, "status": "complete", "sources": [row]})
            self.assertEqual(validated_dependency(bundle, "FR:electroverse_daily", "electroverse"), state)
            station_file = state / CACHE / "shard-000.json"
            station_file.write_bytes(station_file.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "integrity mismatch|Shard manifest mismatch"):
                validated_dependency(bundle, "FR:electroverse_daily", "electroverse")
            station_file.write_bytes(station_file.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError, "Missing validated dependency"):
                validated_dependency(bundle, "FR:electroverse_full", "electroverse")
            row["sha256"] = "0" * 64
            save(bundle / "manifest.json", {"schema_version": 1, "status": "complete", "sources": [row]})
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                validated_dependency(bundle, "FR:electroverse_daily", "electroverse")
            save(bundle / "manifest.json", {"schema_version": 1, "status": "partial_failure", "sources": [row]})
            with self.assertRaisesRegex(ValueError, "incomplete"):
                validated_dependency(bundle, "FR:electroverse_daily", "electroverse")

    def test_historical_builder_and_postbuild_audit_on_one_source_station(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source, status, out = base / "source", base / "status", base / "out"
            fixture(source, [])
            pk = "424930"  # Existing archived FR mapping and tariff-cache row.
            original_manifest = json.loads((ROOT / CACHE / "manifest.json").read_text())
            index = shard_index(pk)
            original_shard = json.loads((ROOT / CACHE / original_manifest["shards"][index]["file"]).read_text())
            shard_path = source / CACHE / f"shard-{index:03d}.json"
            shard = json.loads(shard_path.read_text())
            shard["stations"][pk] = original_shard["stations"][pk]
            save(shard_path, shard)
            manifest = json.loads((source / CACHE / "manifest.json").read_text())
            manifest["shards"][index]["count"] = 1
            manifest["shards"][index]["sizeBytes"] = shard_path.stat().st_size
            manifest["totalStations"] = 1
            save(source / CACHE / "manifest.json", manifest)
            original_mapping = json.loads((ROOT / MAPPING).read_text())
            save(source / MAPPING, {"mappings": [row for row in original_mapping["mappings"] if str(row.get("electroverseLocationPk")) == pk]})
            stage_state(source, status)
            fingerprint = cache_fingerprint(status)
            statuses = {str(evse["pk"]): "AVAILABLE" for evse in original_shard["stations"][pk]["tariff"]["evses"]}
            for partition in range(16):
                save(part_path(status, partition), part(partition, fingerprint, {pk: statuses} if partition == 0 else {}))
            with patch.dict(os.environ, {"ELECTROVERSE_API_KEY": "fixture-only"}):
                completed = subprocess.run(["node", str(ROOT / "scripts/electroverse_status_incremental.mjs"), "finalize"],
                                           cwd=status, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(validate_complete(status)["completedLocations"], 1)
            run(out, source=source, status_source=status)
            built = validate_output(out)
            self.assertGreater(sum(tile["count"] for tile in built["tiles"]), 0)
            self.assertFalse((source / OUT).exists())
            failed = base / "failed"
            def fail_build(command, **kwargs):
                return SimpleNamespace(returncode=2)
            with self.assertRaisesRegex(RuntimeError, "script failed"):
                run(failed, source=source, status_source=status, runner=fail_build)
            self.assertFalse((failed / OUT / "manifest.json").exists())
            run(failed, source=source, status_source=status)
            self.assertGreater(sum(tile["count"] for tile in validate_output(failed)["tiles"]), 0)
            corrupt = base / "corrupt"
            def corrupt_audit(command, **kwargs):
                result = subprocess.run(command, **kwargs)
                if Path(command[1]).name == "audit_electroverse_status_gate_postbuild.mjs":
                    report = json.loads((corrupt / REPORT).read_text())
                    report["invalidPublishedSourceRefs"] = 1
                    save(corrupt / REPORT, report)
                return result
            with self.assertRaisesRegex(ValueError, "status gate"):
                run(corrupt, source=source, status_source=status, runner=corrupt_audit)
            altered = json.loads((source / CACHE / "manifest.json").read_text())
            altered["generatedAt"] = "2026-10-01T00:00:00Z"
            save(source / CACHE / "manifest.json", altered)
            with self.assertRaisesRegex(ValueError, "different provenance"):
                run(base / "wrong-cache", source=source, status_source=status)

    def test_rejects_partial_status_before_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source, status, out = base / "source", base / "status", base / "out"
            fixture(source, [])
            fixture(status, [])
            with self.assertRaises(Exception):
                run(out, source=source, status_source=status)
            self.assertFalse(out.exists())

    def test_tile_and_audit_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            tile = OUT / "t_0_0.json.gz"
            (out / tile).parent.mkdir(parents=True)
            with gzip.open(out / tile, "wt", encoding="utf-8") as handle:
                json.dump({"emspOffers": [{"id": "exact-evse", "evseIds": ["FR*ABC*E1"]}]}, handle)
            data = (out / tile).read_bytes()
            manifest = {"country": "FR", "dataset": "electroverse-france-evse-national-overlay", "tileCount": 1,
                        "tiles": [{"file": tile.name, "count": 1, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}]}
            save(out / OUT / "manifest.json", manifest)
            save(out / REPORT, {"offers": 1, "invalidPublishedSourceRefs": 0,
                                  "missingProvenanceOffers": 0, "statusPkConflicts": 0})
            self.assertEqual(validate_output(out), manifest)
            (out / tile).write_bytes(data + b"corruption")
            with self.assertRaisesRegex(ValueError, "integrity"):
                validate_output(out)


if __name__ == "__main__":
    unittest.main()
