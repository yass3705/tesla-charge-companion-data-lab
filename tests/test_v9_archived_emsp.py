import copy,gzip,hashlib,json,tempfile,unittest
from pathlib import Path
from scripts.build_v9_archived_emsp import normalize,read_archive

class ArchivedEmspTest(unittest.TestCase):
 def setUp(self):
  self.n={'source':{'id':'FR:irve_static'},'cpos':[{'id':'c','country':'FR','sourceOperatorId':'CPO'}],
   'stations':[{'id':'s','country':'FR','cpoId':'c','sourceStationId':'source-site'}],
   'evses':[{'id':'e','country':'FR','stationId':'s','cpoId':'c','sourceEvseId':'FRABCE1','officialEvseId':'FRABCE1'}],
   'connectors':[{'id':'p','evseId':'e','powerKw':22,'officialConnectorId':None}]}
  self.raw={'id':'archived','provider':'Electroverse','currency':'EUR','verifiedScope':'exact_evse','evseIds':['FR*ABC*E1'],
   'metadata':{'verified':True,'identityMode':'exact_unique_national_irve_pdc'},'pricing':{'type':'rules','rules':[{'pricePerKwh':.5,'connectionFee':1,'unknownFee':2}]}}
  self.proof={'nationalSha256':'a'*64,'archiveManifestSha256':'b'*64,'identityContract':'historical_normalized_official_evse_unique'}
 def build(self,rows=None):return normalize(self.n,'Electroverse',rows or [self.raw],self.proof)
 def test_normalization_retains_exact_ids_all_components_and_national_topology(self):
  d,r=self.build();o=d['offers'][0]
  self.assertEqual(o['officialEvseId'],'FRABCE1');self.assertEqual(o['sourceEvseId'],'FR*ABC*E1')
  self.assertEqual(o['rawOffer'],self.raw);self.assertEqual(d['connectors'],self.n['connectors'])
  self.assertEqual(o['scope'],{'evseId':'e','connectorId':None});self.assertEqual(r['rejections'],[])
 def test_ambiguous_and_absent_identity_never_create_a_station(self):
  self.n['evses'].append({**self.n['evses'][0],'id':'e2','officialEvseId':'FR*ABC*E1'})
  d,r=self.build();self.assertEqual(d['stations'],[]);self.assertEqual(r['rejections'][0]['reason'],'national_evse_ambiguous')
  self.raw['evseIds']=['FR*OTHER*E1'];d,r=self.build();self.assertEqual(r['rejections'][0]['reason'],'national_evse_absent')
 def test_station_broadcast_not_silently_accepted(self):
  self.raw['metadata']['identityMode']='strict_station_homogeneous_price_broadcast'
  d,r=self.build();self.assertEqual(d['offers'],[]);self.assertTrue(r['rejections'])
 def test_identical_duplicates_dedup_but_conflicting_duplicates_quarantined(self):
  d,r=self.build([self.raw,copy.deepcopy(self.raw)]);self.assertEqual(len(d['offers']),1);self.assertEqual(r['identicalDuplicateRows'],1)
  other=copy.deepcopy(self.raw);other['pricing']['rules'][0]['pricePerKwh']=.9
  d,r=self.build([self.raw,other]);self.assertEqual(d['offers'],[]);self.assertEqual(r['rejections'][0]['reason'],'conflicting_duplicate_source_offer')
 def test_different_source_ids_conflicting_at_same_evse_are_visible_but_held(self):
  other=copy.deepcopy(self.raw);other['id']='second';other['pricing']['rules'][0]['pricePerKwh']=.9
  d,r=self.build([self.raw,other]);self.assertEqual(len(d['offers']),2)
  self.assertTrue(all(o['calculationHold']=='conflicting_tariffs_for_same_evse' for o in d['offers']))
 def test_electra_requires_source_evse_and_keeps_restrictions_out_of_calculation(self):
  raw=copy.deepcopy(self.raw);raw.update(provider='Electra');raw['metadata']={'verified':True,'verifiedScope':'exact_evse','identityMode':'exact_national_irve_evse','electraLocationId':'loc'}
  loc={'evses':[{'evseId':'FR*ABC*E1'}],'chargeTariffs':[{'elements':[{'restrictions':{'minKwh':10}}]}]}
  d,r=normalize(self.n,'Electra',[raw],self.proof,{'loc':loc})
  self.assertEqual(d['offers'][0]['calculationHold'],'unpreserved_source_restrictions')
  loc['evses']=[];d,r=normalize(self.n,'Electra',[raw],self.proof,{'loc':loc});self.assertEqual(d['offers'],[])
 def test_archive_hash_and_internal_count_not_historical_volume(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);raw=gzip.compress(json.dumps({'schemaVersion':1,'country':'FR','emspOffers':[self.raw]}).encode());(p/'t_1_2.json.gz').write_bytes(raw)
   m={'schemaVersion':1,'country':'FR','dataset':'electroverse-france-evse-national-overlay','tileCount':1,'tiles':[{'file':'t_1_2.json.gz','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'count':1}]}
   (p/'manifest.json').write_text(json.dumps(m));self.assertEqual(len(read_archive(p,'Electroverse')[2]),1)
   m['tiles'][0]['count']=2;(p/'manifest.json').write_text(json.dumps(m))
   with self.assertRaisesRegex(ValueError,'internal count'):read_archive(p,'Electroverse')
   m['tiles'][0]['sha256']='0'*64;(p/'manifest.json').write_text(json.dumps(m))
   with self.assertRaisesRegex(ValueError,'integrity'):read_archive(p,'Electroverse')
