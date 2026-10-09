#!/usr/bin/env python3
"""Conservative supplementary regression fixtures from actual compiled V9 France
direct/subscription offer catalogs. Data Lab local + PINNED stable runtime
snapshots are distinct sources, not proof of current EVSE validity.
"""
import collections,datetime as dt,hashlib,json,os,pathlib,urllib.request
import tariff_global_inventory_20261009 as inv
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/'reports/tariff-scenarios'
PIN=os.environ.get('TCC_V9_PRICING_SHA','38ac26e029ba1c4779d4d8fa43e7d5d300858624')
FILES=[
 'france-direct-offers.json','france-emsp-offers.json','france-belib-offers.json',
 'france-bump-offers.json','france-e55c-offers.json','france-etotem-offers.json',
 'france-freshmile-offers.json','france-ionity-offers.json','france-izivia-offers.json',
 'france-loadmotion-offers.json','france-qovoltis-offers.json','france-zephyre-offers.json',
 'france-zewatt-offers.json'
]
def slim(offer):
 # Do not copy irrelevant large EVSE lists: they do not change pricing-engine evaluation.
 out={k:v for k,v in offer.items() if k not in ('evseIds','stationIds','connectorIds','aliases')}
 return out
def collect(source,path,doc,fixtures,seen,counts):
 if not isinstance(doc,dict):return
 for name,kind in [('directOffers','CPO direct'),('subscriptionOffers','abonnement'),('emspOffers','eMSP')]:
  vals=doc.get(name) or []
  for offer in vals:
   if not isinstance(offer,dict) or not isinstance(offer.get('pricing'),dict):
    counts['missing_structured_pricing']+=1;continue
   pricing=offer['pricing'];typ=str(pricing.get('type') or 'unknown')
   rules=pricing.get('rules') or []
   fields=set(pricing)
   for rule in rules:
    if isinstance(rule,dict):fields.update(rule)
   fam=sorted(set().union(*(inv.family(k) for k in fields)))
   sig=kind+'|'+typ+'|'+','.join(fam)+'|'+','.join(sorted(fields))
   signature=hashlib.sha1(sig.encode()).hexdigest()[:12]
   # Source scope and publication status MUST remain visible.
   key=(source,path,kind,signature)
   counts[source+'/'+kind+'/total_offer_rows']+=1
   if seen[key]>=20:continue
   seen[key]+=1
   fixture={'provider':kind+' — '+str(offer.get('provider') or 'unknown'),
    'offerId':offer.get('id'),'tariffType':typ,'families':fam,
    'signatureId':signature,'origin':source+'/'+path,
    'runtimeVintage':'stable_pinned' if source=='stable_v9' else 'datalab_local',
    'offer':slim(offer)}
   fixtures.append(fixture)
def main():
 fixtures=[];seen=collections.Counter();counts=collections.Counter()
 for p in sorted((ROOT/'v9-production-runtime/data/v9').glob('france-*offers.json')):
  try:doc=json.loads(p.read_text(encoding='utf8'));collect('datalab_v9',p.name,doc,fixtures,seen,counts)
  except (OSError,ValueError):counts['bad_local_json']+=1
 for filename in FILES:
  url=f'https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable/{PIN}/v9-production-runtime/data/v9/{filename}'
  try:
   with urllib.request.urlopen(url,timeout=40) as f:payload=f.read(9000000)
   doc=json.loads(payload)
   collect('stable_v9',filename,doc,fixtures,seen,counts)
  except Exception as e:
   counts['stable_download_failed']+=1;print('runtime_offers_fetch_warning='+filename+':'+str(e)[:100])
 (DEST/'france-runtime-offer-fixtures.json').write_text(inv.jdump(fixtures),encoding='utf8')
 report={'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'enginePin':PIN,'fixtures':len(fixtures),
         'counts':dict(counts),'interpretation':'Pinned V9 snapshot for regression, NOT current tariff truth or new verified EVSE tariffs'}
 (DEST/'france-runtime-offers-inventory.json').write_text(inv.jdump(report),encoding='utf8')
 print('FRANCE_RUNTIME_FIXTURES='+json.dumps(report))
if __name__=='__main__':main()
