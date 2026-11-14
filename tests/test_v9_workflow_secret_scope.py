"""Public workflow must not inject another collector's credentials."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkflowSecretScopeTests(unittest.TestCase):
    def test_each_credential_is_limited_to_registered_consumers(self):
        sources = json.loads((ROOT / 'v9_rebuild/sources.json').read_text())['sources']
        body = (ROOT / '.github/workflows/v9-collect.yml').read_text()
        step = body.split('      - name: Collect migrated sources into isolated artifacts\n')[1].split('        run:')[0]
        seen = set()
        for line in step.splitlines():
            match = re.fullmatch(r"          ([A-Z][A-Z_0-9]+): \$\{\{ (.+) \}\}", line)
            if not match or match[1] == 'SOURCE_ID':
                continue
            name, expression = match.groups()
            # This deliberately accepts only the simple fail-closed expression
            # used here, not arbitrary GitHub expression code.
            condition, lookup = expression.split(' && ', 1)
            self.assertTrue(condition.startswith('(') and condition.endswith(')'))
            self.assertTrue(lookup.startswith('(') and lookup.endswith(") || ''"))
            owners = {re.fullmatch(r"inputs.source == '([^']+)'", part)[1]
                      for part in condition[1:-1].split(' || ')}
            key = 'GRIDSERVE_API_KEY' if name == 'GRIDSERVE_PCPR_API_KEY' else name
            expected = {s['id'] for s in sources if key in s.get('secret_names', [])}
            self.assertEqual(owners, expected, name)
            self.assertTrue(expected)
            seen.add(key)
        self.assertEqual(seen, {n for s in sources for n in s.get('secret_names', [])})
        self.assertIn('persist-credentials: false', body)
        self.assertNotIn('contents: write', body)

    def test_existing_secret_aliases_and_atlante_bootstrap_survive(self):
        body = (ROOT / '.github/workflows/v9-collect.yml').read_text()
        self.assertIn('secrets.MAPA_REVE_API_KEY || secrets.REVE_API_KEY', body)
        self.assertIn('secrets.GRIDSERVE_API_KEY', body)
        self.assertIn('secrets.ATLANTE_API_SUBSCRIPTION_KEY || env.ATLANTE_API_SUBSCRIPTION_KEY', body)
        self.assertIn('bash scripts/atlante/bootstrap_subscription_key.sh', body)


if __name__ == '__main__':
    unittest.main()
