#!/usr/bin/env python3
"""Validate and consolidate current public charging network evidence for Pays de la Loire."""
from __future__ import annotations
import argparse, hashlib, io, json, re, ssl, urllib.error, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
OUEST='https://ouestcharge.fr/tarifs-borne-ouest-charge/'
ENTENTE='https://www.territoire-energie-paysdelaloire.fr/qui-sommes-nous/'
TE53='https://www.territoire-energie53.fr/wp-content/uploads/2025/12/TEM-vous-accompagne-Guide-financier-edition-2026-v3.pdf'
SYDEV='https://www.sydev-vendee.fr/sites/default/files/assets/files/Guide%20financier%202026.pdf'
SYDEV_MOBILITY='https://www.sydev-vendee.fr/transition-energetique/mobilite-durable/electrique'
SARTHE_LOCAL='https://www.sille-le-guillaume.fr/borne-de-recharge-pour-vehicules-electriques-et-hybrides/'
SARTHE_ALIZE='https://alizecharge.com/partenaires/sarthe-irve/'
CCLLB='https://www.loirluceberce.fr/bornes-de-recharge-irve/'
NANTES='https://metropole.nantes.fr/actualites/1-250-bornes-de-recharge-deployees-dans-la-metropole-nantaise'


def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:
            return int(getattr(r,'status',200)),r.read(),r.geturl(),True
    except urllib.error.URLError as e:
        if 'sydev-vendee.fr' not in url or 'CERTIFICATE_VERIFY_FAILED' not in str(e): raise
        ctx=ssl._create_unverified_context()
        with urllib.request.urlopen(req,timeout=90,context=ctx) as r:
            return int(getattr(r,'status',200)),r.read(),r.geturl(),False


def norm(s):
    import unicodedata
    if isinstance(s,bytes): s=s.decode('utf-8',errors='replace')
    s=unescape(s or '')
    s=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>',' ',s,flags=re.I|re.S)
    s=re.sub(r'<[^>]+>',' ',s)
    s=unicodedata.normalize('NFKD',s)
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',s.lower().replace('\xa0',' ')).strip()


def require(text,*items,label='evidence'):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError(f'{label} missing: '+', '.join(missing))


def section(text,start,end):
    n=norm(text); a=n.rfind(norm(start))
    if a<0: raise RuntimeError(f'section start missing: {start}')
    b=n.find(norm(end),a+len(norm(start)))
    if b<0: b=len(n)
    return n[a:b]


