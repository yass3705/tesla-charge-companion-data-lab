"""Credential routing regression tests; no live access or credential values."""
import re
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class AuthContracts(unittest.TestCase):
    def test_reve_uses_existing_repository_name(self):
        text = (ROOT / '.github/workflows/v9-collect.yml').read_text()
        self.assertIn('REVE_API_KEY: ${{ secrets.MAPA_REVE_API_KEY || secrets.REVE_API_KEY }}', text)

    def test_atlante_generated_header_is_not_erased_by_absent_secret(self):
        text = (ROOT / '.github/workflows/v9-collect.yml').read_text()
        prepare = text.split('- name: Resolve preserved Atlante technical app header')[1].split('- name:')[0]
        self.assertIn("inputs.source == 'FR:atlante_fr_it' || inputs.source == 'FR:atlante_direct'", prepare)
        self.assertIn('bash scripts/atlante/bootstrap_subscription_key.sh', prepare)
        collect = text.split('- name: Collect migrated sources into isolated artifacts')[1].split('- name:')[0]
        expression = re.search(r'ATLANTE_API_SUBSCRIPTION_KEY: \$\{\{ (.*?) \}\}', collect).group(1)
        self.assertEqual(expression, 'secrets.ATLANTE_API_SUBSCRIPTION_KEY || env.ATLANTE_API_SUBSCRIPTION_KEY')
        def resolve(secrets, env):
            contexts = {'secrets': secrets, 'env': env}
            for token in expression.split(' || '):
                namespace, name = token.split('.')
                if contexts[namespace].get(name):
                    return contexts[namespace][name]
            return ''
        key = 'ATLANTE_API_SUBSCRIPTION_KEY'
        self.assertEqual(resolve({}, {key: 'generated-placeholder'}), 'generated-placeholder')
        self.assertEqual(resolve({key: 'supplied-placeholder'}, {key: 'generated-placeholder'}), 'supplied-placeholder')
        bootstrap = (ROOT / 'scripts/atlante/bootstrap_subscription_key.sh').read_text()
        self.assertIn('VERSION_CODE="4519"', bootstrap)
        self.assertRegex(bootstrap, r'XAPK_SHA256="[a-f0-9]{64}"')
        self.assertIn('Pinned myAtlante XAPK checksum mismatch', bootstrap)
        self.assertIn('::add-mask::', bootstrap)
        self.assertIn('>> "$GITHUB_ENV"', bootstrap)

if __name__ == '__main__':
    unittest.main()
