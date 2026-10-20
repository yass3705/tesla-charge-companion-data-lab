import copy
import json
import unittest

from scripts.validate_v9_g1 import ROOT, validate_missing_code


class MissingMethodExceptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads((ROOT / "migration/v9/legacy-inventory.json").read_text())
        cls.exceptions = json.loads((ROOT / "migration/v9/legacy-method-exceptions.json").read_text())

    def test_exact_documented_exception_passes(self):
        self.assertEqual(validate_missing_code(ROOT, self.inventory, self.exceptions), [])

    def test_new_missing_script_fails(self):
        inventory = copy.deepcopy(self.inventory)
        inventory["workflows"][0]["missing_script_references"] = ["scripts/unlisted.py"]
        self.assertTrue(validate_missing_code(ROOT, inventory, self.exceptions))

    def test_exception_cannot_hide_restored_or_changed_method(self):
        exceptions = copy.deepcopy(self.exceptions)
        exceptions["exceptions"][0]["workflow_sha256"] = "0" * 64
        self.assertTrue(validate_missing_code(ROOT, self.inventory, exceptions))

    def test_exception_cannot_be_removed_silently(self):
        self.assertTrue(validate_missing_code(ROOT, self.inventory, {"exceptions": []}))

    def test_arbitrary_second_exception_fails(self):
        inventory = copy.deepcopy(self.inventory)
        inventory["workflows"][0]["missing_script_references"] = ["scripts/unlisted.py"]
        exceptions = copy.deepcopy(self.exceptions)
        extra = copy.deepcopy(exceptions["exceptions"][0])
        extra["workflow"] = inventory["workflows"][0]["workflow"]
        extra["missing_scripts"] = ["scripts/unlisted.py"]
        exceptions["exceptions"].append(extra)
        self.assertTrue(validate_missing_code(ROOT, inventory, exceptions))


if __name__ == "__main__":
    unittest.main()
