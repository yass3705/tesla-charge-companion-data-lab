import unittest

from scripts.check_v9_neutralized_main import FX_INSTALLED, EXTENDED_INSTALLED, DIRECT_INSTALLED, IMPORT_INSTALLED, REVE_INSTALLED, reviewed_scheduled_source


class ReviewedScheduleTests(unittest.TestCase):
    def test_source_head_workflow_and_event_are_bound(self):
        self.assertTrue(reviewed_scheduled_source("GL:fx", FX_INSTALLED, 425938005, "schedule"))
        self.assertFalse(reviewed_scheduled_source("GL:fx", FX_INSTALLED, 425938005, "workflow_dispatch"))
        self.assertFalse(reviewed_scheduled_source("GL:fx", EXTENDED_INSTALLED, 425938005, "schedule"))
        self.assertTrue(reviewed_scheduled_source("FR:sdey", DIRECT_INSTALLED, 425938005, "schedule"))
        self.assertTrue(reviewed_scheduled_source("ES:fixed_tariff_secondary", EXTENDED_INSTALLED, 425938005, "schedule"))
        self.assertFalse(reviewed_scheduled_source("ES:fixed_tariff_secondary", REVE_INSTALLED, 425938005, "schedule"))
        for head, workflow, event in [(IMPORT_INSTALLED, 425938005, "schedule"),
                                      (DIRECT_INSTALLED, 425938005, "workflow_dispatch"),
                                      (DIRECT_INSTALLED, 408526766, "schedule")]:
            self.assertFalse(reviewed_scheduled_source("FR:sdey", head, workflow, event))
        self.assertFalse(reviewed_scheduled_source("ES:reve_stream", REVE_INSTALLED, 425938005, "schedule"))
        self.assertTrue(reviewed_scheduled_source("FR:ionity_direct_family", IMPORT_INSTALLED, 425938005, "workflow_dispatch"))
