import copy,tempfile,unittest
from pathlib import Path
from scripts.build_v9_archived_direct_profiles import normalize,replay
class ArchivedDirectProfiles(unittest.TestCase):
 def setUp(self):
  self.n={'source':{'id':'FR:irve_static'},'cpos':[{'id':'c','country':'FR','sourceOperatorId':'CPO'}],
   'stations':[{'id':'s','country':'FR','cpoId':'c','sourceStationId':'site'}],
   'evses':[{'id':'e','country':'FR','stationId':'s','cpoId':'c','sourceEvseId':'FRZWOE1','officialEvseId':'FRZWOE1'}],
   'connectors':[{'id':'p','evseId':'e','powerKw':22}]}
  self.raw={'id':'old','currency':'EUR','countries':['FR'],'verifiedScope':'exact_evse','directOperatorOnly':True,'evseIds':['FR*ZWO*E1'],'pricing':{'type':'kwh','pricePerKwh':.2}}
  self.a={'zewatt':{'country':'FR','mode':'verified_zewatt_direct','directOffers':[self.raw]}};self.proof={'zewatt':{'generatedAt':'2026-10-14T00:00:00Z'}}
 def test_exact_normalized_identity_retains_raw_and_topology(self):
  d,r=normalize(self.n,self.a,self.proof);self.assertEqual(d['offers'][0]['rawOffer'],self.raw);self.assertEqual(d['evses'],self.n['evses']);self.assertEqual(r['rejections'],[])
 def test_absent_or_ambiguous_no_station_created(self):
  self.n['evses'].append({**self.n['evses'][0],'id':'other','officialEvseId':'FR*ZWO*E1'})
  d,r=normalize(self.n,self.a,self.proof);self.assertFalse(d['stations']);self.assertEqual(r['rejections'][0]['reason'],'national_evse_ambiguous')
  self.raw['evseIds']=['FR*UNKNOWN*E1'];d,r=normalize(self.n,self.a,self.proof);self.assertFalse(d['stations']);self.assertEqual(r['rejections'][0]['reason'],'national_evse_absent')
 def test_conflicting_profiles_preserved_not_ranked(self):
  other=copy.deepcopy(self.raw);other['id']='second';other['pricing']['pricePerKwh']=.3;self.a['zewatt']['directOffers'].append(other)
  d,r=normalize(self.n,self.a,self.proof);self.assertEqual(len(d['offers']),2);self.assertTrue(all(o.get('calculationHold') for o in d['offers']))
 def test_station_scope_rejected(self):
  self.raw['stationIds']=['site']
  with self.assertRaises(ValueError):normalize(self.n,self.a,self.proof)
 def test_preserved_compilers_reproduce_all_profiles_offline(self):
  with tempfile.TemporaryDirectory() as t:
   for family in ('zewatt','zephyre'):
    d,p=replay(family,Path(t));self.assertTrue(d['directOffers']);self.assertEqual(len(p['compiledSha256']),64)
