"""Regression guards for read-only EnergyVision XML metadata auditing."""
import gzip
import io
import unittest
from types import SimpleNamespace

from scripts.energyvision_datex_inventory_probe import local, safely_read, xml_structure


class EnergyVisionProbeTests(unittest.TestCase):
    def test_tag_and_namespace(self):
        self.assertEqual(local("{urn:datex}energyInfrastructurePoint"), "energyInfrastructurePoint")

    def test_structural_counts_without_record_values(self):
        fixture = b"""<?xml version="1.0"?>
<d:payload xmlns:d="urn:datex">
 <d:energyInfrastructureSite id="SENSITIVE_STATION_1">
  <d:energyInfrastructurePoint id="SENSITIVE_EVSE_1">
   <d:priceAmount>123.45</d:priceAmount>
  </d:energyInfrastructurePoint>
 </d:energyInfrastructureSite>
</d:payload>"""
        summary = xml_structure(fixture)
        self.assertEqual(summary["rootTag"], "payload")
        self.assertEqual(summary["namespace"], "urn:datex")
        self.assertEqual(summary["elementCounts"]["energyInfrastructureSite"], 1)
        self.assertEqual(summary["elementCounts"]["energyInfrastructurePoint"], 1)
        self.assertEqual(summary["elementCounts"]["priceAmount"], 1)
        self.assertIn("id", summary["attributeCounts"])
        self.assertNotIn("123.45", str(summary))
        self.assertNotIn("SENSITIVE_STATION_1", str(summary))
        self.assertNotIn("SENSITIVE_EVSE_1", str(summary))

    def test_entity_expansion_is_rejected(self):
        payload = b'<!DOCTYPE x [<!ENTITY unsafe "private">]><x>&unsafe;</x>'
        with self.assertRaises(Exception):
            xml_structure(payload)

    def test_gzip_payload_and_size_limit(self):
        value = b"<data>ok</data>"
        packed = gzip.compress(value)
        compressed = SimpleNamespace(
            headers={"Content-Encoding": "gzip"}, read=lambda n: packed[:n])
        self.assertEqual(safely_read(compressed, 200), value)
        oversized = SimpleNamespace(headers={}, read=lambda n: b"123456")
        with self.assertRaises(ValueError):
            safely_read(oversized, 5)


if __name__ == "__main__":
    unittest.main()
