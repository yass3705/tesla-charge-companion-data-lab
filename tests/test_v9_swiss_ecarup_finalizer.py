"""Offline signed Swiss eCarUp finalization and restricted-price accounting."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from v9_rebuild.orchestrator import artifact_digest, read_sources, run_source, sha256
from v9_rebuild.swiss_ecarup_finalizer import COORDINATE, EXACT, REPORT, run, validate_output


def signed_coordinate_bundle(base: Path) -> tuple[Path, Path]:
    stage = base / 'stage'
    for relative in (COORDINATE, EXACT, Path('docs/switzerland-ecarup-owner-coordinate-safe-overlay-2026-09-28.json')):
        (stage / relative).parent.mkdir(parents=True, exist_ok=True)
    exact = {'schemaVersion':1,'country':'CH','operatorId':'CH*ECU',
             'counts':{'nationalEvseCount':3,'pricedEvseCount':1,'classifiedNoPublicDirectTariffCount':1,'unresolvedEvseCount':1},
             'evses':[{'evseId':'CH*ECU*E1','classification':'priced_public_direct'},
                      {'evseId':'CH*ECU*E2','classification':'restricted_no_public_direct_tariff'}],
             'unresolved':[{'evseId':'CH*ECU*E3'}]}
    (stage / EXACT).write_text(json.dumps(exact))
    coordinate = {'schemaVersion':1,'country':'CH','operatorId':'CH*ECU','nationalEvseCount':3,
                  'alreadyExactPricedCount':2,'safeCoordinateOverlayCount':0,'ambiguousCount':0,
                  'noCandidateCount':1,'evses':[],'ambiguous':[],
                  'noCandidate':[{'evseId':'CH*ECU*E3','reason':'no_station_within_3m'}]}
    (stage / COORDINATE).write_text(json.dumps(coordinate))
    report = {key:value for key,value in coordinate.items()
              if key not in ('evses','ambiguous','noCandidate')}
    (stage / 'docs/switzerland-ecarup-owner-coordinate-safe-overlay-2026-09-28.json').write_text(json.dumps(report))
    digest, files = artifact_digest(stage)
    bundle = base / 'bundle'
    state = bundle / 'objects/CH_ecarup_coordinate' / digest
    state.parent.mkdir(parents=True)
    shutil.copytree(stage, state)
    artifact = state / COORDINATE
    (bundle / 'manifest.json').write_text(json.dumps({'schema_version':1,'status':'complete',
        'sources':[{'source':'CH:ecarup_coordinate','module':'cwd_script','status':'ok',
                    'artifact':str(artifact.relative_to(bundle)),'sha256':sha256(artifact),
                    'artifact_set_sha256':digest,'files':files}]}))
    return bundle, state


class SwissEcarupFinalizerTests(unittest.TestCase):
    def test_restricted_evse_is_not_priced_and_orchestration(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle, state = signed_coordinate_bundle(base)
            run(base / 'direct', state)
            report = validate_output(base / 'direct')
            self.assertEqual(report['exactConnectorPricedCount'], 1)
            self.assertEqual(report['exactRestrictedCount'], 1)
            self.assertEqual(report['pricedEvseCount'], 1)
            self.assertEqual(report['unresolvedEvseCount'], 1)
            spec = next(row for row in read_sources() if row['id'] == 'CH:ecarup_finalization')
            artifacts = base / 'artifacts'
            shutil.copytree(bundle, artifacts / 'input_dependencies/CH_ecarup_coordinate')
            def process(command, **_):
                run(Path(command[command.index('--out') + 1]),
                    Path(command[command.index('--source') + 1]))
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, artifacts, runner=process)['status'], 'ok')
            self.assertEqual(run_source(spec, base / 'missing')['reason'], 'validated_dependency_missing')
            bad = base / 'bad/input_dependencies/CH_ecarup_coordinate'
            shutil.copytree(bundle, bad)
            row = json.loads((bad / 'manifest.json').read_text())['sources'][0]
            (bad / row['artifact']).write_bytes(b'corrupt')
            self.assertEqual(run_source(spec, base / 'bad')['reason'], 'validated_dependency_invalid')

    def test_bad_total_and_builder_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            _, state = signed_coordinate_bundle(base)
            coordinate = json.loads((state / COORDINATE).read_text())
            coordinate['nationalEvseCount'] = 4
            (state / COORDINATE).write_text(json.dumps(coordinate))
            with self.assertRaisesRegex(ValueError, 'coordinate evidence'):
                run(base / 'mismatch', state)
            _, good = signed_coordinate_bundle(base / 'fresh')
            def fail(*_, **__):
                return SimpleNamespace(returncode=1)
            with self.assertRaisesRegex(RuntimeError, 'finalizer failed'):
                run(base / 'failed', good, runner=fail)


if __name__ == '__main__':
    unittest.main()
