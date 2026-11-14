import json
import subprocess
import unittest
from v9_rebuild.failure_diagnostics import process_failure

class FailureDiagnostics(unittest.TestCase):
    def test_http_error_is_diagnosable_without_credentials_or_provider_text(self):
        secret='never-export-this-credential'
        result=process_failure(subprocess.CompletedProcess([],1,
            stdout=json.dumps({'offset':1000,'page':1,'nextOffset':2000,'locations':3,
                               'token':secret,'response':secret})+'\n'+secret,
            stderr='Traceback (most recent call last):\n  File "/private/project/collector.py", line 42, in fetch_page\n'+
                   'urllib.error.HTTPError: HTTP Error 429: '+secret+'\nAuthorization: Bearer '+secret))
        self.assertEqual(result['httpStatuses'],[429])
        self.assertEqual(result['exceptionType'],'urllib.error.HTTPError')
        self.assertEqual(result['frames'],[{'file':'collector.py','line':42,'function':'fetch_page'}])
        self.assertEqual(result['progress'],[{'offset':1000,'page':1,'nextOffset':2000,'locations':3}])
        self.assertNotIn(secret,json.dumps(result));self.assertNotIn('/private',json.dumps(result))
    def test_unknown_logs_and_tainted_numeric_fields_are_not_copied(self):
        result=process_failure(subprocess.CompletedProcess([],2,stdout='{"offset":0,"nextOffset":"secret","locations":true}\nnot json',stderr='private header'))
        self.assertEqual(result['progress'],[{'offset':0}]);self.assertIsNone(result['exceptionType'])
        self.assertEqual(result['httpStatuses'],[]);self.assertFalse(result['rawLogsStored'])
