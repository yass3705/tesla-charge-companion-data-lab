"""Archived exact Plenitude residual rules on a signed initial state."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v9_rebuild import swiss_plenitude_closeout
from v9_rebuild.orchestrator import artifact_digest, read_sources, run_source, sha256
from v9_rebuild.swiss_plenitude_closeout import ATLAS, CONTEXT, DATA, REPORT, run, validate_output


def initial_bundle(base: Path) -> tuple[Path, Path]:
    stage = base / 'initial-stage'
    for relative in (ATLAS, DATA, REPORT):
        (stage / relative).parent.mkdir(parents=True, exist_ok=True)
    (stage / ATLAS).write_text(json.dumps({'country':'CH','operatorId':'CH*PLN','stations':[]}))
    rows = [{'evseId':'CH*PLN*EEXACT*1','pricePerKwh':0.5,'category':'Quick','currency':'CHF'}]
    unresolved = [{'evseId':'CH*PLN*EH000762*3'},
                  {'evseId':'CH*PLN*ERES*1'},
                  {'evseId':'CH*PLN*EUNKNOWN*1'}]
    payload = {'schemaVersion':1,'country':'CH','cpo':'Plenitude On The Road','operatorId':'CH*PLN',
               'counts':{'nationalEvseCount':4,'pricedEvseCount':1,'unresolvedEvseCount':3},
               'evses':rows,'unresolved':unresolved}
    (stage / DATA).write_text(json.dumps(payload))
    (stage / REPORT).write_text(json.dumps({'status':'partial','productionSource':str(DATA),
                                            'nationalEvseCount':4,'pricedEvseCount':1,
                                            'unresolvedEvseCount':3}))
    digest, files = artifact_digest(stage)
    bundle = base / 'initial-bundle'
    state = bundle / 'objects/CH_plenitude_official' / digest
    state.parent.mkdir(parents=True)
    shutil.copytree(stage, state)
    artifact = state / DATA
    (bundle / 'manifest.json').write_text(json.dumps({'schema_version':1,'status':'complete',
        'sources':[{'source':'CH:plenitude_official','module':'cwd_script','status':'ok',
                    'artifact':str(artifact.relative_to(bundle)),'sha256':sha256(artifact),
                    'artifact_set_sha256':digest,'files':files}]}))
    return bundle, state


def fixture_root(root: Path) -> None:
    for name in swiss_plenitude_closeout.SCRIPTS:
        script = root / 'scripts' / name
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(swiss_plenitude_closeout.ROOT / 'scripts' / name, script)
    context = root / CONTEXT
    context.parent.mkdir(parents=True, exist_ok=True)
    context.write_text(json.dumps({'CH*PLN*ERES*1':{
        'Accessibility':'Restricted access','AuthenticationModes':[]}}))


class SwissPlenitudeCloseoutTests(unittest.TestCase):
    def test_exact_mapping_restricted_and_signed_orchestration(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle, state = initial_bundle(base)
            fixture_root(base / 'fixture-root')
            with patch.object(swiss_plenitude_closeout, 'ROOT', base / 'fixture-root'):
                run(base / 'direct', state)
            payload = validate_output(base / 'direct')
            self.assertEqual(payload['counts']['pricedEvseCount'], 2)
            self.assertEqual(payload['counts']['classifiedNoPublicDirectTariffCount'], 1)
            self.assertEqual(payload['counts']['unresolvedEvseCount'], 1)
            spec = next(row for row in read_sources() if row['id'] == 'CH:plenitude_closeout')
            artifacts = base / 'artifacts'
            shutil.copytree(bundle, artifacts / 'input_dependencies/CH_plenitude_official')
            def process(command, **_):
                with patch.object(swiss_plenitude_closeout, 'ROOT', base / 'fixture-root'):
                    run(Path(command[command.index('--out') + 1]),
                        Path(command[command.index('--source') + 1]))
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_source(spec, artifacts, runner=process)['status'], 'ok')
            self.assertEqual(run_source(spec, base / 'missing')['reason'], 'validated_dependency_missing')
            bad = base / 'bad/input_dependencies/CH_plenitude_official'
            shutil.copytree(bundle, bad)
            row = json.loads((bad / 'manifest.json').read_text())['sources'][0]
            (bad / row['artifact']).write_bytes(b'bad')
            self.assertEqual(run_source(spec, base / 'bad')['reason'], 'validated_dependency_invalid')

    def test_bad_restricted_evidence_and_builder_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            _, state = initial_bundle(base)
            fixture_root(base / 'fixture-root')
            with patch.object(swiss_plenitude_closeout, 'ROOT', base / 'fixture-root'):
                run(base / 'direct', state)
            path = base / 'direct' / CONTEXT
            context = json.loads(path.read_text())
            context['CH*PLN*ERES*1'] = {'Accessibility':'Public access'}
            path.write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'restricted scope'):
                validate_output(base / 'direct')
            def fail(*_, **__):
                return SimpleNamespace(returncode=2)
            with patch.object(swiss_plenitude_closeout, 'ROOT', base / 'fixture-root'):
                with self.assertRaisesRegex(RuntimeError, 'closeout failed'):
                    run(base / 'failed', state, runner=fail)


if __name__ == '__main__':
    unittest.main()
