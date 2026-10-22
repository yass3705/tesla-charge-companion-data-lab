"""Offline exact Swiss eCarUp owner reconciliation."""

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
from v9_rebuild.orchestrator import read_sources, run_source

METHOD = 'swiss_ecarup_owner'
NATIONAL = [
    {'OperatorID':'CH*ECU','EvseID':'CH*ECU*E1'},
    {'OperatorID':'CH*ECU','EvseID':'CH*ECU*E2'},
    {'OperatorID':'CH*ECU','EvseID':'CH*ECU*E3','Accessibility':'Restricted access','AuthenticationModes':[]},
    {'OperatorID':'CH*ECU','EvseID':'CH*ECU*E4'},
]


def fixture_root(root: Path):
    (root / 'scripts').mkdir(parents=True)
    shutil.copy2(cwd_script.ROOT / cwd_script.METHODS[METHOD][0], root / cwd_script.METHODS[METHOD][0])
    data = root / 'data/switzerland'
    data.mkdir(parents=True)
    (data / 'ecarup-public-stations.json').write_text(json.dumps({'stations':[
        {'ID':'station-1','Name':'One','Connectors':[{'Id':'c1','Hubject':{'ID':'CH*ECU*E1'},
                                                    'AccessType':0,'Price':{'EnergyPrice':0.4,'Currency':'CHF'}}]},
        {'ID':'station-2','Name':'Two','Connectors':[{'Id':'c2','Hubject':{'ID':'CH*ECU*E2'},
                                                    'AccessType':1,'Price':None}]},
    ]}))


def offline_runner(command, **kwargs):
    if os.environ.get('TCC_FAIL_OWNER'):
        return SimpleNamespace(returncode=1)
    old = Path.cwd()
    try:
        os.chdir(kwargs['cwd'])
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(NATIONAL).encode())):
            runpy.run_path(command[1], run_name='__main__')
    finally:
        os.chdir(old)
    return SimpleNamespace(returncode=0)


class SwissEcarupOwnerMigrationTests(unittest.TestCase):
    def test_exact_price_restricted_and_unmatched(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            with patch.object(cwd_script, 'ROOT', base / 'source'):
                cwd_script.run(base / 'direct', METHOD, runner=offline_runner)
            payload = cwd_script.validate_output(base / 'direct', METHOD)
            self.assertEqual(payload['counts']['pricedEvseCount'], 1)
            self.assertEqual(payload['counts']['classifiedNoPublicDirectTariffCount'], 2)
            self.assertEqual(payload['counts']['unresolvedEvseCount'], 1)
            spec = next(row for row in read_sources() if row['id'] == 'CH:ecarup_owner')
            def process(command, **_):
                with patch.object(cwd_script, 'ROOT', base / 'source'):
                    cwd_script.run(Path(command[command.index('--out') + 1]), METHOD, runner=offline_runner)
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, base / 'artifacts', runner=process)['status'], 'ok')

    def test_failure_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            with patch.object(cwd_script, 'ROOT', base / 'source'):
                with patch.dict(os.environ, {'TCC_FAIL_OWNER':'1'}):
                    with self.assertRaisesRegex(RuntimeError, 'method failed'):
                        cwd_script.run(base / 'failed', METHOD, runner=offline_runner)
                cwd_script.run(base / 'good', METHOD, runner=offline_runner)
            path = base / 'good' / cwd_script.METHODS[METHOD][1]
            payload = json.loads(path.read_text())
            payload['counts']['pricedEvseCount'] = 2
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'owner contract'):
                cwd_script.validate_output(base / 'good', METHOD)


if __name__ == '__main__':
    unittest.main()