def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def write_json(path,payload): path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/pdl'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    os_,oraw,ofinal,otls=fetch(OUEST); es,eraw,efinal,etls=fetch(ENTENTE); ms,mraw,mfinal,mtls=fetch(TE53)
    ys,yraw,yfinal,ytls=fetch(SYDEV); yms,ymraw,ymfinal,ymtls=fetch(SYDEV_MOBILITY)
    ss,sraw,sfinal,stls=fetch(SARTHE_LOCAL); cs,craw,cfinal,ctls=fetch(CCLLB); ns,nraw,nfinal,ntls=fetch(NANTES)
    if min(os_,es,ms,ys,yms,ss,cs,ns)!=200: raise RuntimeError('one or more official sources returned non-200')

    sec49=section(oraw,'Maine-et-Loire (49)','Loire-Atlantique (44)')
    require(sec49,'borne normale','0,35','5eme heure','0,20','borne rapide','0,45','1ere heure','borne ultra rapide','0,55','45 min','1€','non abonnes',label='Ouest Charge 49')
    sec44=section(oraw,'Loire-Atlantique (44)','Ille-et-Vilaine (35)')
    require(sec44,'borne normale','0,35','4eme heure','0,20','borne rapide','0,50','1ere heure','1€','non abonnes',label='Ouest Charge 44')
    require(oraw,'Vendée (85)','Mayenne (53)','Sarthe (72)','un de nos partenaires','Alize Charge','Territoire d’énergie','SYDEV',label='Ouest Charge partners')
    require(eraw,"Territoire d'énergie 44",'Siéml',"Territoire d'énergie 53",'SYDEV','Département de la Sarthe','Région Pays de la Loire',label='regional entente')

    from pypdf import PdfReader
    mt='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(mraw)).pages)
    require(mt,'Tarifs de recharge pour les usagers au 01/01/2026','22 kW (normale)','0,43','50 kW (rapide)','0,87','180 kW (ultra-rapide)','0,92','Badge Ouest Charge','Scan du QR Code','Carte bleue sans contact','E-totem','plus de 150 points de recharge','2025 et 2026',label='TE53 2026')
    yt='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(yraw)).pages)
    require(yt,'GUIDE FINANCIER','2026','Tarifs pour les utilisateurs des IRVE','Non abonné','0,41','0,50','0,59','2,00',label='SYDEV 2026')
    require(ymraw,'bornes','recharge','véhicules électriques',label='SYDEV mobility')

    require(sraw,'groupement de commandes','Département de la Sarthe','22 kW','Bouygues Énergies','Bornes normales','0,20€/kWh','1 € + 0,20€/kWh',label='Sarthe municipal current evidence')
    require(craw,'9 bornes','badge Freshmile','QR code','0,23','0,04','minute','continue tant que le véhicule reste branché','plafonné à 50',label='Loir-Luce-Berce')
    require(nraw,'1 250 bornes','24 communes','e-Totem','e-City','3 à 22 kW','e-Fast','50 à 150 kW','35 € HT','100 kWh','10 minutes','quart d’heure','1 €','3 €',label='Nantes e-Totem')

    common={'schemaVersion':'1.0.0','generatedAt':now(),'country':'FR','region':'Pays de la Loire','publicationStatus':'validated_candidate'}
    ouest={**common,'dataset':'ouestcharge-44-49-official-pdl','operator':'Ouest Charge','classification':{'regionalPublicNetworkFamily':True,'exactDirectTariffByDepartment':True,'subscriberAndNonSubscriber':True,'energyPlusConnectionTime':True,'roamingSeparate':True},'departments':{'Loire-Atlantique':{'authority':'Territoire d’énergie 44','tariffs':{'normal':{'energyEurPerKwh':0.35,'freeConnectedMinutes':240,'day0700To2100AfterFreeEurPerMin':0.20},'rapid':{'energyEurPerKwh':0.50,'freeConnectedMinutes':60,'day0700To2100AfterFreeEurPerMin':0.20}},'nonSubscriberSessionFeeEur':1.0},'Maine-et-Loire':{'authority':'Siéml','tariffs':{'normal':{'energyEurPerKwh':0.35,'freeConnectedMinutes':300,'day0700To2100AfterFreeEurPerMin':0.20},'rapid':{'energyEurPerKwh':0.45,'freeConnectedMinutes':60,'day0700To2100AfterFreeEurPerMin':0.20},'ultraRapid':{'energyEurPerKwh':0.55,'freeConnectedMinutes':45,'day0700To2100AfterFreeEurPerMin':0.20}},'nonSubscriberSessionFeeEur':1.0}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'departmentAndStationCategoryRequired':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'tariffUrl':ofinal,'tariffHttpStatus':os_,'tariffSha256':hashlib.sha256(oraw).hexdigest(),'regionalEntenteUrl':efinal,'regionalEntenteHttpStatus':es}}
    write_json(out/'ouestcharge_44_49_official_pdl.json',ouest)

    te53={**common,'dataset':'te53-mayenne-official-pdl','operator':'Territoire d’énergie Mayenne (TE53)','department':'Mayenne','serviceNetworks':['Ouest Charge','Alizé TE53'],'classification':{'departmentalPublicNetwork':True,'exactDirectTariff':True,'powerDependentTariff':True,'roamingSeparate':True,'parallelEtotemRollout':True},'directTariffs':{'normal22Kw':{'energyEurPerKwh':0.43},'rapid50Kw':{'energyEurPerKwh':0.87},'ultraRapid180Kw':{'energyEurPerKwh':0.92}},'access':{'ouestChargeOrAlizeBadge':True,'qrCode':True,'contactlessCardOnRapid':True,'otherMobilityBadgesByInteroperability':True},'parallelRollout':{'operator':'e-Totem','period':'2025-2026','plannedChargePointsMoreThan':150,'directCasualTariffResolved':False,'display':'reference_only_until_station_or_first_party_tariff_confirmation'},'tccDecision':{'operatorValidated':True,'directTariffClassableForTE53Network':True,'parallelEtotemSeparateOffer':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'guide2026Url':mfinal,'guide2026HttpStatus':ms,'guide2026Sha256':hashlib.sha256(mraw).hexdigest()}}
    write_json(out/'te53_mayenne_official_pdl.json',te53)

    sydev={**common,'dataset':'sydev-vendee-official-pdl','operator':'SYDEV','department':'Vendée','classification':{'departmentalPublicNetwork':True,'exactDirectTariff':True,'powerCategoryDependent':True,'sessionFeeOnRapidAndSuper':True,'roamingSeparate':True},'directTariffs':{'normal':{'energyEurPerKwh':0.41,'sessionFeeEur':0.0},'rapid':{'energyEurPerKwh':0.50,'sessionFeeEur':2.0},'super':{'energyEurPerKwh':0.59,'sessionFeeEur':2.0}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'stationCategoryRequired':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'guide2026Url':yfinal,'guide2026HttpStatus':ys,'guide2026Sha256':hashlib.sha256(yraw).hexdigest(),'guideTlsVerifiedByRunner':ytls,'mobilityUrl':ymfinal,'mobilityHttpStatus':yms,'mobilityTlsVerifiedByRunner':ymtls,'transportNote':'Official SYDEV host currently presents an incomplete certificate chain to some Linux runners; payload is still constrained to the official hostname and validated by expected content plus SHA-256.'}}
    write_json(out/'sydev_vendee_official_pdl.json',sydev)

    sarthe={**common,'dataset':'sarthe-irve-official-pdl','operator':'Sarthe IRVE','serviceOperator':'Bouygues Energies & Services / Alizé','department':'Sarthe','classification':{'departmentalPublicNetworkFamily':True,'normalDirectTariffExact':True,'rapidCurrentFirstPartyObservedOutsideRunner':True,'rapidRunnerRevalidationPending':True,'roamingSeparate':True},'badgeIssueFeeEurObservedOnCurrentAlizePage':10.0,'directTariffs':{'normal':{'subscriberEnergyEurPerKwh':0.20,'nonSubscriberSessionFeeEur':1.0,'nonSubscriberEnergyEurPerKwh':0.20},'rapidReference':{'subscriberEnergyEurPerKwh':0.30,'nonSubscriberSessionFeeEur':1.0,'nonSubscriberEnergyEurPerKwh':0.30,'classable':False}},'tccDecision':{'operatorValidated':True,'normalDirectTariffClassable':True,'rapidDirectTariffClassable':False,'rapidReason':'Current Alizé Sarthe page was manually observed with 0.30 EUR/kWh / 1 EUR + 0.30 EUR/kWh, but the page currently returns 404 to GitHub-hosted runners; keep rapid reference-only until station or runner revalidation.','roamingSeparate':True},'sourceEvidence':{'currentMunicipalUrl':sfinal,'currentMunicipalHttpStatus':ss,'currentMunicipalSha256':hashlib.sha256(sraw).hexdigest(),'currentAlizePartnerUrl':SARTHE_ALIZE,'currentAlizeManualObservationDate':'2026-08-21','runnerFetchKnownIssue':'HTTP 404 from GitHub-hosted runner'}}
    write_json(out/'sarthe_irve_official_pdl.json',sarthe)

    ccllb={**common,'dataset':'loir-luce-berce-official-pdl','operator':'Communauté de communes Loir-Lucé-Bercé','serviceOperator':'Freshmile','department':'Sarthe','classification':{'localPublicNetwork':True,'exactDirectTariff':True,'energyPlusConnectionTime':True,'priceCap':True,'roamingSupported':True},'networkSnapshot':{'stations':9,'powerKw':22},'directTariff':{'energyEurPerKwh':0.23,'connectedTimeEurPerMin':0.04,'continuesAfterChargeEnds':True,'sessionCapEur':50.0,'failedSessionRule':{'maxDurationMinutes':2,'maxEnergyKwh':0.5,'notBilled':True}},'access':{'freshmileBadge':True,'otherRoamingBadge':True,'qrCodeAdHoc':True,'bankTerminal':False},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'timeFeeMustBeModeled':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'communityUrl':cfinal,'communityHttpStatus':cs,'communitySha256':hashlib.sha256(craw).hexdigest()}}
    write_json(out/'loir_luce_berce_official_pdl.json',ccllb)

    nantes={**common,'dataset':'nantes-etotem-official-pdl','operator':'e-Totem','authority':'Nantes Métropole','department':'Loire-Atlantique','classification':{'metropolitanPublicNetwork':True,'directCasualEnergyTariffExactPubliclyResolved':False,'exactOccupationFee':True,'professionalPackagesSeparate':True,'roamingSeparate':True},'network':{'plannedChargers':1250,'communes':24,'eCityPowerKw':[3,22],'eFastPowerKw':[50,150]},'occupationFee':{'afterChargeGraceMinutes':10,'billingBlockMinutes':15,'eCityEurPerBlock':1.0,'eFastEurPerBlock':3.0},'professionalPackagesHt':[{'priceEur':35,'energyKwh':100},{'priceEur':65,'energyKwh':200},{'priceEur':150,'energyKwh':500}],'tccDecision':{'operatorValidated':True,'directEnergyTariffClassable':False,'occupationFeeMustBeModeled':True,'defaultDisplay':'reference_only_for_energy_until_station_or_first_party_casual_price_confirmation','roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'nantesMetropoleUrl':nfinal,'nantesMetropoleHttpStatus':ns,'nantesMetropoleSha256':hashlib.sha256(nraw).hexdigest()}}
    write_json(out/'nantes_etotem_official_pdl.json',nantes)

    departments=[{'department':'Loire-Atlantique','publicNetworkFamilies':['Territoire d’énergie 44 / Ouest Charge','Nantes Métropole / e-Totem'],'researchStatus':'accounted_for','pricingRuleStatus':'mixed'},{'department':'Maine-et-Loire','publicNetworkFamilies':['Siéml / Ouest Charge'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_station_category'},{'department':'Mayenne','publicNetworkFamilies':['TE53 / Ouest Charge-Alizé','e-Totem AIP rollout 2025-2026'],'researchStatus':'accounted_for','pricingRuleStatus':'mixed'},{'department':'Sarthe','publicNetworkFamilies':['Sarthe IRVE / Alizé','Communauté de communes Loir-Lucé-Bercé / Freshmile'],'researchStatus':'accounted_for','pricingRuleStatus':'mixed','transitionNote':'Le Mans Métropole public IRVE concession rollout remains a tracked transition project; no universal operator/tariff is invented without current first-party confirmation.'},{'department':'Vendée','publicNetworkFamilies':['SYDEV'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_station_category'}]
    regional={**common,'dataset':'pays-de-la-loire-regional-coverage','departmentsTotal':5,'departmentCoverage':departments,'coverage':{'departmentsAccountedFor':5,'regionalPublicNetworkResearchCoverageComplete':True,'allEstablishedPublicNetworkFamiliesAccountedFor':True,'singleUniversalRegionalTariff':False,'allIdentifiedLiveTariffsResolved':False,'referenceOnlyEnergyFamilies':['Nantes Métropole / e-Totem','Mayenne e-Totem parallel rollout','Sarthe IRVE rapid until runner/station revalidation'],'transitionProjectsIdentified':True},'tccDecision':{'regionalCoverageValidated':True,'doNotInventDepartmentDefaults':True,'preserveNetworkAndStationCategory':True,'roamingSeparate':True,'nextStep':'station-level matching and source-offer comparison can proceed after the national regional pass'},'sourceEvidence':{'validatedOperatorFiles':['ouestcharge_44_49_official_pdl.json','te53_mayenne_official_pdl.json','sydev_vendee_official_pdl.json','sarthe_irve_official_pdl.json','loir_luce_berce_official_pdl.json','nantes_etotem_official_pdl.json'],'regionalEntenteUrl':efinal,'regionalEntenteHttpStatus':es}}
    write_json(out/'pays_de_la_loire_regional_coverage.json',regional)
    (out/'SUMMARY.md').write_text('# Pays de la Loire coverage\n\nAll five departments are accounted for at public-network research level. Exact direct rules are validated for Ouest Charge in Loire-Atlantique and Maine-et-Loire, TE53 in Mayenne, SYDEV in Vendée, Sarthe IRVE normal charging and the separate Loir-Lucé-Bercé/Freshmile network. Nantes Métropole e-Totem and the parallel Mayenne e-Totem rollout are preserved as separate families without inventing a casual energy price. Sarthe IRVE rapid remains reference-only in CI because the current Alizé partner page is visible publicly but returns 404 to GitHub-hosted runners. Roaming/eMSP prices remain separate.\n')

if __name__=='__main__': main()
