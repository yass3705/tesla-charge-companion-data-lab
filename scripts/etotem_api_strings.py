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

contexts={}
for needle in ['aBornes','sIdPoolUnique','sIdPool','sNomReseau','bOcpi','tarifs','Tarifs','reseauxBornes','nIdBorne','nIdPdc','sTypeBorne','sLibelleBorne','szOcppChargeBoxIdentity']:
    vals=[]
    for m in re.finditer(re.escape(needle),js):
        snippet=re.sub(r'\s+',' ',js[max(0,m.start()-600):min(len(js),m.end()+1000)])
        if snippet not in vals: vals.append(snippet)
        if len(vals)>=20: break
    contexts[needle]=vals

# Strings that look like application action names / backend method names.
actions=[]
for s in quoted:
    if len(s)>100 or len(s)<2: continue
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9_./:-]*',s) and any(k in s.lower() for k in keywords):
        actions.append(s)
actions=sorted(set(actions))

payload={'bundleSize':len(js),'absoluteUrls':abs_urls,'routeishStrings':routeish,'actionStrings':actions,'contexts':contexts}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print('ABSOLUTE URLS')
for x in abs_urls: print(x)
print('\nACTION STRINGS')
for x in actions: print(x)
print('\nROUTEISH STRINGS')
for x in routeish: print(x)
print('\nKEY CONTEXTS')
for k,vals in contexts.items():
    print('\n###',k)
    for v in vals[:6]: print(v[:1600])
