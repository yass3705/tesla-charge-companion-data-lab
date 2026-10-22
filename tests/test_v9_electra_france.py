"""Offline migration checks for the archived Electra France platform builder."""

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

from v9_rebuild import electra_france
from v9_rebuild.orchestrator import read_sources, run_source


MOCK_FETCH = """
global.fetch = async (_url, options) => {
  const offset = JSON.parse(options.body).variables.offset;
  if (process.env.FAIL_ELECTRA_PAGE === '1' && offset === 100) throw new Error('fixture page interrupted');
  const total = Number(process.env.ELECTRA_TOTAL || 1);
  const items = offset === 0 ? Array.from({length: Math.min(total,100)}, (_,i) => ({
    id: `loc-${i}`, name: `Location ${i}`, country:'FR', coordinates:{latitude:48.8,longitude:2.3},
    connectorTypes:['CCS'], maxPower:50, cpo:{name:'Fixture CPO'}, operator:{name:'Fixture CPO'},
    evses:[{id:`evse-${i}`,evseId:'FR*FIX*E1',status:'AVAILABLE'}],
    chargeTariffs:[{chargeTariffId:'tariff-1',currency:'EUR',elements:[{
      restrictions:{},priceComponents:[{type:'ENERGY',price:0.4}]}]}]
  })) : (process.env.SHORT_ELECTRA_PAGE === '1' ? [] : [{
    id:'loc-tail',name:'Tail',country:'FR',coordinates:{latitude:48.9,longitude:2.4},
    connectorTypes:['CCS'],maxPower:50,cpo:{name:'Fixture CPO'},evses:[],chargeTariffs:[]}]);
  return {status:200,text:async()=>JSON.stringify({data:{locations:{totalCount:total,items}}})};
};
"""


def fixture_root(root: Path) -> None:
    for path in (electra_france.NATIONAL, electra_france.ASSOCIATIONS,
                 electra_france.VERIFIED, electra_france.SCRIPT):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
    row = [None] * 9
    row[8] = [[None, 'IRVE · CCS', 'DC', 50, None, None, ['FR*FIX*E1']]]
    with gzip.open(root / electra_france.NATIONAL, 'wt', encoding='utf-8') as stream:
        json.dump([row], stream)
    (root / electra_france.ASSOCIATIONS).write_text(json.dumps({
        'schemaVersion':1,'status':'curated_location_associations','batch':'base','associations':[]}))
    (root / electra_france.VERIFIED).write_text(json.dumps({'schemaVersion':1,'verifiedLinks':[]}))
    (root / electra_france.ASSOCIATION_DIR).mkdir(parents=True)
    shutil.copy2(electra_france.ROOT / electra_france.SCRIPT, root / electra_france.SCRIPT)
    (root / 'fetch.cjs').write_text(MOCK_FETCH)


def fixture_runner(command, **kwargs):
    env = dict(os.environ, NODE_OPTIONS=f"--require={kwargs['cwd'] / 'fetch.cjs'}",
               ELECTRA_TOTAL=os.environ.get('ELECTRA_TOTAL', '1'))
    env.update({key: os.environ[key] for key in ('FAIL_ELECTRA_PAGE', 'SHORT_ELECTRA_PAGE') if key in os.environ})
    return subprocess.run(command, **{**kwargs, 'env': env})


class ElectraFranceMigrationTests(unittest.TestCase):
    def test_historical_builder_exact_evse_and_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            with patch.object(electra_france, 'ROOT', base / 'source'):
                # Node preload stays in the isolated working directory.
                def run_node(command, **kwargs):
                    shutil.copy2(base / 'source/fetch.cjs', kwargs['cwd'] / 'fetch.cjs')
                    return fixture_runner(command, **kwargs)
                electra_france.run(base / 'direct', runner=run_node)
            manifest = electra_france.validate_output(base / 'direct')
            self.assertEqual(manifest['stats']['publishedOffers'], 1)
            self.assertEqual(manifest['sourceArchive']['locationCount'], 1)
            spec = next(row for row in read_sources() if row['id'] == 'FR:electra_platform')

            def process(command, **_):
                with patch.object(electra_france, 'ROOT', base / 'source'):
                    electra_france.run(Path(command[-1]), runner=run_node)
                return SimpleNamespace(returncode=0)

            result = run_source(spec, base / 'artifacts', runner=process)
            self.assertEqual(result['status'], 'ok')

    def test_incomplete_page_and_bad_digest_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture_root(base / 'source')
            def run_node(command, **kwargs):
                shutil.copy2(base / 'source/fetch.cjs', kwargs['cwd'] / 'fetch.cjs')
                return fixture_runner(command, **kwargs)
            with patch.object(electra_france, 'ROOT', base / 'source'):
                with patch.dict(os.environ, {'ELECTRA_TOTAL':'101','SHORT_ELECTRA_PAGE':'1'}):
                    with self.assertRaisesRegex(RuntimeError, 'builder failed'):
                        electra_france.run(base / 'short', runner=run_node)
                with patch.dict(os.environ, {'ELECTRA_TOTAL':'101','FAIL_ELECTRA_PAGE':'1'}):
                    with self.assertRaisesRegex(RuntimeError, 'builder failed'):
                        electra_france.run(base / 'interrupted', runner=run_node)
                electra_france.run(base / 'good', runner=run_node)
            manifest = electra_france.validate_output(base / 'good')
            tile = base / 'good' / electra_france.OUTPUT / manifest['tiles'][0]['file']
            tile.write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError, 'digest'):
                electra_france.validate_output(base / 'good')


if __name__ == '__main__':
    unittest.main()
