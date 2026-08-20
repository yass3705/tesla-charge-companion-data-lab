#!/usr/bin/env python3
"""Test whether e-Vadea direct tariffs can be resolved exactly from public station metadata.

Safety: public unauthenticated GET only; no account/payment/session actions; raw bodies are not persisted.
"""
from __future__ import annotations
import csv, hashlib, io, json, re, ssl, urllib.request
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

def pick(row,*names):
 lower={str(k).lower().strip():v for k,v in row.items()}
 for n in names:
  if n.lower() in lower and lower[n.lower()] not in (None,''): return str(lower[n.lower()]).strip()
 return ''

def norm_evse(s): return re.sub(r'[^A-Z0-9]','',str(s).upper())
def parse_power(row):
 raw=pick(row,'puiss_max','puissance_nominale','power','puissance','puiss_max_kw')
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
 text=raw.decode('utf-8-sig',errors='replace')
 sample=text[:4096]
 try: dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
 except Exception: dialect=csv.excel
 rows=list(csv.DictReader(io.StringIO(text),dialect=dialect))
 classified=[]; counts={'motorway':0,'off_motorway':0,'unknown':0}; exact=0; evses=set(); high=0
 for row in rows:
  name=pick(row,'nom_station','nom_enseigne','n_station','station_name','nom_borne')
  addr=pick(row,'ad_station','adresse_station','address','adresse')
  evse=pick(row,'id_pdc_itinerance','id_pdc_local','evse_id','id_pdc')
  p=parse_power(row)
  context,confidence=classify(f'{name} {addr}')
  counts[context]+=1
  if confidence=='high': high+=1
  price=tariff(context,p)
  if price is not None: exact+=1
  if evse: evses.add(norm_evse(evse))
  if len(classified)<40 or (context=='unknown' and len([x for x in classified if x['context']=='unknown'])<12):
   classified.append({'stationName':name[:160],'address':addr[:220],'evseId':evse[:80],'powerKw':p,'context':context,'confidence':confidence,'resolvedEurPerKwh':price})
 payload={
  'schemaVersion':'1.0.0','dataset':'evadea-context-exact-price-discovery','generatedAt':now_iso(),
  'method':{'authenticated':False,'mobilePackageUsed':False,'paymentSubmitted':False,'chargingSessionStarted':False,'persistRawBodies':False,'httpMethods':['GET']},
  'map':map_meta,'mapSemanticMarkers':map_markers,
  'inventory':{'url':INVENTORY,'httpStatus':s,'contentType':ctype,'bytesRead':len(raw),'contentSha256':hashlib.sha256(raw).hexdigest(),'rowCount':len(rows),'uniqueEvseIds':len(evses),'contextCounts':counts,'highConfidenceContextRows':high,'exactTariffResolvableRows':exact,'exactTariffResolvablePercent':round(100*exact/len(rows),2) if rows else 0},
  'samples':classified,
  'tariffRuleUsed':{'motorway':{'lt100':0.48,'gte100':0.62},'offMotorway':{'lt30':0.40,'gte30lt60':0.48,'gte60':0.58}},
  'conclusion':{
    'publicInventoryUsable':bool(rows),
    'roadContextDerivableForAllRows':counts['unknown']==0,
    'exactTariffResolvableForAllRows':exact==len(rows) and bool(rows),
    'safePartialResolverPossible':exact>0,
    'nextStep':'build EVSE-level e-Vadea exact-price overlay only for high/medium-confidence resolved records; leave unknown records reference-only' if exact>0 else 'keep e-Vadea reference-only; public metadata does not resolve road context safely'
  },
  'errors':errors
 }
 (out/'evadea_context_exact_price_probe.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (out/'SUMMARY.md').write_text('# e-Vadea context exact-price discovery\n\n'+f"- Inventory rows: **{len(rows)}**\n- Motorway: **{counts['motorway']}**\n- Off-motorway: **{counts['off_motorway']}**\n- Unknown context: **{counts['unknown']}**\n- Exact tariff resolvable: **{exact}/{len(rows)}** ({payload['inventory']['exactTariffResolvablePercent']}%)\n- Next step: {payload['conclusion']['nextStep']}\n",encoding='utf-8')

if __name__=='__main__': main()
