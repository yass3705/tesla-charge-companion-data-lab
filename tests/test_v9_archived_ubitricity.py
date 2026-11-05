import copy,gzip,json,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.build_v9_archived_ubitricity_uk import restore,normalize_uk_ocpi_pair,sha,ROOT

class ArchivedUbitricity(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  raw=json.loads(gzip.decompress((ROOT/'data/national/uk_ubitricity_pcpr.json.gz').read_bytes()))
  compiled=json.loads(gzip.decompress((ROOT/'data/national/uk_ubitricity_v9.json.gz').read_bytes()))
  loc=next(l for l in compiled['sources'][0]['locations'] if any(c.get('validatedV9Offer') for e in l['evses'] for c in e['connectors']))
  raw['locations']=[l for l in raw['locations'] if l['id']==loc['id']]
  tids={t for l in raw['locations'] for e in l['evses'] for c in e['connectors'] for t in c['tariff_ids']}
  raw['tariffs']=[t for t in raw['tariffs'] if t['id'] in tids]
  compiled['sources'][0]['locations']=[loc]
  cls.r,cls.c=raw,compiled
 def build(self,r=None,c=None):
  r=r or self.r;c=c or self.c
  canonical=normalize_uk_ocpi_pair(r,artifact_sha256='a'*64,source_id='GB:ubitricity_pcpr_direct')
  with patch('urllib.request.urlopen',side_effect=AssertionError('Network forbidden')):
   return restore(canonical,r,c,'a'*64,'b'*64)
 def test_exact_archived_scope_and_no_network(self):
  d,r=self.build();self.assertGreater(r['compiledOffersRestored'],0)
  for o in d['offers']:
   if o.get('proof'):self.assertEqual(o['archivedCompiledOffer']['metadata']['tariffId'],o['sourceTariffKey'])
 def test_changed_compilation_or_date_rejected(self):
  c=copy.deepcopy(self.c);c['collectedAt']='other'
  with self.assertRaises(ValueError):self.build(c=c)
  c=copy.deepcopy(self.c)
  o=next(c for l in c['sources'][0]['locations'] for e in l['evses'] for c in e['connectors'] if c.get('validatedV9Offer'))['validatedV9Offer']
  o['pricing']['rules'][0]['pricePerKwh']=.01
  with self.assertRaisesRegex(ValueError,'differs'):self.build(c=c)
 def test_unknown_component_never_silently_dropped(self):
  r=copy.deepcopy(self.r)
  for t in r['tariffs']:t['elements'][0]['price_components'].append({'type':'UNKNOWN','price':1,'step_size':1,'vat':20})
  with self.assertRaises(ValueError):self.build(r=r)
 def test_uncompiled_retains_raw_without_price(self):
  c=copy.deepcopy(self.c)
  for l in c['sources'][0]['locations']:
   for e in l['evses']:
    for plug in e['connectors']:plug.pop('validatedV9Offer',None)
  d,r=self.build(c=c);self.assertEqual(r['compiledOffersRestored'],0)
  self.assertTrue(all(o.get('rawOffer') and o.get('calculationHold') for o in d['offers']))
