#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,io,json,re,urllib.request
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

SOURCE='https://www.data.gouv.fr/api/1/datasets/r/775dd5a9-c0e4-4bb7-8995-f4b5a4148836'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def value(row,*names):
    d={str(k).strip().lower():(v or '').strip() for k,v in row.items() if k is not None}
    for n in names:
        if d.get(n.lower()): return d[n.lower()]
    return ''
def number(s):
    m=re.search(r'-?\d+(?:[,.]\d+)?',s or '')
    return float(m.group(0).replace(',','.')) if m else None
def network_class(row):
    op=value(row,'nom_operateur','operateur','operator')
    name=value(row,'nom_station','n_station','station_name')
    h=(op+' '+name).lower()
    if 'partner network' in h or 'powered by driveco' in h: return 'partner_network'
    return 'driveco_network' if 'driveco' in h else 'other_or_unspecified'
def parse_tariff(raw):
    if not raw: return None
    s=raw.strip()
    # Publisher CSV currently escapes embedded JSON as doubled quotes and may wrap it in quotes.
    for candidate in (s, s.strip('"').replace('""','"')):
        try:
            obj=json.loads(candidate)
            if isinstance(obj,str): obj=json.loads(obj)
            if isinstance(obj,dict): return obj
        except Exception: pass
    # Last-resort field extraction: never invent values not present in the published string.
    def f(key):
        m=re.search(rf'"?{re.escape(key)}"?\s*:\s*(-?\d+(?:[.,]\d+)?)',s)
        return float(m.group(1).replace(',','.')) if m else None
    ep=f('energyPrice')
    if ep is None:return None
    return {'energyPrice':ep,'fixedPrice':f('fixedPrice'),'minimumBilling':f('minimumBilling'),'rawUnparsed':s}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/driveco-evse');args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(SOURCE,headers={'User-Agent':UA,'Accept':'text/csv,*/*;q=0.8'})
    with urllib.request.urlopen(req,timeout=60) as r: raw=r.read()
    text=raw.decode('utf-8-sig',errors='replace')
    try: dialect=csv.Sniffer().sniff(text[:20000],delimiters=',;\t'); rows=list(csv.DictReader(io.StringIO(text),dialect=dialect))
    except csv.Error: rows=list(csv.DictReader(io.StringIO(text),delimiter=';'))
    assert len(rows)>1000
    resolved=[];unresolved=[];counts=Counter();prices=Counter()
    for row in rows:
        cls=network_class(row);counts[cls]+=1
        evse=value(row,'id_pdc_itinerance','id_pdc_local','id_pdc') or None
        sid=value(row,'id_station_itinerance','id_station_local','id_station') or None
        item={
          'evseId':evse,'stationId':sid,'networkClass':cls,
          'operator':value(row,'nom_operateur','operateur','operator') or None,
          'stationName':value(row,'nom_station','n_station','station_name') or None,
          'address':value(row,'adresse_station','adresse','address') or None,
          'postalCode':value(row,'code_postal','code_postal_station','postal_code') or None,
          'city':value(row,'consolidated_commune','nom_commune','commune','ville') or None,
          'powerKw':number(value(row,'puissance_nominale','puissance_nominale_kw','power')),
        }
        tariff_raw=value(row,'tarification','tarif','pricing','price')
        tariff=parse_tariff(tariff_raw)
        if tariff and isinstance(tariff.get('energyPrice'),(int,float)):
            item['tariff']={
              'energyPriceEurPerKwh':float(tariff['energyPrice']),
              'fixedPriceEur':tariff.get('fixedPrice'),
              'minimumBillingEur':tariff.get('minimumBilling'),
              'matrix':tariff.get('matrix',[]),
              'matrixOSF':tariff.get('matrixOSF',[]),
              'hasDynamicTarif':tariff.get('hasDynamicTarif'),
              'ecoHour':tariff.get('ecoHour'),
              'rawPublished':tariff_raw,
            }
            item['feeSemantics']={'matrixOSF':'published_raw_not_yet_interpreted','safeForEnergyPrice':True,'safeForFullSessionCost':False if tariff.get('matrixOSF') else True}
            resolved.append(item);prices[(cls,float(tariff['energyPrice']))]+=1
        else:
            item['unresolvedReason']='official_driveco_irve_row_has_no_machine_readable_tarification'
            unresolved.append(item)
    payload={
      'schemaVersion':'1.0.0','dataset':'driveco-evse-direct-tariffs','generatedAt':now(),'source':SOURCE,
      'policy':{'operatorDirectOnly':True,'roamingExcluded':True,'referencePricesNeverUsedAsFallback':True,'matrixOSFNotInterpretedUntilSemanticsValidated':True},
      'summary':{'rowCount':len(rows),'networkClassRows':dict(counts),'resolvedEnergyPriceRows':len(resolved),'unresolvedRows':len(unresolved),'resolvedByNetworkAndEnergyPrice':[{'networkClass':k[0],'energyPriceEurPerKwh':k[1],'rows':v} for k,v in sorted(prices.items())]},
      'resolved':resolved,'unresolved':unresolved
    }
    (out/'driveco_evse_tariffs.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    summary=['# DRIVECO EVSE direct tariff base','',f'- Official rows: **{len(rows)}**',f'- Energy price resolved: **{len(resolved)}**',f'- Unresolved: **{len(unresolved)}**','', '## Resolved distribution']
    for x in payload['summary']['resolvedByNetworkAndEnergyPrice']:summary.append(f"- {x['networkClass']} — {x['energyPriceEurPerKwh']:.2f} €/kWh: **{x['rows']} EVSE**")
    summary += ['', '> `matrixOSF` is retained verbatim and is not yet converted to a TCC fee rule. Reference headline prices are never used as a fallback.']
    (out/'SUMMARY.md').write_text('\n'.join(summary)+'\n',encoding='utf-8')
    print('\n'.join(summary))
if __name__=='__main__': main()
