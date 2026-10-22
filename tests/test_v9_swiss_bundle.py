import gzip
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from v9_rebuild.swiss_bundle import NATIONAL, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_batch, run_source
from v9_rebuild.swiss_integration import run as run_integration, validate_output as validate_integration


def write_input(source, evses):
    national = {"Operators": [{"OperatorID": "CH*ABC", "OperatorName": "Example", "ChargingStations": [{"ChargingStationId": "S1", "Evses": [{"EvseID": eid, "ChargingStationId": "S1", "Accessibility": "Free publicly accessible"} for eid in evses]}]}]}
    target = source / NATIONAL
    target.parent.mkdir(parents=True)
    target.write_bytes(gzip.compress(json.dumps(national).encode(), mtime=0))
    manifest = {"schemaVersion": 1, "source": "CH:swiss_bundle_inputs", "branch": "rebuild/v9-20261020", "fixtureMode": True, "files": {str(NATIONAL): hashlib.sha256(target.read_bytes()).hexdigest()}}
    (source / "input-manifest.json").write_text(json.dumps(manifest))


class SwissBundleTest(unittest.TestCase):
    def test_constructor_and_reduced_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, out = root / "source", root / "out"
            source.mkdir()
            out.mkdir()
            write_input(source, ["CH*ABC*E1"])
            run(out, source)
            report = validate_output(out)
            self.assertEqual(report["counts"]["nationalEvseCount"], 1)
            bundle = json.loads((out / "data/tcc_v9/switzerland.json").read_text())
            self.assertEqual(bundle["evses"][0]["evseId"], "CH*ABC*E1")
            self.assertEqual(bundle["evses"][0]["directTariffStatus"], "unresolved")

    def test_bad_sha_and_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, out = root / "source", root / "out"
            source.mkdir()
            out.mkdir()
            write_input(source, [])
            manifest_path = source / "input-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][str(NATIONAL)] = "0" * 64
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                run(out, source)
            manifest["branch"] = "main"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "branch invalid"):
                run(out, source)

    def test_empty_inventory_is_technical_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, out = root / "source", root / "out"
            source.mkdir()
            out.mkdir()
            write_input(source, [])
            run(out, source)
            self.assertEqual(validate_output(out)["counts"]["nationalEvseCount"], 0)

    def test_production_input_set_must_be_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, out = root / "source", root / "out"
            source.mkdir()
            out.mkdir()
            write_input(source, ["CH*ABC*E1"])
            manifest_path = source / "input-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest.pop("fixtureMode")
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "production inputs incomplete"):
                run(out, source)

    def test_orchestrator_uses_only_verified_input(self):
        spec = next(item for item in read_sources() if item["id"] == "CH:swiss_bundle")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input_dependencies/CH_swiss_bundle_inputs"
            source.mkdir(parents=True)
            write_input(source, ["CH*ABC*E1"])
            self.assertEqual(run_source(spec, root, attempts=1)["status"], "ok")
            manifest_path = source / "input-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][str(NATIONAL)] = "0" * 64
            manifest_path.write_text(json.dumps(manifest))
            self.assertEqual(run_source(spec, root, attempts=1)["reason"], "validated_dependency_invalid")

    def test_public_integration_preserves_exact_evse_and_excludes_restricted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, bundle, out = root / "source", root / "bundle", root / "public"
            for path in (source, bundle, out):
                path.mkdir()
            write_input(source, ["CH*ABC*E1", "CH*ABC*E2"])
            national_path = source / NATIONAL
            national = json.loads(gzip.decompress(national_path.read_bytes()))
            national["Operators"][0]["ChargingStations"][0]["Evses"][1]["Accessibility"] = "Restricted access"
            national_path.write_bytes(gzip.compress(json.dumps(national).encode(), mtime=0))
            manifest_path = source / "input-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][str(NATIONAL)] = hashlib.sha256(national_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            run(bundle, source)
            run_integration(out, bundle)
            self.assertEqual(validate_integration(out)["summary"]["nationalEvseCount"], 1)
            public = json.loads((out / "data/national/switzerland_public_charging_v9.json").read_text())
            self.assertEqual(public["evses"][0]["evseId"], "CH*ABC*E1")
            self.assertEqual(public["evses"][0]["directTariff"]["status"], "unresolved")

    def test_integration_requires_signed_bundle_artifact(self):
        sources = read_sources()
        bundle_spec = next(item for item in sources if item["id"] == "CH:swiss_bundle")
        integration_spec = next(item for item in sources if item["id"] == "CH:swiss_integration")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle_root, public_root = root / "bundle", root / "public"
            fixture = bundle_root / "input_dependencies/CH_swiss_bundle_inputs"
            fixture.mkdir(parents=True)
            write_input(fixture, ["CH*ABC*E1"])
            self.assertEqual(run_batch([bundle_spec], bundle_root, workers=1)["status"], "complete")
            self.assertEqual(run_source(integration_spec, public_root, attempts=1)["reason"], "validated_dependency_missing")
            dependency = public_root / "input_dependencies/CH_swiss_bundle"
            shutil.copytree(bundle_root, dependency)
            self.assertEqual(run_source(integration_spec, public_root, attempts=1)["status"], "ok")
            manifest = json.loads((dependency / "manifest.json").read_text())
            artifact = dependency / manifest["sources"][0]["artifact"]
            artifact.write_text("{}")
            self.assertEqual(run_source(integration_spec, public_root, attempts=1)["reason"], "validated_dependency_invalid")


if __name__ == "__main__":
    unittest.main()
