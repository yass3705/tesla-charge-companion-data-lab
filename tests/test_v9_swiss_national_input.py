import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request

from scripts.swiss_national_input import open_national, URL


class SharedInputTests(unittest.TestCase):
    def test_shared_bytes_require_expected_origin_digest_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "source"
            for data, valid in [({"EVSEData": [{"OperatorID": "CH*TEST", "EVSEDataRecord": []}]}, True),
                                ({"EVSEData": [{}]}, False)]:
                raw = json.dumps(data).encode()
                file.write_bytes(raw)
                with patch.dict(os.environ, TCC_CH_OICP_FILE=str(file), TCC_CH_OICP_SHA256=hashlib.sha256(raw).hexdigest()), patch("urllib.request.urlopen") as network:
                    if valid:
                        self.assertEqual(open_national(Request(URL), 90).read(), raw)
                    else:
                        with self.assertRaises(ValueError):
                            open_national(Request(URL), 90)
                    with self.assertRaises(ValueError):
                        open_national(Request("https://example.invalid"), 90)
                    file.write_bytes(b"changed")
                    with self.assertRaisesRegex(ValueError, "SHA"):
                        open_national(Request(URL), 90)
                    network.assert_not_called()
