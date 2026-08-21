#!/usr/bin/env python3
"""Public discovery for current Connect&go Mad et Moselle and Bassin de Pompey tariff pages."""
import hashlib,html,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
TARGETS={
 'mad_et_moselle':('Connect&go - Mad et Moselle','https://madetmoselle.connectandgo.fr/','https://madetmoselle.connectandgo.fr/tarifs/'),
 'bassin_pompey':('Connect&go - Bassin de Pompey','https://bassinpompey.connectandgo.fr/','https://bassinpompey.connectandgo.fr/tarifs/'),
}
def fetch(u):
 req=urllib.request.Request(u,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
 with urllib.request.urlopen(req,timeout=60) as r:return int(getattr(r,'status',200)),r.read(),r.geturl()
def text(b):
 s=b.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>','\n',s);s=html.unescape(s).replace('\xa0',' ');return re.sub(r'[ \t]+',' ',s)
def evidence_lines(s):
 lines=[]
 for x in s.splitlines():
  x=re.sub(r'\s+',' ',x).strip()
  if not x:continue
  low=x.lower()
  if any(k in low for k in ('€/','€ /','kwh','minute','heure','abonnement','puissance','surtaxe','tarif','bornes','freshmile','delmonicos')):
   if x not in lines:lines.append(x)
 return lines[:250]
def main():
 out=Path('out/connectandgo_next');out.mkdir(parents=True,exist_ok=True);result={'dataset':'connectandgo-next-grandest-discovery','generatedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'targets':{}}
 for key,(name,home,tariffs) in TARGETS.items():
  row={'operator':name}
  for label,u in [('home',home),('tariffs',tariffs)]:
   try:
    status,raw,final=fetch(u);row[label]={'status':status,'url':final,'sha256':hashlib.sha256(raw).hexdigest(),'evidenceLines':evidence_lines(text(raw))}
   except Exception as e:row[label]={'status':'error','url':u,'error':str(e)[:500]}
  result['targets'][key]=row
 (out/'discovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:{x:v.get(x,{}).get('status') for x in ('home','tariffs')} for k,v in result['targets'].items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
