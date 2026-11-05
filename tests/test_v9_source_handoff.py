import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_v9_source_handoff import check_execution,REPO
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
