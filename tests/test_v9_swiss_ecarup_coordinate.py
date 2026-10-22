"""Offline exact-coordinate Swiss eCarUp method migration."""

import io
import json
import os
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild import cwd_script
from v9_rebuild.orchestrator import read_sources, run_batch, run_source

METHOD = 'swiss_ecarup_coordinate'
NATIONAL = [
    {'OperatorID':'CH*ECU','EvseID':'CH*ECU*E1','GeoCoordinates':{'Google':'46.8 8.2'}},
    {'OperatorID':'CH*ECU','EvseID':'CH*ECU*E2','GeoCoordinates':{'Google':'46.9 8.3'}},
    {'OperatorID':'CH*ECU','EvseID':'CH*ECU*E3','GeoCoordinates':{'Google':'47.0 8.4'}},
]


def station(identifier, lat, lon, rate):
    return {'ID':identifier,'Name':identifier,'Latitude':lat,'Longitude':lon,
            'Connectors':[{'ID':identifier+'-c','AccessType':0,
                           'Price':{'EnergyPrice':rate,'Currency':'CHF'}}]}


def fixture_root(root: Path):
    (root / 'scripts').mkdir(parents=True)
    shutil.copy2(cwd_script.ROOT / cwd_script.METHODS[METHOD][0],
                 root / cwd_script.METHODS[METHOD][0])
    shutil.copy2(cwd_script.ROOT / cwd_script.METHODS['swiss_ecarup_owner'][0],
                 root / cwd_script.METHODS['swiss_ecarup_owner'][0])
    data = root / 'data/switzerland'
    data.mkdir(parents=True)
    (data / 'ecarup-public-stations.json').write_text(json.dumps({'stations':[
        station('one',46.8,8.2,0.4), station('two-a',46.9,8.3,0.4),
        station('two-b',46.9,8.3,0.6)]}))
    (data / 'ecarup-owner-direct-tariffs.json').write_text(json.dumps({'evses':[]}))


def offline_runner(command, **kwargs):
    if os.environ.get('TCC_FAIL_COORDINATE'):
        return SimpleNamespace(returncode=1)
    old = Path.cwd()
    try:
        os.chdir(kwargs['cwd'])
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(NATIONAL).encode())):
            runpy.run_path(command[1], run_name='__main__')
    finally:
        os.chdir(old)
    return SimpleNamespace(returncode=0)


class SwissEcarupCoordinateMigrationTests(unittest.TestCase):
    def test_exact_ambiguous_missing_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            with patch.object(cwd_script, 'ROOT', base / 'source'):
                cwd_script.run(base / 'direct', METHOD, runner=offline_runner)
            result = cwd_script.validate_output(base / 'direct', METHOD)
            self.assertEqual([row['evseId'] for row in result['evses']], ['CH*ECU*E1'])
            self.assertEqual([row['evseId'] for row in result['ambiguous']], ['CH*ECU*E2'])
            self.assertEqual([row['evseId'] for row in result['noCandidate']], ['CH*ECU*E3'])
            spec = next(row for row in read_sources() if row['id'] == 'CH:ecarup_coordinate')
            owner_spec = next(row for row in read_sources() if row['id'] == 'CH:ecarup_owner')
            def owner_process(command, **_):
                with patch.object(cwd_script, 'ROOT', base / 'source'):
                    cwd_script.run(Path(command[command.index('--out') + 1]),
                                   'swiss_ecarup_owner', runner=offline_runner)
                return SimpleNamespace(returncode=0)
            bundle = base / 'owner-bundle'
            self.assertEqual(run_batch([owner_spec], bundle, runner=owner_process)['status'], 'complete')
            dependency = base / 'artifacts/input_dependencies/CH_ecarup_owner'
            shutil.copytree(bundle, dependency)
            def process(command, **_):
                with patch.object(cwd_script, 'ROOT', base / 'source'):
                    cwd_script.run(Path(command[command.index('--out') + 1]), METHOD,
                                   source=Path(command[command.index('--source') + 1]),
                                   runner=offline_runner)
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, base / 'artifacts', runner=process)['status'], 'ok')
            missing = run_source(spec, base / 'missing')
            self.assertEqual(missing['reason'], 'validated_dependency_missing')
            copied = base / 'bad/input_dependencies/CH_ecarup_owner'
            shutil.copytree(bundle, copied)
            row = json.loads((copied / 'manifest.json').read_text())['sources'][0]
            (copied / row['artifact']).write_bytes(b'bad')
            self.assertEqual(run_source(spec, base / 'bad')['reason'], 'validated_dependency_invalid')

    def test_failure_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            with patch.object(cwd_script, 'ROOT', base / 'source'):
                with patch.dict(os.environ, {'TCC_FAIL_COORDINATE':'1'}):
                    with self.assertRaisesRegex(RuntimeError, 'method failed'):
                        cwd_script.run(base / 'failed', METHOD, runner=offline_runner)
                cwd_script.run(base / 'good', METHOD, runner=offline_runner)
            path = base / 'good' / cwd_script.METHODS[METHOD][1]
            payload = json.loads(path.read_text())
            payload['evses'][0]['evseId'] = 'CH*ECU*E2'
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'eCarUp coordinate evidence'):
                cwd_script.validate_output(base / 'good', METHOD)


if __name__ == '__main__':
    unittest.main()
