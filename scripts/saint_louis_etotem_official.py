#!/usr/bin/env python3
"""Validate Saint-Louis Agglomération / E-TOTEM network coverage from durable official procurement evidence."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
AWARD='https://www.agglo-saint-louis.fr/wp-content/uploads/2025/12/20251209_dcp_AMI_IRVE_attribution.pdf'
ANALYSIS='https://www.agglo-saint-louis.fr/wp-content/uploads/2025/10/AR-V1-rapport-d%E2%80%99analyse-des-offres-AMI-IRVE-SLA.pdf'
def fetch(url,timeout=45):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/pdf,*/*','Connection':'close'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return int(getattr(r,'status',200)),r.read(),r.geturl()
def pdftext(raw):return re.sub(r'\s+',' ',' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages)).strip()
def norm(s):
    import unicodedata
    s=unicodedata.normalize('NFKD',s or '');s=''.join(c for c in s if not unicodedata.combining(c));s=s.lower().replace('’',"'");s=re.sub(r'\s+',' ',s);return s.strip()
def require_regex(text,label,pattern):
    n=norm(text)
    if not re.search(pattern,n,re.I):raise RuntimeError('Saint-Louis official evidence missing: '+label)
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='out/saint_louis_etotem');args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    as_,araw,afinal=fetch(AWARD,45)
    if as_!=200:raise RuntimeError(f'HTTP failure award={as_}')
    at=pdftext(araw)
    require_regex(at,'winner field',r'laureat')
    require_regex(at,'E-TOTEM winner',r'e\s*[-–—]?\s*totem|etotem')
    require_regex(at,'signature date',r'08\s*/\s*12\s*/\s*2025')
    analysis_live=False;analysis_status=None;analysis_sha=None;analysis_url=ANALYSIS;legacy_points=None;deployment_deadline=None
    try:
        rs,rraw,rfinal=fetch(ANALYSIS,8);rt=pdftext(rraw)
        require_regex(rt,'40 existing charge points',r'40\s+points?\s+de\s+charge')
        require_regex(rt,'E-TOTEM retained',r'retenir[^\n]{0,100}(?:e\s*[-–—]?\s*totem|etotem)')
        require_regex(rt,'May 2027 deadline',r'fin\s+mai\s+2027')
        analysis_live=True;analysis_status=rs;analysis_sha=hashlib.sha256(rraw).hexdigest();analysis_url=rfinal;legacy_points=40;deployment_deadline='2027-05'
    except Exception:
        pass
    payload={'schemaVersion':'1.0.0','dataset':'saint-louis-etotem-official-grandest','generatedAt':now(),'operator':'Saint-Louis Agglomération - réseau public','serviceOperator':'E-TOTEM','country':'FR','region':'Grand Est','department':'Haut-Rhin','classification':{'localPublicNetwork':True,'networkExistenceValidated':True,'etotemAwardValidated':True,'existingNetworkTakeoverValidated':analysis_live,'nationalEtotemOperatorAlreadyValidated':True,'exactCurrentLocalTariffResolvedHere':False,'directTariffClassable':False},'network':{'legacyChargePointsTakenOver':legacy_points,'awardSignatureDate':'2025-12-08','deploymentSecondPhaseDeadline':deployment_deadline,'serviceModel':'private partner rollout and operation'},'tariff':{'exactCurrentAmount':None,'status':'deferred_to_live_network_or_station_tariff','reuseNationalEtotemOperatorReference':True,'note':'The official award is the blocking authority for E-TOTEM network attribution. The analysis PDF is optional in CI because the Saint-Louis host is intermittent; exact live local consumer pricing remains reference-only until captured from the live tariff surface or station flow.'},'tccDecision':{'operatorValidated':True,'coverageValidated':True,'directTariffClassable':False,'defaultDisplay':'reference_only','roamingSeparate':True,'stationTestsDeferred':True,'exactTariffFollowupRequired':True},'sourceEvidence':{'officialOnly':True,'awardUrl':afinal,'awardHttpStatus':as_,'awardSha256':hashlib.sha256(araw).hexdigest(),'analysisUrl':analysis_url,'analysisLiveFetchSucceededInCi':analysis_live,'analysisHttpStatus':analysis_status,'analysisSha256':analysis_sha,'analysisRole':'optional_supplemental_nonblocking'},'publicationStatus':'validated_candidate_reference_only'}
    sig={k:payload[k] for k in ('classification','network','tariff','tccDecision')};payload['sourceEvidence']['relevantFingerprintSha256']=hashlib.sha256(json.dumps(sig,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    (out/'saint_louis_etotem_official_grandest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(out/'SUMMARY.md').write_text('# Saint-Louis Agglomération / E-TOTEM\n\nOfficial award evidence validates E-TOTEM as the selected Saint-Louis network partner, signed 8 December 2025. The analysis PDF is used only as optional supplemental evidence because the official host is intermittent from GitHub Actions. Exact local pricing remains reference-only until the live tariff/station flow is captured.\n')
if __name__=='__main__':main()
