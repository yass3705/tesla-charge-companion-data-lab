#!/usr/bin/env python3
"""Probe Wirelane public direct-payment pages from national-catalog EVSE ids.

Wirelane prices are station/EVSE specific. BNetzA rows often lack the DE*WLN*
identifier used by Wirelane direct payment, so this probe falls back to the
already-safe AFIR site attached to the BNetzA physical site.
"""
from __future__ import annotations
import argparse,gzip,html,json,re,urllib.parse,urllib.request
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
def wirelane_evses(site):
    bnetza=[str(e) for e in (site.get('evseIds') or []) if str(e).upper().startswith('DE*WLN*')]
    afir_data=((site.get('afir') or {}).get('data') or {})
    afir=[str(e) for e in (afir_data.get('evseIds') or []) if str(e).upper().startswith('DE*WLN*')]
    merged=sorted(set(bnetza+afir))
    return merged,('bnetza' if bnetza else 'afir' if afir else None)
def fetch(evse):
    url=BASE.format(evse=urllib.parse.quote(evse,safe=''))
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'de-DE,de;q=0.9'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:raw=r.read();status=getattr(r,'status',200)
        text=textify(raw)
        m=re.search(r'(?:max\.\s*[0-9.,]+\s*kW)\s+(.{1,700}?)\s+(?:Betreiber|Provider)\s+Wirelane\s+GmbH',text,re.I)
        tariff=(m.group(1).strip() if m else None)
        kwh=None;start_fee=None;minute_fee=None;after_min=None;cap=None
        if tariff:
            mk=re.search(r'([0-9]+(?:[,.][0-9]+)?)\s*(€|EUR|ct)\s*/?\s*kWh',tariff,re.I)
            if mk:
                val=float(mk.group(1).replace(',','.'))
                if mk.group(2).lower()=='ct':val/=100
                kwh=round(val,6)
            ms=re.search(r'(?:zzgl\.|\+)\s*([0-9]+(?:[,.][0-9]+)?)\s*€\s*(?:Startgebühr|Start)',tariff,re.I)
            if ms:start_fee=float(ms.group(1).replace(',','.'))
            mm=re.search(r'([0-9]+(?:[,.][0-9]+)?)\s*(€|EUR|ct)\s*/?\s*Min',tariff,re.I)
            if mm:
                val=float(mm.group(1).replace(',','.'))
                if mm.group(2).lower()=='ct':val/=100
                minute_fee=round(val,6)
            ma=re.search(r'(?:ab|nach)\s*([0-9]+)\s*Min',tariff,re.I)
            if ma:after_min=int(ma.group(1))
            mc=re.search(r'max\.?\s*([0-9]+(?:[,.][0-9]+)?)\s*€',tariff,re.I)
            if mc:cap=float(mc.group(1).replace(',','.'))
        unavailable=bool(re.search(r'(?:zur Zeit nicht verfügbar|Status:)',text,re.I))
        provider_wirelane=bool(re.search(r'(?:Betreiber|Provider)\s+Wirelane\s+GmbH',text,re.I))
        return {'evseId':evse,'url':url,'status':status,'tariffText':tariff,'eurPerKwh':kwh,'startFeeEur':start_fee,'minuteFeeEur':minute_fee,'afterMinutes':after_min,'capEur':cap,'providerWirelane':provider_wirelane,'pageSaysUnavailable':unavailable,'bytes':len(raw)}
    except Exception as exc:return {'evseId':evse,'url':url,'error':f'{type(exc).__name__}: {exc}'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--catalog',type=Path,default=Path('data/germany/germany_non_tesla_catalog_staging_tariff_classified.json.gz'));ap.add_argument('--limit',type=int,default=150);ap.add_argument('--workers',type=int,default=8);ap.add_argument('--output',type=Path,default=Path('data/germany/wirelane_direct_probe.json'));args=ap.parse_args()
    d=load_gz(args.catalog);all_candidates=[];id_source_counts=Counter();operator_sites=0
    for s in d.get('sites') or []:
        if s.get('operator')!=OPERATOR:continue
        operator_sites+=1;evses,source=wirelane_evses(s)
        if not evses:continue
        id_source_counts[source]+=1
        all_candidates.append({'siteId':s['id'],'evseId':evses[0],'evseCount':len(evses),'idSource':source,'address':s.get('address'),'afirProvider':(((s.get('afir') or {}).get('data') or {}).get('provider'))})
    candidates=all_candidates[:args.limit]
    by_evse={c['evseId']:c for c in candidates};results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs={ex.submit(fetch,e):e for e in by_evse}
        for fut in as_completed(futs):
            row=fut.result();meta=by_evse[row['evseId']];row.update({k:meta[k] for k in ('siteId','address','idSource','afirProvider','evseCount')});results.append(row)
    results.sort(key=lambda x:x['siteId']);stats=Counter();sigs=Counter();prices=Counter()
    for r in results:
        stats['attempted']+=1
        if r.get('error'):stats['errors']+=1;continue
        stats['reachable']+=1
        if r.get('providerWirelane'):stats['providerConfirmed']+=1
        if r.get('pageSaysUnavailable'):stats['pageUnavailable']+=1
        if r.get('tariffText'):stats['tariffTextFound']+=1;sigs[r['tariffText']]+=1
        if r.get('eurPerKwh') is not None:stats['kwhParsed']+=1;prices[r['eurPerKwh']]+=1
    out={'schemaVersion':'0.2.0','dataset':'germany-wirelane-direct-tariff-probe','countryCode':'DE','scope':{'stagedOnly':True,'publishesToTcc':False,'sampleOnly':True},'operator':OPERATOR,'operatorSites':operator_sites,'candidateSitesWithWirelaneEvse':len(all_candidates),'evseIdSourceDistribution':dict(id_source_counts),'stats':dict(stats),'priceDistribution':[{'eurPerKwh':p,'count':n} for p,n in prices.most_common()],'topTariffSignatures':[{'tariffText':k,'count':v} for k,v in sigs.most_common(40)],'results':results}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_WIRELANE_DIRECT_PROBE='+json.dumps({'operatorSites':operator_sites,'candidateSitesWithWirelaneEvse':out['candidateSitesWithWirelaneEvse'],'evseIdSourceDistribution':out['evseIdSourceDistribution'],'stats':dict(stats),'priceDistribution':out['priceDistribution'][:20],'topTariffSignatures':out['topTariffSignatures'][:15]},ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
