import copy,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_v9_source_handoff import check_execution,verify,REPO
class SourceHandoff(unittest.TestCase):
 def setUp(self):
  self.h='a'*40;self.r={'id':1,'status':'completed','conclusion':'failure','head_branch':'rebuild/v9-20261020','head_sha':self.h,'repository':{'full_name':REPO},'path':'.github/workflows/v9-tariff-restoration-pilot.yml'}
  self.j=[{'name':'collect (FR:belib)','status':'completed','conclusion':'success'}]
  self.a={'expired':False,'digest':'sha256:'+'b'*64,'workflow_run':{'id':1,'head_sha':self.h,'head_branch':'rebuild/v9-20261020'}}
 def check(self):return check_execution(self.r,self.j,self.a,'FR:belib',self.h)
 def test_independent_success_does_not_relabel_failed_run(self):
  self.assertEqual(self.check()['conclusion'],'success');self.assertEqual(self.r['conclusion'],'failure')
 def test_failed_or_partial_source_rejected(self):
  for key,value in [('conclusion','failure'),('status','in_progress')]:
   old=self.j[0][key];self.j[0][key]=value
   with self.assertRaises(ValueError):self.check()
   self.j[0][key]=old
 def test_wrong_branch_sha_repository_and_run_rejected(self):
  for key,value in [('head_branch','main'),('head_sha','c'*40),('status','in_progress'),('repository',{'full_name':'other/repo'})]:
   old=self.r[key];self.r[key]=value
   with self.assertRaises(ValueError):self.check()
   self.r[key]=old
  self.a['workflow_run']['id']=2
  with self.assertRaises(ValueError):self.check()
 def test_expired_artifact_or_duplicate_jobs_rejected(self):
  self.a['expired']=True
  with self.assertRaises(ValueError):self.check()
  self.a['expired']=False;self.j*=2
  with self.assertRaises(ValueError):self.check()
 def test_cached_zip_still_requires_current_github_digest(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t);(out/'artifact.zip').write_bytes(b'bad')
   self.a.update(id=12,name='fixture',size_in_bytes=3)
   replies=[{'enabled':False},self.r,{'jobs':self.j},{'artifacts':[self.a]}]
   with patch('verify_v9_source_handoff.subprocess.check_output',side_effect=[json.dumps(x).encode() for x in replies]) as calls:
    with self.assertRaisesRegex(ValueError,'ZIP integrity'):
     verify(1,'FR:belib','fixture',self.h,out,reuse_archive=True)
   self.assertEqual(calls.call_count,4)
   self.assertFalse((out/'receipt.json').exists())
 def test_cached_valid_zip_is_rechecked_and_extracted_without_redownload(self):
  import hashlib,io,zipfile
  body=io.BytesIO()
  with zipfile.ZipFile(body,'w') as z:z.writestr('manifest.json','{}')
  raw=body.getvalue()
  with tempfile.TemporaryDirectory() as t:
   out=Path(t);(out/'artifact.zip').write_bytes(raw);self.j[0]['id']=17
   self.a.update(id=12,name='fixture',size_in_bytes=len(raw),digest='sha256:'+hashlib.sha256(raw).hexdigest())
   replies=[{'enabled':False},self.r,{'jobs':self.j},{'artifacts':[self.a]}]
   with patch('verify_v9_source_handoff.subprocess.check_output',side_effect=[json.dumps(x).encode() for x in replies]) as calls,patch('verify_v9_source_handoff.verify_files',side_effect=lambda folder,source:(folder,'c'*64,[])):
    report=verify(1,'FR:belib','fixture',self.h,out,reuse_archive=True)
   self.assertEqual(calls.call_count,4);self.assertEqual(report['technicalValidation'],'PASS')
   self.assertTrue((Path((out/'state-path.txt').read_text().strip())/'manifest.json').is_file())
   self.assertEqual((out/'artifact.zip').read_bytes(),raw)
