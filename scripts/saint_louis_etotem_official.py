#!/usr/bin/env python3
"""Validate Saint-Louis Agglomération / E-TOTEM network coverage from durable official PDFs."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
AWARD='https://www.agglo-saint-louis.fr/wp-content/uploads/2025/12/20251209_dcp_AMI_IRVE_attribution.pdf'
ANALYSIS='https://www.agglo-saint-louis.fr/wp-content/uploads/2025/10/AR-V1-rapport-d%E2%80%99analyse-des-offres-AMI-IRVE-SLA.pdf'
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/pdf,*/*','Connection':'close'})
    with urllib.request.urlopen(req,timeout=60) as r:return int(getattr(r,'status',200)),r.read(),r.geturl()
def pdftext(raw):return re.sub(r'\s+',' ',' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages)).strip()
def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '');s=''.join(c for c in s if not unicodedata.combining(c));s=re.sub(r'\s*-\s*','-',s);return re.sub(r'\s+',' ',s.lower().replace('’',"'")).strip()
def require(text,*items):
    n=norm(text);missing=[x for x in items if norm(x) not in n]
    if missing:raise RuntimeError('Saint-Louis official evidence missing: '+', '.join(missing))
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/saint_louis_etotem');args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    as_,araw,afinal=fetch(AWARD);rs,rraw,rfinal=fetch(ANALYSIS)
    if as_!=200 or rs!=200:raise RuntimeError(f'HTTP failure award={as_} analysis={rs}')
    at=pdftext(araw);rt=pdftext(rraw)
    require(at,'Le lauréat','E-TOTEM','Date de signature de la convention','08/12/2025')
    require(rt,'40 Points de Charge existants','retenir E-TOTEM','fin mai 2027')
    payload={'schemaVersion':'1.0.0','dataset':'saint-louis-etotem-official-grandest','generatedAt':now(),'operator':'Saint-Louis Agglomération - réseau public','serviceOperator':'E-TOTEM','country':'FR','region':'Grand Est','department':'Haut-Rhin','classification':{'localPublicNetwork':True,'networkExistenceValidated':True,'etotemAwardValidated':True,'existingNetworkTakeoverValidated':True,'nationalEtotemOperatorAlreadyValidated':True,'exactCurrentLocalTariffResolvedHere':False,'directTariffClassable':False},'network':{'legacyChargePointsTakenOver':40,'awardSignatureDate':'2025-12-08','deploymentSecondPhaseDeadline':'2027-05','serviceModel':'private partner rollout and operation'},'tariff':{'exactCurrentAmount':None,'status':'deferred_to_live_network_or_station_tariff','reuseNationalEtotemOperatorReference':True,'note':'Durable official procurement PDFs validate E-TOTEM and the Saint-Louis network scope, but do not publish the complete live consumer tariff table. Keep local pricing reference-only until the live tariff surface or station test is captured.'},'tccDecision':{'operatorValidated':True,'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','roamingSeparate':True,'stationTestsDeferred':True,'exactTariffFollowupRequired':True},'sourceEvidence':{'officialOnly':True,'awardUrl':afinal,'awardHttpStatus':as_,'awardSha256':hashlib.sha256(araw).hexdigest(),'analysisUrl':rfinal,'analysisHttpStatus':rs,'analysisSha256':hashlib.sha256(rraw).hexdigest()},'publicationStatus':'validated_candidate_reference_only'}
    sig={k:payload[k] for k in ('classification','network','tariff','tccDecision')};payload['sourceEvidence']['relevantFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'saint_louis_etotem_official_grandest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(out/'SUMMARY.md').write_text('# Saint-Louis Agglomération / E-TOTEM\n\nDurable official procurement evidence validates E-TOTEM as the selected network partner, with takeover of 40 existing charge points and rollout through 2027. The complete live local consumer tariff is not present in these durable PDFs, so Saint-Louis is covered as reference-only until live/station pricing is captured.\n')
if __name__=='__main__':main()
