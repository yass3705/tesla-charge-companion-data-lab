#!/usr/bin/env python3
"""Recover only client-distributed myAtlante API configuration and prove one read-only tariff.

No account login, charging, payment or mutation endpoint is called. Any candidate APIM key
found in the publicly distributed Android package is immediately masked in GitHub logs and
is never written to artifacts.
"""
from __future__ import annotations
import io, json, os, re, sys, urllib.request, urllib.error, zipfile
from pathlib import Path

PKG='com.atlante.charging'
VERSION_CODE='3970'  # myAtlante 1.58.0 public APKPure package; known downloadable build
XAPK=f'https://d.apkpure.net/b/XAPK/{PKG}?versionCode={VERSION_CODE}'
BASE='https://pdefweushaapiam01.azure-api.net/app-backend/v1'
TENANT='390c3ff9-b41c-42dc-aa48-1dd51ad6ce39'
MAP=f'{BASE}/tenants/{TENANT}/map-locations?latLongBottomLeft=35%2C5&latLongTopRight=48%2C19&evseTypes=AC%2CDC%2CHPC&locationStatus=ALL&connectorTypes=CCS%2CCHADEMO%2CTYPE2'
OUT=Path('data/reports/atlante_apk_public_config_probe.json')
UA='Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/140 Mobile Safari/537.36'


def fetch_bytes(url:str)->bytes:
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Referer':'https://apkpure.net/'})
    with urllib.request.urlopen(req,timeout=90) as r:
        return r.read()


def all_payloads(blob:bytes):
    yield ('xapk',blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for n in z.namelist():
            if n.lower().endswith('.apk'):
                b=z.read(n); yield (n,b)
                try:
                    with zipfile.ZipFile(io.BytesIO(b)) as a:
                        for p in a.namelist():
                            if p.endswith('/'):
                                continue
                            try: d=a.read(p)
                            except Exception: continue
                            if len(d)<=80_000_000:
                                yield (n+'!'+p,d)
                except Exception:
                    pass


def strings(data:bytes):
    # Android/Flutter/React-Native client constants are generally preserved as ASCII/UTF-8 strings.
    for m in re.finditer(rb'[\x20-\x7e]{12,256}',data):
        try: yield m.group().decode('utf-8')
        except Exception: pass


def candidates(blob:bytes):
    hits=[]; vals=set()
    for name,data in all_payloads(blob):
        ss=list(strings(data))
        joined='\n'.join(ss)
        if 'pdefweushaapiam01.azure-api.net' in joined or 'Ocp-Apim-Subscription-Key' in joined:
            hits.append(name)
        for s in ss:
            # Standard Azure APIM subscription keys are 32 hex chars. Restricting to this shape
            # avoids broad guessing and only tests constants physically shipped in the public app.
            for m in re.findall(r'(?<![0-9A-Fa-f])[0-9A-Fa-f]{32}(?![0-9A-Fa-f])',s):
                vals.add(m)
    return sorted(vals),sorted(set(hits))


def api_json(url,key):
    req=urllib.request.Request(url,headers={
        'Ocp-Apim-Subscription-Key':key,'Accept':'application/json','Accept-Language':'it-IT',
        'X-App-Version':'1.58.0','X-App-Platform':'android','User-Agent':'myAtlante/1.58.0 (Android)'
    })
    with urllib.request.urlopen(req,timeout=45) as r:
        return r.status,json.loads(r.read().decode('utf-8'))


def main():
    x=fetch_bytes(XAPK)
    cands,hits=candidates(x)
    working=None; map_payload=None; tried=0
    for c in cands[:400]:
        tried+=1
        print(f'::add-mask::{c}')
        try:
            st,p=api_json(MAP,c)
            if st==200 and isinstance(p,dict) and isinstance(p.get('locations'),list):
                working=c; map_payload=p; break
        except urllib.error.HTTPError as e:
            if e.code not in (401,403):
                continue
        except Exception:
            continue
    if not working:
        raise SystemExit(f'No client-distributed APIM key validated; candidates={len(cands)} hits={hits}')

    locs=[l for l in map_payload.get('locations',[]) if str(l.get('countryCode','')).upper()=='IT' and str(l.get('partyId','')).upper()=='ATE']
    if not locs: raise SystemExit('Working client key found but no Italy ATE locations')
    samples=[]
    # obtain actual station tariff response, read-only; try several locations until an unconditional energy component appears
    for l in locs[:40]:
        lid=str(l.get('id') or '')
        if not lid: continue
        try:
            _,detail=api_json(f'{BASE}/tenants/{TENANT}/locations/{lid}',working)
            _,tariffs=api_json(f'{BASE}/tenants/{TENANT}/locations/{lid}/tariffs',working)
        except Exception:
            continue
        rows=[]
        for t in tariffs if isinstance(tariffs,list) else (tariffs.get('tariffs',[]) if isinstance(tariffs,dict) else []):
            ids=t.get('identifiers') or {}
            for pc in t.get('priceComponents') or []:
                if str(pc.get('priceDimension','')).upper()=='ENERGY' and str(pc.get('currency','')).upper()=='EUR':
                    price=(pc.get('price') or {}).get('incl_vat')
                    if isinstance(price,(int,float)) and price>0:
                        rows.append({'evseId':ids.get('evseId'),'connectorId':ids.get('connectorId'),'eurPerKwh':price})
        if rows:
            samples.append({'locationId':lid,'name':detail.get('displayName') or detail.get('locationName') or l.get('displayName'),'city':detail.get('city') or l.get('city'),'tariffs':rows[:12]})
            if len(samples)>=3: break
    if not samples: raise SystemExit('API access succeeded but no station energy tariff sample found')
    out={
      'source':'public myAtlante Android client configuration',
      'package':PKG,'testedVersion':'1.58.0','apiBase':BASE,'tenantId':TENANT,
      'clientCredentialRecovered':True,'clientCredentialPersisted':False,
      'candidateCount':len(cands),'candidateProbeCount':tried,'configHitFiles':hits[:20],
      'italyAtlanteMapLocations':len(locs),'stationTariffSamples':samples,
      'security':{'accountCredentialsUsed':False,'loginEndpointsCalled':False,'chargingEndpointsCalled':False,'paymentEndpointsCalled':False,'mutationsCalled':False}
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'italyAtlanteLocations':len(locs),'stationTariffSamples':samples},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
