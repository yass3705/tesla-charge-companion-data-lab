#!/usr/bin/env python3
"""Validate the small e-Vadea off-motorway subset from the official public IRVE inventory.

Safety: public unauthenticated GET only; no account/payment/session actions; raw CSV is not persisted.
"""
from __future__ import annotations
import csv, hashlib, io, json, re, ssl, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
INVENTORY="https://www.data.gouv.fr/api/1/datasets/r/29f5db7c-5148-4353-a78c-25085a119394"
MOTORWAY_RE=re.compile(r"(?:\bA\s?\d{1,3}\b|\bautoroute\b|\baire\s+(?:de|d['’])|\baires?\s+de\s+service\b|\baires?\s+de\s+repos\b|\bp[eé]age\b)",re.I)
OFFROAD_RE=re.compile(r"(?:\brue\b|\bavenue\b|\bboulevard\b|\broute\s+de\b|\bchemin\b|\bparking\b|\bcentre\b|\bzone\b|\bzac\b|\bza\b|\bplace\b)",re.I)

def now_iso(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def get(url,limit=12_000_000):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/csv,*/*;q=0.8','Cache-Control':'no-cache'},method='GET')
 with urllib.request.urlopen(req,timeout=45,context=ssl.create_default_context()) as r:
  raw=r.read(limit); return int(getattr(r,'status',200)),r.headers.get('Content-Type','').split(';',1)[0].lower(),raw

def norm_key(s):
 s=str(s or '').replace('\ufeff','').strip().lower()
 return re.sub(r'[^a-z0-9]+','_',s).strip('_')

def decode_csv(raw):
 candidates=[]
 for enc in ('utf-8-sig','utf-8','cp1252','latin-1'):
  try:
   text=raw.decode(enc)
  except UnicodeDecodeError:
   continue
  first=text.splitlines()[0] if text.splitlines() else ''
  for delim in (';',',','\t'):
   score=first.count(delim)
   if score: candidates.append((score,enc,delim,text))
 if not candidates: raise RuntimeError('unable to detect CSV encoding/delimiter')
 _,enc,delim,text=max(candidates,key=lambda x:x[0])
 reader=csv.DictReader(io.StringIO(text),delimiter=delim)
 rows=[]
 for row in reader:
  rows.append({norm_key(k): ('' if v is None else str(v).strip()) for k,v in row.items()})
 return enc,delim,rows

def pick(row,*names):
 for n in names:
  v=row.get(norm_key(n),'')
  if v: return v
 return ''

def parse_power(row):
 raw=pick(row,'puissance_nominale','puiss_max','power','puissance','puiss_max_kw')
 m=re.search(r'\d+(?:[.,]\d+)?',raw)
 return float(m.group(0).replace(',','.')) if m else None

def matched(rx,text):
 return sorted({m.group(0).strip() for m in rx.finditer(text)})

def tariff(power):
 if power is None: return None
 if power < 30: return 0.40
 if power < 60: return 0.48
 return 0.58

def main():
 status,ctype,raw=get(INVENTORY)
 enc,delim,rows=decode_csv(raw)
 selected=[]
 for row in rows:
  name=pick(row,'nom_station','nom_enseigne')
  addr=pick(row,'adresse_station','ad_station','adresse')
  text=f'{name} {addr}'
  mw=matched(MOTORWAY_RE,text)
  off=matched(OFFROAD_RE,text)
  if mw or not off: continue
  evse=pick(row,'id_pdc_itinerance','id_pdc_local','id_pdc')
  station_id=pick(row,'id_station_itinerance','id_station_local')
  power=parse_power(row)
  selected.append({
   'stationId':station_id[:100],
   'stationName':name[:180],
   'address':addr[:240],
   'evseId':evse[:100],
   'powerKw':power,
   'implantationStation':pick(row,'implantation_station')[:120],
   'publishedTarificationField':pick(row,'tarification')[:220],
   'offMotorwayEvidence':off,
   'motorwayEvidence':mw,
   'resolvedEurPerKwhFromCurrentOfficialGrid':tariff(power)
  })
 groups=defaultdict(list)
 for x in selected: groups[x['stationId'] or x['stationName']].append(x)
 station_groups=[]; conflicts=[]
 for key,items in groups.items():
  names=sorted({x['stationName'] for x in items})
  addrs=sorted({x['address'] for x in items})
  has_missing=any(not x['evseId'] or x['powerKw'] is None for x in items)
  station_groups.append({'key':key,'rows':len(items),'names':names,'addresses':addrs,'allRowsHaveEvseAndPower':not has_missing})
  if has_missing: conflicts.append({'key':key,'reason':'missing EVSE or power'})
 payload={
  'schemaVersion':'1.0.0','dataset':'evadea-offmotorway-validation','generatedAt':now_iso(),
  'method':{'authenticated':False,'mobilePackageUsed':False,'paymentSubmitted':False,'chargingSessionStarted':False,'persistRawBodies':False,'httpMethods':['GET']},
  'inventory':{'url':INVENTORY,'httpStatus':status,'contentType':ctype,'bytesRead':len(raw),'contentSha256':hashlib.sha256(raw).hexdigest(),'rowCount':len(rows),'csvEncoding':enc,'csvDelimiter':delim},
  'offMotorwayRows':selected,
  'stationGroups':station_groups,
  'conflicts':conflicts,
  'conclusion':{
   'offMotorwayRowsFound':len(selected),
   'offMotorwayStationGroupsFound':len(station_groups),
   'allRowsHavePositiveOffMotorwayEvidence':all(bool(x['offMotorwayEvidence']) for x in selected) and bool(selected),
   'allRowsHaveNoMotorwayEvidence':all(not x['motorwayEvidence'] for x in selected) and bool(selected),
   'allRowsHaveEvseAndPower':all(bool(x['evseId']) and x['powerKw'] is not None for x in selected) and bool(selected),
   'safeForEvseContextMapping':bool(selected) and not conflicts and all(bool(x['offMotorwayEvidence']) and not x['motorwayEvidence'] and bool(x['evseId']) for x in selected)
  }
 }
 out=Path('out/exact-price/evadea-offmotorway'); out.mkdir(parents=True,exist_ok=True)
 (out/'evadea_offmotorway_validation.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (out/'SUMMARY.md').write_text('# e-Vadea off-motorway validation\n\n'+f"- Off-motorway rows: **{len(selected)}**\n- Station groups: **{len(station_groups)}**\n- Conflicts: **{len(conflicts)}**\n- Safe for EVSE context mapping: **{payload['conclusion']['safeForEvseContextMapping']}**\n",encoding='utf-8')
if __name__=='__main__': main()
