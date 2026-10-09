#!/usr/bin/env python3
"""Regression of the frozen IRVE->tariff archive trigger and snapshot gating."""
import datetime as dt,runpy,unittest,pathlib
GATE=runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1]/'scripts/france/check_irve_tariff_review_gate.py'))['decide']
NOW=dt.datetime(2026,10,9,20,0,tzinfo=dt.timezone.utc)
def data(hours=1,sha='feed-abc'):
 return {'enServicePdcIds':['FRA001','FRA002'],'states':{'en_service':2},
         'sourceSha256':sha,'generatedAt':(NOW-dt.timedelta(hours=hours)).isoformat()}
def prior(d):
 return {'provenance':{'irveDynamic':{'sourceSha256':d['sourceSha256'],'generatedAt':d['generatedAt']}}}
class GateTests(unittest.TestCase):
 def test_new_dynamic_after_irve_publication_runs(self):
  self.assertEqual(GATE(data(),prior(data(2)), 'workflow_run','France IRVE static refresh and residual audit',NOW)[0],'run')
 def test_reused_dynamic_skips_pan_outage(self):
  d=data();self.assertEqual(GATE(d,prior(d),'workflow_run','France IRVE static refresh and residual audit',NOW),('skip','dynamic_already_reviewed'))
 def test_schedule_does_not_double_review(self):
  d=data();self.assertEqual(GATE(d,prior(d),'schedule','',NOW)[0],'skip')
 def test_provider_validation_rechecks_overlay_with_same_dynamic(self):
  d=data();self.assertEqual(GATE(d,prior(d),'workflow_run','Build France Electroverse EVSE overlay',NOW)[0],'run')
 def test_stale_dynamic_never_published(self):
  self.assertEqual(GATE(data(hours=76),None,'workflow_dispatch','',NOW),('skip','dynamic_too_old_or_future'))
 def test_missing_positive_list_is_rejected(self):
  d=data();d['enServicePdcIds']=[];self.assertEqual(GATE(d,None,'workflow_run','France IRVE static refresh and residual audit',NOW)[0],'skip')
 def test_invalid_status_count_is_rejected(self):
  d=data();d['states']['en_service']=3;self.assertEqual(GATE(d,None,'schedule','',NOW)[0],'skip')
 def test_new_irve_generatedAt_same_sha_runs(self):
  # Recollection of identical bytes is a NEW temporal observation; do not skip it.
  d=data();self.assertEqual(GATE(d,prior(data(hours=2)),'workflow_run','France IRVE static refresh and residual audit',NOW)[0],'run')
if __name__=='__main__':unittest.main()
