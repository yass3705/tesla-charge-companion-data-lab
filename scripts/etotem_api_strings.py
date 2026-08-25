#!/usr/bin/env python3
"""Extract likely e-Totem backend URLs/actions from the public Flutter bundle."""
import json, re, urllib.request
from pathlib import Path

URL='https://www.e-totem.fr/main.dart.js'
OUT=Path('data/national/etotem_api_strings.json')
req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 TeslaChargeCompanionDataLab/1.0'})
with urllib.request.urlopen(req,timeout=90) as r:
    js=r.read().decode('utf-8','replace')

quoted=[]
for pat in (r'"([^"\\]*(?:\\.[^"\\]*)*)"', r"'([^'\\]*(?:\\.[^'\\]*)*)'"):
    for m in re.finditer(pat,js):
        try:
            s=bytes(m.group(1),'utf-8').decode('unicode_escape')
        except Exception:
            s=m.group(1)
        if s not in quoted:
            quoted.append(s)

abs_urls=sorted(set(re.findall(r'https?://[^"\'`\\\s)]+',js)))
routeish=[]
keywords=('borne','bornes','station','stations','tarif','tarifs','price','prix','pool','reseau','charge','connector','pdc','ocpi','gireve','itin','api','map')
for s in quoted:
    l=s.lower()
    if len(s)>400: continue
    if any(k in l for k in keywords):
        if '/' in s or len(s)<120:
            routeish.append(s)
routeish=sorted(set(routeish))

needles=[
    'aBornes','sIdPoolUnique','sIdPool','sNomReseau','bOcpi','tarifs','Tarifs','reseauxBornes',
    'nIdBorne','nIdPdc','sTypeBorne','sLibelleBorne','szOcppChargeBoxIdentity',
    'SelectsBornes','Stations','ActionsPdc','fPrixMensuel','fPrixPostCharge','nPrixInscription',
    'nPrixTotal','bPostChargeGratuit','bPostChargeInclus','bVisibleTarifs','aPdc','cpo_pool'
]
contexts={}
for needle in needles:
    vals=[]
    for m in re.finditer(re.escape(needle),js):
        snippet=re.sub(r'\s+',' ',js[max(0,m.start()-1200):min(len(js),m.end()+2200)])
        if snippet not in vals: vals.append(snippet)
        if len(vals)>=30: break
    contexts[needle]=vals

# Strings that look like application action names / backend method names.
actions=[]
for s in quoted:
    if len(s)>100 or len(s)<2: continue
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9_./:-]*',s) and any(k in s.lower() for k in keywords):
        actions.append(s)
actions=sorted(set(actions))

# Capture nearby request construction markers too.
request_markers={}
for needle in ['SelectsBornes','ActionsPdc','Stations','Tarifs','cpo_pool']:
    vals=[]
    for m in re.finditer(re.escape(needle),js):
        lo=max(0,m.start()-5000); hi=min(len(js),m.end()+5000)
        block=js[lo:hi]
        # Retain quoted tokens from the surrounding request code, useful for reconstructing payloads.
        tokens=[]
        for qm in re.finditer(r'["\']([^"\']{1,180})["\']',block):
            v=qm.group(1)
            if v not in tokens: tokens.append(v)
        vals.append({'offset':m.start(),'tokens':tokens[:250],'snippet':re.sub(r'\s+',' ',block)[:10000]})
        if len(vals)>=10: break
    request_markers[needle]=vals

payload={'bundleSize':len(js),'absoluteUrls':abs_urls,'routeishStrings':routeish,'actionStrings':actions,'contexts':contexts,'requestMarkers':request_markers}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print('ABSOLUTE URLS')
for x in abs_urls: print(x)
print('\nACTION STRINGS')
for x in actions: print(x)
print('\nKEY CONTEXTS')
for k,vals in contexts.items():
    print('\n###',k)
    for v in vals[:4]: print(v[:3200])
