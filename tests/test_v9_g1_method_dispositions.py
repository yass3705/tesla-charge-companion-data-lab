import unittest

from scripts.v9_g1_method_dispositions import classify_workflow


BASE = {
    "workflow": ".github/workflows/example.yml",
    "scheduled": False,
    "literal_production_references": {},
    "git_add_literal_paths": [],
    "literal_paths_untyped": [],
    "code_literal_paths_untyped": [],
    "upload_artifact_literal_paths": [],
}


class MethodDispositionTests(unittest.TestCase):
    def classify(self, **changes):
        return classify_workflow({**BASE, **changes}, {}, set())[0]

    def test_production_dependency_survives_report_only_wrapper(self):
        self.assertEqual(self.classify(literal_production_references={"reports/needed.json": ["scripts/build_snapshot.py"]}, git_add_literal_paths=["reports/needed.json"]), "retain_production_dependency")

    def test_scheduled_published_data_is_retained(self):
        self.assertEqual(self.classify(scheduled=True, git_add_literal_paths=["data/national/feed.json.gz"]), "retain_scheduled_data_method")

    def test_report_only_workflow_is_archived(self):
        self.assertEqual(self.classify(git_add_literal_paths=["reports/audit.json"], code_literal_paths_untyped=["data/national/feed.json.gz"]), "archive_validation_reference")

    def test_untyped_material_path_is_retained_as_partial(self):
        self.assertEqual(self.classify(literal_paths_untyped=["data/platforms/electroverse/source.json"]), "retain_dormant_partial_method")

    def test_no_output_is_archived_even_with_input_code_path(self):
        self.assertEqual(self.classify(code_literal_paths_untyped=["data/national/feed.json.gz"]), "archive_historical_reference")


if __name__ == "__main__":
    unittest.main()
