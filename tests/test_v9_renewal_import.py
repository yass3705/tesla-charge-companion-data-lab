import json,tempfile,unittest
from pathlib import Path
from scripts.prepare_v9_renewed_ionity import build
class RenewalImport(unittest.TestCase):
 def test_wrong_execution_and_partial_input_leave_last_good_untouched(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);last=root/'last';last.mkdir();(last/'manifest.json').write_text('last-good')
   receipt=root/'run.json';meta=dict(head_branch='rebuild/v9-20261020',head_sha='abc',conclusion='success',status='completed',name='V9 bounded renewal pilot')
   receipt.write_text(json.dumps(meta));downloads=root/'download';(downloads/'source').mkdir(parents=True)
   (downloads/'source/manifest.json').write_text(json.dumps({'schema_version':1,'status':'partial','sources':[]}))
   with self.assertRaisesRegex(ValueError,'Untrusted'):build(downloads,receipt,'different',last,root/'out')
   with self.assertRaisesRegex(ValueError,'Partial'):build(downloads,receipt,'abc',last,root/'out')
   self.assertFalse((root/'out').exists());self.assertEqual((last/'manifest.json').read_text(),'last-good')
