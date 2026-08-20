#!/usr/bin/env python3
"""Test whether e-Vadea direct tariffs can be resolved exactly from public station metadata.

Safety: public unauthenticated GET only; no account/payment/session actions; raw bodies are not persisted.
"""
from __future__ import annotations
import csv, hashlib, io, json, re, ssl, unicodedata, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
INVENTORY="https://www.data.gouv.fr/api/1/datasets/r/29f5db7c-5148-4353-a78c-25085a119394"
MAP="https://www.e-vadea.fr/fr/carte-des-bornes"
MOTORWAY_RE=re.compile(r"(?:\bA\s?\d{1,3}\b|\bautoroute\b|\baire\s+(?:de|d['’])|\baires?\s+de\s+service\b|\baires?\s+de\s+repos\b|\bp[eé]age\b)",re.I)
OFFROAD_RE=re.compile(r"(?:\brue\b|\bavenue\b|\bboulevard\b|\broute\s+de\b|\bchemin\b|\bparking\b|\bcentre\b|\bzone\b|\bzac\b|\bza\b|\bplace\b)",re.I)


def now_iso(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def get(url,limit=12_000_000):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,text/csv,application/json,*/*;q=0.8','Cache-Control':'no-cache'},method='GET')
 with urllib.request.urlopen(req,timeout=45,context=ssl.create_default_context()) as r:
  raw=r.read(limit); return int(getattr(r,'status',200)),r.geturl(),r.headers.get('Content-Type','').split(';',1)[0].lower(),raw

def norm_key(value):
 s=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode('ascii').lower().strip()
 return re.sub(r'[^a-z0-9]+','_',s).strip('_')

def pick(row,*names):
 lower={norm_key(k):v for k,v in row.items()}
 for n in names:
  key=norm_key(n)
  if key in lower and lower[key] not in (None,''): return str(lower[key]).strip()
 return ''

def norm_evse(s): return re.sub(r'[^A-Z0-9]','',str(s).upper())
def parse_power(row):
 raw=pick(row,'puiss_max','puissance_nominale','power','puissance','puiss_max_kw','puissance_maximale')
 m=re.search(r'\d+(?:[.,]\d+)?',raw)
 return float(m.group(0).replace(',','.')) if m else None

def tariff(context,power):
 if power is None: return None
 if context=='motorway': return 0.48 if power < 100 else 0.62
 if context=='off_motorway':
  if power < 30: return 0.40
  if power < 60: return 0.48
  return 0.58
 return None

def classify(text):
 if MOTORWAY_RE.search(text): return 'motorway','high'
 if OFFROAD_RE.search(text): return 'off_motorway','medium'
 return 'unknown','none'

def parse_inventory(raw):
 expected=('station','pdc','puissance','adresse','enseigne')
 encodings=['utf-8-sig','utf-16','cp1252']
 best=None
 for enc in encodings:
  try: text=raw.decode(enc)
  except Exception: continue
  first=(text.splitlines() or [''])[0]
  delimiters=[',',';','\t','|']
  delimiter=max(delimiters,key=lambda d:first.count(d))
  try:
   reader=csv.DictReader(io.StringIO(text),delimiter=delimiter)
   rows=list(reader)
   fields=[str(x or '') for x in (reader.fieldnames or [])]
  except Exception:
   continue
  normalized=[norm_key(x) for x in fields]
  score=sum(1 for token in expected if any(token in f for f in normalized))
  candidate=(score,len(fields),len(rows),enc,delimiter,fields,rows)
  if best is None or candidate[:3] > best[:3]: best=candidate
 if best is None: raise ValueError('unable to parse public inventory CSV')
 score,_,_,enc,delimiter,fields,rows=best
 return rows,fields,enc,delimiter,score

def main():
 out=Path('out/exact-price/evadea'); out.mkdir(parents=True,exist_ok=True)
 errors=[]; map_meta={}; map_markers=[]
 try:
  s,final,ctype,raw=get(MAP,4_000_000); text=raw.decode('utf-8',errors='replace').lower()
  map_meta={'url':MAP,'finalUrl':final,'httpStatus':s,'contentType':ctype,'bytesRead':len(raw),'contentSha256':hashlib.sha256(raw).hexdigest()}
  map_markers=[k for k in ('station','borne','tarif','price','map','api','json','evse','autoroute') if k in text]
 except Exception as e: errors.append({'url':MAP,'errorType':type(e).__name__,'message':str(e)[:180]})
 try:
  s,final,ctype,raw=get(INVENTORY)
 except Exception as e:
  raise SystemExit(f'inventory fetch failed: {e}')
 rows,field_names,encoding,delimiter,parse_score=parse_inventory(raw)
 classified=[]; counts={'motorway':0,'off_motorway':0,'unknown':0}; exact=0; evses=set(); high=0
 populated={'name':0,'address':0,'evse':0,'power':0}
 for row in rows:
  name=pick(row,'nom_station','nom_enseigne','n_station','station_name','nom_borne')
  addr=pick(row,'ad_station','adresse_station','address','adresse','implantation_station')
  evse=pick(row,'id_pdc_itinerance','id_pdc_local','evse_id','id_pdc')
  p=parse_power(row)
  if name: populated['name']+=1
  if addr: populated['address']+=1
  if evse: populated['evse']+=1
  if p is not None: populated['power']+=1
  extra=pick(row,'implantation_station','observations')
  context,confidence=classify(f'{name} {addr} {extra}')
  counts[context]+=1
  if confidence=='high': high+=1
  price=tariff(context,p)
  if price is not None: exact+=1
  if evse: evses.add(norm_evse(evse))
  if len(classified)<40 or (context=='unknown' and len([x for x in classified if x['context']=='unknown'])<12):
   classified.append({'stationName':name[:160],'address':addr[:220],'evseId':evse[:80],'powerKw':p,'context':context,'confidence':confidence,'resolvedEurPerKwh':price})
 payload={
  'schemaVersion':'1.1.0','dataset':'evadea-context-exact-price-discovery','generatedAt':now_iso(),
  'method':{'authenticated':False,'mobilePackageUsed':False,'paymentSubmitted':False,'chargingSessionStarted':False,'persistRawBodies':False,'httpMethods':['GET']},
  'map':map_meta,'mapSemanticMarkers':map_markers,
  'inventory':{'url':INVENTORY,'httpStatus':s,'contentType':ctype,'bytesRead':len(raw),'contentSha256':hashlib.sha256(raw).hexdigest(),'rowCount':len(rows),'uniqueEvseIds':len(evses),'contextCounts':counts,'highConfidenceContextRows':high,'exactTariffResolvableRows':exact,'exactTariffResolvablePercent':round(100*exact/len(rows),2) if rows else 0,'csvEncoding':encoding,'csvDelimiter':delimiter,'fieldNames':[norm_key(x) for x in field_names][:80],'headerSemanticScore':parse_score,'populatedCanonicalFields':populated},
  'samples':classified,
  'tariffRuleUsed':{'motorway':{'lt100':0.48,'gte100':0.62},'offMotorway':{'lt30':0.40,'gte30lt60':0.48,'gte60':0.58}},
  'conclusion':{
    'publicInventoryUsable':bool(rows) and populated['evse']>0,
    'roadContextDerivableForAllRows':counts['unknown']==0,
    'exactTariffResolvableForAllRows':exact==len(rows) and bool(rows),
    'safePartialResolverPossible':exact>0 and populated['evse']>0,
    'nextStep':'build EVSE-level e-Vadea exact-price overlay only for resolved records; leave unknown records reference-only' if exact>0 and populated['evse']>0 else 'keep e-Vadea reference-only; public metadata does not resolve enough station context safely'
  },
  'errors':errors
 }
 (out/'evadea_context_exact_price_probe.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (out/'SUMMARY.md').write_text('# e-Vadea context exact-price discovery\n\n'+f"- Inventory rows: **{len(rows)}**\n- Parsed EVSE IDs: **{populated['evse']}**\n- Parsed powers: **{populated['power']}**\n- Motorway: **{counts['motorway']}**\n- Off-motorway: **{counts['off_motorway']}**\n- Unknown context: **{counts['unknown']}**\n- Exact tariff resolvable: **{exact}/{len(rows)}** ({payload['inventory']['exactTariffResolvablePercent']}%)\n- Next step: {payload['conclusion']['nextStep']}\n",encoding='utf-8')

if __name__=='__main__': main()
