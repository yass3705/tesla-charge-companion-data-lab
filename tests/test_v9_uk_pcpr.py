"""Offline Allego UK and Source EV exact-connector PCPR handoff."""

from __future__ import annotations

import json
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild.orchestrator import read_sources, run_source
from v9_rebuild.uk_pcpr import paths, run, validate_output
from v9_rebuild.uk_blink import load_script
from v9_rebuild.electroverse import ROOT


def fixture(provider: str, *, empty=False, wrong=False) -> dict:
    if empty:
        return {"locations": [], "tariffs": []}
    source_ev = provider == "source_ev"
    party = "SGB" if source_ev else "ABC"
    tariff_id = "GB*SGB_02" if source_ev else "T1"
    loc = {
        "id": "L1", "country_code": "GB", "country": "GBR", "party_id": party,
        "operator": {"name": "ChargePoint" if wrong else "Source EV" if source_ev else "Allego UK"},
        "publish": True, "coordinates": {"latitude": "51.5", "longitude": "-0.1"},
        "evses": [{"uid": "1", "evse_id": f"GB*{party}*E1", "status": "AVAILABLE",
                   "connectors": [{"id": "1", "standard": "IEC_62196_T2", "max_electric_power": 22000,
                                   "tariff_ids": [tariff_id]}]}],
    }
    tariff = {"id": tariff_id, "country_code": "GB", "party_id": party, "currency": "GBP",
              "elements": [{"price_components": [{"type": "ENERGY", "price": 0.7416667 if source_ev else 0.5,
                                                  "vat": 0.2 if source_ev else 20, "step_size": 1}]}]}
    return {"locations": [loc], "tariffs": [tariff]}


class UKPCPRMigrationTests(unittest.TestCase):
    def fixture_file(self, root: Path, provider: str, **kwargs) -> Path:
        path = root / "fixture.json"
        path.write_text(json.dumps(fixture(provider, **kwargs)), encoding="utf-8")
        return path

    def test_two_historical_methods_and_orchestrator(self):
        for provider, secret in (("allego_uk", "ALLEGO_UK_PCPR_TOKEN"), ("source_ev", "SOURCE_EV_PCPR_TOKEN")):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {secret: "offline-fixture"}):
                root = Path(temp)
                source = self.fixture_file(root, provider)
                run(root / "source", provider, fixture=source)
                doc = validate_output(root / "source", provider)
                self.assertEqual(len(doc["sources"][0]["tariffs"]), 1)
                spec = next(row for row in read_sources() if row["id"] == f"GB:{provider}_pcpr")
                def outer(command, **kwargs):
                    run(Path(command[command.index("--out") + 1]), provider, fixture=source)
                    return SimpleNamespace(returncode=0)
                artifact = run_source(spec, root / "artifacts", runner=outer)
                self.assertEqual(artifact["status"], "ok")
                self.assertEqual(len(artifact["files"]), 4)

    def test_changed_price_keeps_station_and_raw_offer_through_historical_audit(self):
        import gzip
        import hashlib
        from v9_rebuild.canonical_uk_pcpr import normalize_uk_pcpr
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"SOURCE_EV_PCPR_TOKEN": "offline-fixture"}):
            root = Path(temp)
            payload = fixture("source_ev")
            payload["tariffs"][0]["elements"][0]["price_components"][0].update(price=0.5, vat=20)
            path = root / "fixture.json"
            path.write_text(json.dumps(payload))
            run(root / "out", "source_ev", fixture=path)
            doc = validate_output(root / "out", "source_ev")
            staged = root / "out" / paths("source_ev")[1]
            canonical = normalize_uk_pcpr(doc, artifact_sha256=hashlib.sha256(staged.read_bytes()).hexdigest(),
                                         source_id="GB:source_ev_pcpr_direct")
            self.assertEqual(len(canonical["stations"]), 1)
            self.assertEqual(len(canonical["connectors"]), 1)
            self.assertEqual(len(canonical["offers"]), 1)
            self.assertEqual(canonical["offers"][0]["rawOffer"], payload["tariffs"][0])
            self.assertEqual(canonical["offers"][0]["calculationHold"], "historical_payg_evidence_mismatch")
            self.assertEqual(canonical["tariffCatalog"], {})
            self.assertEqual(len(canonical["unresolvedTariffRefs"]), 1)

    def test_failed_audit_preserves_raw_outside_objects_and_last_good(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"SOURCE_EV_PCPR_TOKEN": "offline-fixture"}):
            root = Path(temp)
            spec = next(row for row in read_sources() if row["id"] == "GB:source_ev_pcpr")
            def outer(command, **kwargs):
                out = Path(command[command.index("--out") + 1])
                raw = out / paths("source_ev")[0]
                raw.parent.mkdir(parents=True, exist_ok=True)
                raw.write_bytes(b"quarantined-invalid-gzip")
                (out / "private.log").write_text("not an allowed diagnostic")
                return SimpleNamespace(returncode=1, stdout="", stderr="AssertionError: fixture")
            result = run_source(spec, root / "artifacts", runner=outer, attempts=1)
            failure = root / "artifacts/failures/GB_source_ev_pcpr/attempt-1/unvalidated-output"
            self.assertEqual((failure / paths("source_ev")[0]).read_bytes(), b"quarantined-invalid-gzip")
            self.assertFalse((failure / "private.log").exists())
            self.assertIsNone(result.get("artifact"))
            self.assertEqual(list((root / "artifacts/objects/GB_source_ev_pcpr").iterdir()), [])
            self.assertFalse((root / "artifacts/checkpoints/GB_source_ev_pcpr").exists())

    def test_empty_and_wrong_operator_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"ALLEGO_UK_PCPR_TOKEN": "offline-fixture"}):
            root = Path(temp)
            run(root / "empty", "allego_uk", fixture=self.fixture_file(root, "allego_uk", empty=True))
            audit = json.loads((root / "empty" / paths("allego_uk")[3]).read_text())
            self.assertFalse(audit["validatedForV9"])
            self.assertEqual(audit["status"], "no_exact_tariff_available")
            with self.assertRaisesRegex(RuntimeError, "different CPO"):
                run(root / "wrong", "allego_uk", fixture=self.fixture_file(root, "allego_uk", wrong=True))

    def test_preserved_page_boundary_and_budget(self):
        module = load_script(ROOT / "scripts/uk_pcpr_cpo_collect.py", "v9_uk_pcpr_pagination_test")
        pages = [io.BytesIO(json.dumps({"status_code": 1000, "data": [{}] * 1000}).encode()),
                 io.BytesIO(json.dumps({"status_code": 1000, "data": [{"id": "last"}]}).encode())]
        budget = [0]
        with patch.object(module.urllib.request, "urlopen", side_effect=pages) as fetch, patch.object(module.time, "sleep"):
            rows = module.collect("locations", "Token offline", budget)
        self.assertEqual(len(rows), 1001)
        self.assertEqual(budget[0], 2)
        self.assertIn("offset=1000", fetch.call_args_list[1].args[0].full_url)
        with self.assertRaisesRegex(RuntimeError, "request budget reached"):
            module.collect("locations", "Token offline", [28])


if __name__ == "__main__":
    unittest.main()
