#!/usr/bin/env python3
"""Probe Picoty's public EAS Update endpoint and safely scan returned launch bundles.

Only public update metadata/assets are fetched. No user/account credentials, cookies, OAuth
or API subscription keys are sent. Persisted output contains only sanitized metadata and
configuration snippets; launch assets themselves are never committed.
"""
from __future__ import annotations
import json,re,urllib.request,urllib.error
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from datetime import datetime,timezone

PROJECT='fda4bdf2-46e4-4bc8-9ec8-296862f5d2c3'
BASE=f'https://u.expo.dev/{PROJECT}'
RUNTIMES=['2.0.0','1.59.0','1.58.0','1.56.2','1.55.0','2','1']
TOKENS=['tenantId','tenant_id','getTenantId','registrationCode','registrationGroup','registerWithoutToken','appDistribution','distributionId','deftpower','picoty','getMapLocationsAsGuest','getLocationTariffsAsGuest']
JWT=re.compile(rb'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}(?:\.[A-Za-z0-9_-]{8,})?')
GOOGLE=re.compile(rb'AIza[0-9A-Za-z_-]{20,}')
SECRET=re.compile(rb'(?i)(authorization|subscription[-_]?key|api[-_]?key|access[-_]?token|refresh[-_]?token|client[-_]?secret)(\s*[=:]\s*["\']?)([^\s"\',}]{8,})')

def sanitize_bytes(b:bytes)->str:
    b=JWT.sub(b'<redacted-jwt>',b); b=GOOGLE.sub(b'<redacted-google-api-key>',b)
    b=SECRET.sub(lambda m:m.group(1)+m.group(2)+b'<redacted>',b)
    return b.decode('utf-8','replace')

def request(runtime:str):
    headers={
      'User-Agent':'TeslaChargeCompanion-data-lab/1.0',
      'Accept':'multipart/mixed,application/expo+json,application/json',
      'expo-platform':'android','expo-runtime-version':runtime,
      'expo-channel-name':'production','expo-protocol-version':'1',
    }
    req=urllib.request.Request(BASE,headers=headers,method='GET')
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return r.status,dict(r.headers),r.read(8_000_000)
    except urllib.error.HTTPError as e:return e.code,dict(e.headers),e.read(500_000)
    except Exception as e:return None,{},str(e).encode()

def parse_parts(headers:dict,body:bytes):
    ct=headers.get('Content-Type') or headers.get('content-type') or ''
    parts=[]
    if 'multipart/' in ct.lower():
        msg=BytesParser(policy=default).parsebytes((f'Content-Type: {ct}\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
        for p in msg.iter_parts():
            payload=p.get_payload(decode=True) or b''
            parts.append({'contentType':p.get_content_type(),'headers':{k:v for k,v in p.items()},'body':payload})
    else:parts.append({'contentType':ct,'headers':{},'body':body})
    return parts

def collect_json(obj,found):
    if isinstance(obj,dict):
        for k,v in obj.items():
            kl=str(k).lower()
            if kl in {'url','launchasset','assets','metadata','extra','runtimeversion','createdat','id'}:
                if isinstance(v,(str,int,float,bool)) or v is None:found.append((str(k),v))
            collect_json(v,found)
    elif isinstance(obj,list):
        for v in obj:collect_json(v,found)

def asset_urls(obj):
    out=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k=='url' and isinstance(v,str) and v.startswith('https://') and v not in out:out.append(v)
                else:walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(obj);return out

def fetch_asset(url):
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'TeslaChargeCompanion-data-lab/1.0'})
        with urllib.request.urlopen(req,timeout=45) as r:return r.status,dict(r.headers),r.read(30_000_000)
    except Exception as e:return None,{},str(e).encode()

def snippets(text:str):
    low=text.lower();out=[]
    for tok in TOKENS:
        needle=tok.lower();start=0
        while True:
            i=low.find(needle,start)
            if i<0:break
            sn=text[max(0,i-700):min(len(text),i+len(tok)+1200)].replace('\x00',' ')
            if sn not in [x['snippet'] for x in out]:out.append({'token':tok,'snippet':sn})
            start=i+len(tok)
            if len(out)>=120:return out
    return out

def main():
    report={'schemaVersion':'1.0.0','generatedAt':datetime.now(timezone.utc).isoformat(),'projectId':PROJECT,'channel':'production','credentialsSent':False,'results':[]}
    seen_assets=set()
    for runtime in RUNTIMES:
        status,h,b=request(runtime)
        item={'runtime':runtime,'status':status,'contentType':h.get('Content-Type') or h.get('content-type'),'bytes':len(b),'parts':[],'assetScans':[]}
        for part in parse_parts(h,b):
            txt=sanitize_bytes(part['body'])
            po={'contentType':part['contentType'],'bytes':len(part['body']),'snippets':snippets(txt),'jsonSummary':[]}
            obj=None
            try:obj=json.loads(part['body'].decode('utf-8'))
            except Exception:pass
            if obj is not None:
                vals=[];collect_json(obj,vals);po['jsonSummary']=vals[:120]
                for url in asset_urls(obj):
                    if url in seen_assets:continue
                    seen_assets.add(url)
                    st,ah,ab=fetch_asset(url)
                    atxt=sanitize_bytes(ab)
                    hits=snippets(atxt)
                    if hits:item['assetScans'].append({'url':url,'status':st,'contentType':ah.get('Content-Type') or ah.get('content-type'),'bytes':len(ab),'snippets':hits})
            item['parts'].append(po)
        report['results'].append(item)
    raw=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if re.search(r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}',raw) or re.search(r'AIza[0-9A-Za-z_-]{20,}',raw):raise RuntimeError('secret-like material survived')
    Path('data/reports/avia_picoty_expo_update_probe.json').write_text(raw,encoding='utf-8')
    print(json.dumps([{'runtime':x['runtime'],'status':x['status'],'contentType':x['contentType'],'parts':len(x['parts']),'assetHits':len(x['assetScans'])} for x in report['results']],indent=2))
if __name__=='__main__':main()
