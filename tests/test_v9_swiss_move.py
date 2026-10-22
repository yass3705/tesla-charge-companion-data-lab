"""Offline CCI, SOC, and MMN MOVE tariff finalizer migration."""

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

from v9_rebuild import swiss_move
from v9_rebuild.orchestrator import read_sources, run_source

NATIONAL = [
    {'EvseID':'CH*CCI*E1','ChargingFacilities':[{'powertype':'AC'}]},
    {'EvseID':'CH*CCI*E2','ChargingFacilities':[{'powertype':'DC'}]},
    {'EvseID':'CH*CCI*E3','ChargingFacilities':[]},
    {'EvseID':'CH*SOC*E1','ChargingFacilities':[{'powertype':'AC'}]},
    {'EvseID':'CH*SOC*E2','ChargingFacilities':[]},
    {'EvseID':'CH*MMN*E1','ChargingFacilities':[{'powertype':'AC'}]},
    {'EvseID':'CH*MMN*E2','ChargingFacilities':[{'powertype':'DC'}]},
]


def fixture_root(root: Path):
    for script_name, *_ in swiss_move.METHODS.values():
        path = root / 'scripts' / script_name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(swiss_move.ROOT / 'scripts' / script_name, path)
    tariff = {'attributes':{'tariff_level':'cpo','is_roaming':False,
                            'prices_per_station_available':False,
                            'restricted_segments':[{'dimension':'kwh','charge_point_energy_type':'ac','price':0.4},
                                                   {'dimension':'kwh','charge_point_energy_type':'dc','price':0.5}]},
              'tariff':{'attributes':{'name':'MOVE direct','total_monthly_fee':0,'currency':'CHF'}},
              'cpo':{'attributes':{'name':'Move'}},'emp':{'attributes':{'name':'Move'}}}
    cci = {'stations':[{'evseIds':['CH*CCI*E1','CH*CCI*E2'],
                        'chargePoints':[{'chargePoint':{'energy_type':'ac','evse_ids':['CH*CCI*E1']},
                                         'directTariffs':[tariff]}]}]}
    soc = {'stations':[]}
    for path, value in zip(swiss_move.INPUTS, (cci, soc)):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value))


def offline_runner(command, **kwargs):
    if os.environ.get('TCC_FAIL_MOVE'):
        return SimpleNamespace(returncode=2)
    old = Path.cwd()
    try:
        os.chdir(kwargs['cwd'])
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(NATIONAL).encode())), \
             patch('builtins.print'):
            runpy.run_path(command[1], run_name='__main__')
    finally:
        os.chdir(old)
    return SimpleNamespace(returncode=0)


class SwissMoveMigrationTests(unittest.TestCase):
    def test_three_historical_finalizers_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            expected = {'cci':(2,1),'soc':(1,1),'mmn':(1,1)}
            for method in swiss_move.METHODS:
                with self.subTest(method=method):
                    with patch.object(swiss_move, 'ROOT', base / 'source'):
                        swiss_move.run(base / method, method, runner=offline_runner)
                    payload = swiss_move.validate_output(base / method, method)
                    self.assertEqual((len(payload['evses']),len(payload['unresolved'])), expected[method])
                    spec = next(row for row in read_sources() if row['id'] == f'CH:{method}_move')
                    def process(command, **_):
                        with patch.object(swiss_move, 'ROOT', base / 'source'):
                            swiss_move.run(Path(command[command.index('--out') + 1]), method,
                                           runner=offline_runner)
                        return SimpleNamespace(returncode=0)
                    self.assertEqual(run_source(spec, base / f'{method}-artifacts', runner=process)['status'], 'ok')

    def test_failed_method_and_bad_evse_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            with patch.object(swiss_move, 'ROOT', base / 'source'):
                with patch.dict(os.environ, {'TCC_FAIL_MOVE':'1'}):
                    with self.assertRaisesRegex(RuntimeError, 'method failed'):
                        swiss_move.run(base / 'failed', 'soc', runner=offline_runner)
                swiss_move.run(base / 'good', 'soc', runner=offline_runner)
            output = base / 'good' / swiss_move.METHODS['soc'][1]
            payload = json.loads(output.read_text())
            payload['evses'][0]['evseId'] = 'CH*CCI*E1'
            output.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, 'EVSE tariff scope'):
                swiss_move.validate_output(base / 'good', 'soc')


if __name__ == '__main__':
    unittest.main()
