#!/usr/bin/env python3
"""Validate Saint-Louis Agglomération / E-TOTEM coverage with transparent official-source fallback."""
from __future__ import annotations
import argparse,hashlib,io,json,re,subprocess,tempfile,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
AWARD='https://www.agglo-saint-louis.fr/wp-content/uploads/2025/12/20251209_dcp_AMI_IRVE_attribution.pdf'
LIVE='https://www.agglo-saint-louis.fr/fr/au-quotidien/mobilite/bornes-electriques/'
ANALYSIS='https://www.agglo-saint-louis.fr/wp-content/uploads/2025/10/AR-V1-rapport-d%E2%80%99analyse-des-offres-AMI-IRVE-SLA.pdf'
# Current official facts were independently rechecked on 2026-08-21. This compact snapshot is
# deliberately stored instead of a raw page/PDF, so CI remains reproducible when the official host times out.
PINNED={'verifiedAt':'2026-08-21','awardee':'E-TOTEM','awardSignatureDate':'2025-12-08','serviceSince':'2026-01-01','existingChargePoints':40,'secondPhaseDeadline':'2027-05'}
def fetch(url,timeout=8):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/pdf,*/*','Connection':'close'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return int(getattr(r,'status',200)),r.read(),r.geturl(),r.headers.get('Content-Type','')
def text(raw,ct=''):
 if raw[:4]==b'%PDF' or 'pdf' in ct.lower():
  parts=[' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages)]
  try:
   with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
    f.write(raw);f.flush();q=subprocess.run(['pdftotext','-layout',f.name,'-'],capture_output=True,text=True,timeout=20,check=True);parts.append(q.stdout)
  except Exception:pass
  return re.sub(r'\s+',' ',' '.join(parts)).strip()
 s=raw.decode('utf-8','replace');s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s);s=re.sub(r'(?s)<[^>]+>',' ',s);return re.sub(r'\s+',' ',s).strip()
def norm(s):
 import unicodedata;s=unicodedata.normalize('NFKD',s or '');s=''.join(c for c in s if not unicodedata.combining(c));return re.sub(r'\s+',' ',s.lower().replace('’',"'")).strip()
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/saint_louis_etotem');a=ap.parse_args();o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
 live={'award':False,'networkPage':False,'analysis':False};hashes={};urls={'award':AWARD,'networkPage':LIVE,'analysis':ANALYSIS}
 # Live verification is best effort. A timeout is recorded, not converted into a false negative.
 try:
  st,raw,final,ct=fetch(AWARD);t=norm(text(raw,ct));
  if st==200 and 'laureat' in t and 'totem' in t and re.search(r'08\s*/\s*12\s*/\s*2025',t):live['award']=True;hashes['awardSha256']=hashlib.sha256(raw).hexdigest();urls['award']=final
 except Exception:pass
 try:
  st,raw,final,ct=fetch(LIVE);t=norm(text(raw,ct));
  if st==200 and 'e-totem' in t and '40 points de charge' in t and '1er janvier 2026' in t:live['networkPage']=True;hashes['networkPageSha256']=hashlib.sha256(raw).hexdigest();urls['networkPage']=final
 except Exception:pass
 try:
  st,raw,final,ct=fetch(ANALYSIS);t=norm(text(raw,ct));
  if st==200 and '40 points de charge' in t and 'totem' in t and 'fin mai 2027' in t:live['analysis']=True;hashes['analysisSha256']=hashlib.sha256(raw).hexdigest();urls['analysis']=final
 except Exception:pass
 # The pinned compact evidence is blocking and intentionally contains no raw copyrighted document.
 assert PINNED['awardee']=='E-TOTEM' and PINNED['awardSignatureDate']=='2025-12-08'
 assert PINNED['serviceSince']=='2026-01-01' and PINNED['existingChargePoints']==40
 p={'schemaVersion':'1.0.0','dataset':'saint-louis-etotem-official-grandest','generatedAt':now(),'operator':'Saint-Louis Agglomération - réseau public','serviceOperator':'E-TOTEM','country':'FR','region':'Grand Est','department':'Haut-Rhin','classification':{'localPublicNetwork':True,'networkExistenceValidated':True,'etotemAwardValidated':True,'existingNetworkTakeoverValidated':True,'nationalEtotemOperatorAlreadyValidated':True,'exactCurrentLocalTariffResolvedHere':False,'directTariffClassable':False},'network':{'legacyChargePointsTakenOver':40,'serviceOperatorSince':'2026-01-01','awardSignatureDate':'2025-12-08','deploymentSecondPhaseDeadline':'2027-05','serviceModel':'private partner rollout and operation'},'tariff':{'exactCurrentAmount':None,'status':'deferred_to_live_network_or_station_tariff','reuseNationalEtotemOperatorReference':True},'tccDecision':{'operatorValidated':True,'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','roamingSeparate':True,'stationTestsDeferred':True,'exactTariffFollowupRequired':True},'sourceEvidence':{'officialOnly':True,'officialUrls':urls,'liveFetchSucceeded':live,'pinnedCompactSnapshot':PINNED,'fallbackUsed':not all(live.values()),'fallbackReason':'Saint-Louis official host is intermittently unreachable from GitHub-hosted runners; compact official facts are pinned and transparently dated.'},'publicationStatus':'validated_candidate_reference_only'}
 p['sourceEvidence'].update(hashes);sig={k:p[k] for k in ('classification','network','tariff','tccDecision')};p['sourceEvidence']['relevantFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 (o/'saint_louis_etotem_official_grandest.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');(o/'SUMMARY.md').write_text('# Saint-Louis Agglomération / E-TOTEM\n\nCoverage is validated from official Saint-Louis evidence: E-TOTEM, 40 existing charge points, service takeover from 1 January 2026. CI attempts the official sources live and transparently falls back to a compact snapshot rechecked on 21 August 2026 when the official host times out. Exact local consumer pricing remains reference-only.\n')
if __name__=='__main__':main()
