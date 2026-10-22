"""Offline execution of archived EnergyVision stage, catalog, and NAP audit."""

import gzip
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild import energyvision
from v9_rebuild.orchestrator import read_sources, run_source

FAKE_KEY = "fixture" + "-" + "token"

STATIC = b'''<payload><energyInfrastructureSite id="SITE1">
 <brand><values><value>EnergyVision</value></values></brand>
 <entrance><pointByCoordinates><pointCoordinates><latitude>50.85</latitude><longitude>4.35</longitude></pointCoordinates></pointByCoordinates></entrance>
 <energyInfrastructureStation id="STATION1"><numberOfRefillPoints>1</numberOfRefillPoints>
  <refillPoint id="PDC1"><availableChargingPower>22000</availableChargingPower>
   <connector><connectorType><value>iec62196T2</value></connectorType><maxPowerAtSocket>22000</maxPowerAtSocket>
    <externalIdentifier><identifier>BE*EV*E1</identifier></externalIdentifier></connector></refillPoint>
  <energyProduct><energyRate id="RATE1"><ratePolicy>adHoc</ratePolicy><applicableCurrency>EUR</applicableCurrency>
   <energyPrice><priceType>pricePerKWh</priceType><value>0.35</value></energyPrice>
  </energyRate></energyProduct>
 </energyInfrastructureStation>
</energyInfrastructureSite></payload>'''
DYNAMIC = b'''<payload><energyInfrastructureSiteStatus><energyInfrastructureStationStatus>
 <refillPointStatus><reference id="PDC1"/><status><value>available</value></status></refillPointStatus>
</energyInfrastructureStationStatus></energyInfrastructureSiteStatus></payload>'''
SITE_CUSTOMIZE = '''import io, os, urllib.request
from pathlib import Path
def offline(request, **kwargs):
    url = request.full_url
    if url.endswith("/energy-infrastructure-table"):
        name = "static.xml"
    elif url.endswith("/energy-infrastructure-status"):
        name = "dynamic.xml"
    else:
        raise RuntimeError("unexpected network route: " + url)
    if os.environ.get("TCC_FAIL_DYNAMIC") == "1" and name == "dynamic.xml":
        raise RuntimeError("fixture status request interrupted")
    stream = io.BytesIO((Path(os.environ["TCC_FIXTURE_DIR"]) / name).read_bytes())
    stream.status = 200
    stream.headers = {}
    return stream
urllib.request.urlopen = offline
'''


def fixture_root(root: Path) -> None:
    (root / 'scripts').mkdir(parents=True)
    for name in energyvision.METHODS:
        shutil.copy2(energyvision.ROOT / 'scripts' / name, root / 'scripts' / name)
    manifest = root / energyvision.NAP_MANIFEST
    manifest.parent.mkdir(parents=True)
    page = Path('data/belgium/pages/nap-belgium-000000.json.gz')
    manifest.write_text(json.dumps({'country':'BE','pages':[{'canonicalPath':str(page)}]}))
    target = root / page
    target.parent.mkdir(parents=True)
    with gzip.open(target, 'wt') as stream:
        json.dump({'locations':[]}, stream)
    (root / 'static.xml').write_bytes(STATIC)
    (root / 'dynamic.xml').write_bytes(DYNAMIC)
    (root / 'sitecustomize.py').write_text(SITE_CUSTOMIZE)


class EnergyVisionMigrationTests(unittest.TestCase):
    def test_complete_chain_keeps_station_rate_unassigned(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            def process(command, **kwargs):
                shutil.copy2(base / 'source/sitecustomize.py', kwargs['cwd'] / 'sitecustomize.py')
                env = dict(os.environ, ENERGYVISION_API_KEY=FAKE_KEY,
                           TCC_FIXTURE_DIR=str(base / 'source'), PYTHONPATH=str(kwargs['cwd']))
                return subprocess.run(command, **{**kwargs, 'env':env})
            with patch.object(energyvision, 'ROOT', base / 'source'):
                energyvision.run(base / 'direct', runner=process)
            payload = energyvision.validate_output(base / 'direct')
            self.assertFalse(payload['v9PublicationReady'])
            self.assertEqual(payload['v9PricedPDC'], 0)
            self.assertEqual(payload['counts']['sourcePDC'], 1)
            self.assertEqual(payload['sites'][0]['stations'][0]['sourceStationRatesUnassignedToPdc'][0]['sourceRateId'], 'RATE1')
            spec = next(row for row in read_sources() if row['id'] == 'BE:energyvision')
            def orchestrated(command, **_):
                with patch.object(energyvision, 'ROOT', base / 'source'):
                    energyvision.run(Path(command[-1]), runner=process)
                return SimpleNamespace(returncode=0)
            with patch.dict(os.environ, {'ENERGYVISION_API_KEY':FAKE_KEY}):
                result = run_source(spec, base / 'artifacts', runner=orchestrated)
            self.assertEqual(result['status'], 'ok')

    def test_interruption_and_corrupt_stage_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            def process(command, **kwargs):
                shutil.copy2(base / 'source/sitecustomize.py', kwargs['cwd'] / 'sitecustomize.py')
                env = dict(os.environ, ENERGYVISION_API_KEY=FAKE_KEY,
                           TCC_FIXTURE_DIR=str(base / 'source'), PYTHONPATH=str(kwargs['cwd']))
                return subprocess.run(command, **{**kwargs, 'env':env})
            with patch.object(energyvision, 'ROOT', base / 'source'):
                with patch.dict(os.environ, {'TCC_FAIL_DYNAMIC':'1'}):
                    with self.assertRaisesRegex(RuntimeError, 'method failed'):
                        energyvision.run(base / 'failed', runner=process)
                energyvision.run(base / 'good', runner=process)
            path = base / 'good' / energyvision.INDEPENDENT
            path.write_bytes(b'corrupt')
            with self.assertRaises(OSError):
                energyvision.validate_output(base / 'good')


if __name__ == '__main__':
    unittest.main()
