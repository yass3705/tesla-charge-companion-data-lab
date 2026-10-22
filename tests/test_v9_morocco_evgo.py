import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from v9_rebuild.morocco_evgo import HYDRATION, OUTPUT, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / HYDRATION


def reduced_fixture(path):
    source = json.loads(ARCHIVE.read_text())
    for entry in source["versions"].values():
        item = entry["locations"][0]
        lid = item["id"]
        entry["locations"] = [item]
        entry["location_ids"] = [lid]
        entry["pins"] = [pin for pin in entry["pins"] if lid in (pin.get("underlyingLocationIds") or [])]
        entry["pin_count"] = len(entry["pins"])
    path.write_text(json.dumps(source))


class MoroccoEvgoTest(unittest.TestCase):
    def test_reduced_archived_fixture_runs_without_volume_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "hydration.json"
            reduced_fixture(fixture)
            out = root / "out"
            out.mkdir()
            run(out, fixture)
            result = validate_output(out)
            self.assertEqual(result["summary"]["station_count"], 1)
            self.assertEqual(result["source_api_version"], "v2")
            data = json.loads((out / OUTPUT).read_text())
            data["stations"][0]["tariff_channel"] = "Electroverse"
            (out / OUTPUT).write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "metadata mutated"):
                validate_output(out)

    def test_incomplete_hydration_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "hydration.json"
            reduced_fixture(fixture)
            data = json.loads(fixture.read_text())
            for entry in data["versions"].values():
                entry["locations"][0]["status"] = 503
            fixture.write_text(json.dumps(data))
            out = root / "out"
            out.mkdir()
            with self.assertRaisesRegex(RuntimeError, "status_overlay"):
                run(out, fixture)
            self.assertFalse((out / OUTPUT).exists())

    def test_preserved_probe_paginates_all_declared_locations(self):
        script = ROOT / "scripts/morocco_evgo_pin_hydration_probe.py"
        spec = importlib.util.spec_from_file_location("fixture_evgo_probe", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for count in (0, 1):
            pins = [{"id": 1, "underlyingLocationIds": [42], "geo": "33,-7"}] if count else []
            def request(path):
                if path.endswith("/pins"):
                    return 200, "application/json", {"pins": pins}
                return 200, "application/json", {"id": 42, "name": "EVGO", "zones": []}
            module.req_json = request
            with tempfile.TemporaryDirectory() as tmp:
                module.OUT = Path(tmp)
                module.main()
                result = json.loads((module.OUT / "summary.json").read_text())
                self.assertEqual(len(result["versions"]["v1"]["location_ids"]), count)
        module.req_json = lambda path: (200, "application/json", {"pins": [{"id": x, "underlyingLocationIds": [x]} for x in range(101)]})
        with self.assertRaisesRegex(ValueError, "bound"):
            module.main()

    def test_orchestrator_uses_isolated_technical_artifact(self):
        source = next(row for row in read_sources() if row["id"] == "MA:evgo")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "hydration.json"
            reduced_fixture(fixture)
            def runner(command, **kwargs):
                out = Path(command[command.index("--out") + 1])
                run(out, fixture)
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(source, root / "artifacts", attempts=1, runner=runner)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
