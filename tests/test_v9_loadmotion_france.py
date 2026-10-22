import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from v9_rebuild.loadmotion_france import CURRENT, OUTPUT, TENANTS, run, validate_output
from v9_rebuild.orchestrator import read_sources, run_source

ROOT = Path(__file__).resolve().parents[1]
PRELOAD = '''import fs from 'node:fs';
const fixture=JSON.parse(fs.readFileSync(process.env.LOADMOTION_FIXTURE,'utf8'));
const token='a.'+Buffer.from(JSON.stringify({id:'fixture-user'})).toString('base64url')+'.c';
globalThis.fetch=async (url,options={})=>{
 const u=new URL(url);const tenant=Object.entries({yes55:'yes55',loadstations:'loadstations',reveo:'reveocharge',mobisdec:'mobisdec'}).find(([k,v])=>u.hostname.includes(v))?.[0];
 if(!tenant)throw new Error('unknown fixture host '+u.hostname);
 let body;
 if(u.pathname.endsWith('/auth/signin'))body={token};
 else if(u.pathname.endsWith('/charging-stations'))body={result:[{id:fixture[tenant].station,connectors:[{connectorId:fixture[tenant].connector}],site:{name:fixture[tenant].site}}]};
 else if(u.pathname.endsWith('/matching-pricing-definitions/resolve'))body={pricingDefinitions:fixture[tenant].definitions};
 else throw new Error('unknown fixture path '+u.pathname);
 return {ok:true,status:200,text:async()=>JSON.stringify(body)};
};
'''


class LoadMotionFranceTest(unittest.TestCase):
    def fixture(self, root):
        data = {}
        for tenant in TENANTS:
            with gzip.open(ROOT / CURRENT / f"{tenant}.json.gz", "rt") as handle:
                row = json.load(handle)["tarifs"][0]
            data[tenant] = {"station": row["station"], "connector": row["connector"], "site": row.get("site"), "definitions": row["definitions"]}
        path = root / "fixture.json"
        path.write_text(json.dumps(data))
        preload = root / "preload.mjs"
        preload.write_text(PRELOAD)
        return path, preload

    def test_four_historical_collectors_and_compiler_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture, preload = self.fixture(root)
            out = root / "out"
            out.mkdir()
            secrets = {"LOADMOTION_ID": "fixture", "YES55_PASS": "fixture", "LOADSTATIONS_PASS": "fixture", "REVEO_PASS": "fixture", "MOBISDEC_PASS": "fixture", "LOADMOTION_FIXTURE": str(fixture)}
            with patch.dict(os.environ, secrets):
                run(out, fixture_preload=preload)
            offers = validate_output(out)
            self.assertEqual({row["metadata"]["tenant"] for row in offers["directOffers"]}, set(TENANTS))
            self.assertEqual(len([path for path in (out / CURRENT).glob("*.json.gz")]), 4)
            payload = json.loads((out / OUTPUT).read_text())
            payload["directOffers"][0]["evseIds"] = ["wrong-id"]
            (out / OUTPUT).write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "EVSE offer scope"):
                validate_output(out)

    def test_missing_credentials_prevents_partial_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture, preload = self.fixture(root)
            out = root / "out"
            out.mkdir()
            with patch.dict(os.environ, {"LOADMOTION_ID": "", "YES55_PASS": "", "LOADMOTION_FIXTURE": str(fixture)}):
                with self.assertRaisesRegex(RuntimeError, "tenant failed"):
                    run(out, fixture_preload=preload)
            self.assertFalse((out / OUTPUT).exists())

    def test_orchestrator_and_unknown_component(self):
        spec = next(row for row in read_sources() if row["id"] == "FR:loadmotion")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture, preload = self.fixture(root)
            secrets = {"LOADMOTION_ID": "fixture", "YES55_PASS": "fixture", "LOADSTATIONS_PASS": "fixture", "REVEO_PASS": "fixture", "MOBISDEC_PASS": "fixture", "LOADMOTION_FIXTURE": str(fixture)}
            def adapter_runner(command, **kwargs):
                out = Path(command[command.index("--out") + 1])
                run(out, fixture_preload=preload)
                return SimpleNamespace(returncode=0)
            with patch.dict(os.environ, secrets):
                self.assertEqual(run_source(spec, root / "artifacts", attempts=1, runner=adapter_runner)["status"], "ok")
            artifact = root / "plain"
            artifact.mkdir()
            with patch.dict(os.environ, secrets):
                run(artifact, fixture_preload=preload)
            target = artifact / CURRENT / "yes55.json.gz"
            with gzip.open(target, "rt") as handle:
                payload = json.load(handle)
            payload["tarifs"][0]["definitions"][0]["dimensions"]["undocumentedFee"] = {"active": True, "price": 1}
            with gzip.open(target, "wt") as handle:
                json.dump(payload, handle)
            with self.assertRaisesRegex(ValueError, "unsupported active component"):
                validate_output(artifact)


if __name__ == "__main__":
    unittest.main()
