#!/usr/bin/env python3
"""Probe Wirelane public direct-payment pages from BNetzA EVSE identifiers.

Wirelane prices are station/EVSE specific. This script samples unique BNetzA
physical sites and queries one DE*WLN* EVSE per site to validate whether the
public direct-payment surface is suitable for national tariff extraction.
"""
from __future__ import annotations
import argparse,gzip,html,json,re,time,urllib.parse,urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'
BASE='https://direct.wirelane.com/{evse}?_locale=de'
OPERATOR='Wirelane Public 1'

def load_gz(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)
def textify(raw):
    s=raw.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s).replace('\xa0',' ')).strip()
def fetch(evse):
    url=BASE.format(evse=urllib.parse.quote(evse,safe=''))
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'de-DE,de;q=0.9'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:raw=r.read();status=getattr(r,'status',200)
        text=textify(raw)
        # Capture the tariff sentence between the connector descriptor and operator marker.
        m=re.search(r'(?:max\.\s*[0-9.,]+\s*kW)\s+(.{1,500}?)\s+(?:Betreiber|Provider)\s+Wirelane\s+GmbH',text,re.I)
        tariff=(m.group(1).strip() if m else None)
        # Basic structured tokens; keep raw sentence as authority.
        kwh=None;start_fee=None;minute_fee=None;after_min=None;cap=None
        if tariff:
            mk=re.search(r'([0-9]+(?:[,.][0-9]+)?)\s*(?:€|EUR|ct)\s*/?\s*kWh',tariff,re.I)
            if mk:
                val=float(mk.group(1).replace(',','.'))
                if re.search(re.escape(mk.group(1))+r'\s*ct',tariff,re.I):val/=100
                kwh=round(val,6)
            ms=re.search(r'(?:zzgl\.|\+)\s*([0-9]+(?:[,.][0-9]+)?)\s*€\s*(?:Startgebühr|Start)',tariff,re.I)
            if ms:start_fee=float(ms.group(1).replace(',','.'))
            mm=re.search(r'([0-9]+(?:[,.][0-9]+)?)\s*(?:€|EUR|ct)\s*/?\s*Min',tariff,re.I)
            if mm:
                val=float(mm.group(1).replace(',','.'))
                if re.search(re.escape(mm.group(1))+r'\s*ct',tariff,re.I):val/=100
                minute_fee=round(val,6)
            ma=re.search(r'(?:ab|nach)\s*([0-9]+)\s*Min',tariff,re.I)
            if ma:after_min=int(ma.group(1))
            mc=re.search(r'max\.?\s*([0-9]+(?:[,.][0-9]+)?)\s*€',tariff,re.I)
            if mc:cap=float(mc.group(1).replace(',','.'))
        return {'evseId':evse,'url':url,'status':status,'tariffText':tariff,'eurPerKwh':kwh,'startFeeEur':start_fee,'minuteFeeEur':minute_fee,'afterMinutes':after_min,'capEur':cap,'bytes':len(raw)}
    except Exception as exc:
        return {'evseId':evse,'url':url,'error':f'{type(exc).__name__}: {exc}'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--catalog',type=Path,default=Path('data/germany/germany_non_tesla_catalog_staging_tariff_classified.json.gz'));ap.add_argument('--limit',type=int,default=150);ap.add_argument('--workers',type=int,default=8);ap.add_argument('--output',type=Path,default=Path('data/germany/wirelane_direct_probe.json'));args=ap.parse_args()
    d=load_gz(args.catalog)
    candidates=[]
    for s in d.get('sites') or []:
        if s.get('operator')!=OPERATOR:continue
        evses=[e for e in (s.get('evseIds') or []) if str(e).upper().startswith('DE*WLN*')]
        if not evses:continue
        candidates.append({'siteId':s['id'],'evseId':sorted(evses)[0],'address':s.get('address')})
    candidates=candidates[:args.limit]
    by_evse={c['evseId']:c for c in candidates};results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs={ex.submit(fetch,e):e for e in by_evse}
        for fut in as_completed(futs):
            row=fut.result();row['siteId']=by_evse[row['evseId']]['siteId'];row['address']=by_evse[row['evseId']]['address'];results.append(row)
    results.sort(key=lambda x:x['siteId'])
    stats=Counter();sigs=Counter()
    for r in results:
        stats['attempted']+=1
        if r.get('error'):stats['errors']+=1;continue
        stats['reachable']+=1
        if r.get('tariffText'):stats['tariffTextFound']+=1;sigs[r['tariffText']]+=1
        if r.get('eurPerKwh') is not None:stats['kwhParsed']+=1
    out={'schemaVersion':'0.1.0','dataset':'germany-wirelane-direct-tariff-probe','countryCode':'DE','scope':{'stagedOnly':True,'publishesToTcc':False,'sampleOnly':True},'operator':OPERATOR,'candidateSitesWithWirelaneEvse':len([s for s in d.get('sites') or [] if s.get('operator')==OPERATOR and any(str(e).upper().startswith('DE*WLN*') for e in (s.get('evseIds') or []))]),'stats':dict(stats),'topTariffSignatures':[{'tariffText':k,'count':v} for k,v in sigs.most_common(40)],'results':results}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_WIRELANE_DIRECT_PROBE='+json.dumps({'candidateSitesWithWirelaneEvse':out['candidateSitesWithWirelaneEvse'],'stats':dict(stats),'topTariffSignatures':out['topTariffSignatures'][:20]},ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
