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
SARTHE='https://alizecharge.com/partenaires/sarthe-irve/'
NANTES='https://metropole.nantes.fr/actualites/1-250-bornes-de-recharge-deployees-dans-la-metropole-nantaise'


def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:
            return int(getattr(r,'status',200)),r.read(),r.geturl(),True
    except urllib.error.URLError as e:
        # SYDEV currently serves an incomplete TLS chain to some Linux runners.
        # Limit the fallback strictly to the official SYDEV host and still hash/validate the payload.
        if 'sydev-vendee.fr' not in url or 'CERTIFICATE_VERIFY_FAILED' not in str(e):
            raise
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

    os_,oraw,ofinal,otls=fetch(OUEST)
    es,eraw,efinal,etls=fetch(ENTENTE)
    ms,mraw,mfinal,mtls=fetch(TE53)
    ys,yraw,yfinal,ytls=fetch(SYDEV)
    yms,ymraw,ymfinal,ymtls=fetch(SYDEV_MOBILITY)
    ss,sraw,sfinal,stls=fetch(SARTHE)
    ns,nraw,nfinal,ntls=fetch(NANTES)
    if min(os_,es,ms,ys,yms,ss,ns)!=200:
        raise RuntimeError(f'HTTP failure ouest={os_} entente={es} te53={ms} sydev={ys} sydevMobility={yms} sarthe={ss} nantes={ns}')

    sec49=section(oraw,'Maine-et-Loire (49)','Loire-Atlantique (44)')
    require(sec49,'borne normale','0,35','apres la 5eme heure','0,20','borne rapide','0,45','apres la 1ere heure','borne ultra rapide','0,55','45 min','+ 1€','non abonnes',label='Ouest Charge Maine-et-Loire')
    sec44=section(oraw,'Loire-Atlantique (44)','Ille-et-Vilaine (35)')
    require(sec44,'borne normale','0,35','apres la 4eme heure','0,20','borne rapide','0,50','apres la 1ere heure','+ 1€','non abonnes',label='Ouest Charge Loire-Atlantique')
    require(oraw,'Vendée (85)','Mayenne (53)','Sarthe (72)','un de nos partenaires','Alize Charge','Territoire d’énergie','SYDEV',label='Ouest Charge partner map')
    require(eraw,"Territoire d'énergie 44",'Siéml',"Territoire d'énergie 53",'SYDEV','Département de la Sarthe','Région Pays de la Loire',label='regional energy entente')

    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError('pypdf required') from e
    mt='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(mraw)).pages)
    require(mt,'Tarifs de recharge pour les usagers au 01/01/2026','22 kW (normale)','0,43','50 kW (rapide)','0,87','180 kW (ultra-rapide)','0,92','Badge Ouest Charge','Scan du QR Code','Carte bleue sans contact','E-totem','plus de 150 points de recharge','2025 et 2026',label='TE53 2026')

    yt='\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(yraw)).pages)
    require(yt,'GUIDE FINANCIER','2026','Tarifs pour les utilisateurs des IRVE','Non abonné','0,41','0,50','0,59','2,00',label='SYDEV 2026')
    require(ymraw,'bornes','recharge','véhicules électriques',label='SYDEV mobility')
    require(sraw,'SARTHE IRVE','10€','Bornes de recharge normales','0,20€/kWh','1€ + 0,20€/kWh','Bornes de recharge rapides','0,30€/kWh','1€ + 0,30€/kWh','carte bancaire sans contact','itinérance',label='Sarthe IRVE')
    require(nraw,'1 250 bornes','24 communes','e-Totem','e-City','3 à 22 kW','e-Fast','50 à 150 kW','35 € HT','100 kWh','10 minutes','quart d’heure','1 €','3 €',label='Nantes e-Totem')

    common={'schemaVersion':'1.0.0','generatedAt':now(),'country':'FR','region':'Pays de la Loire','publicationStatus':'validated_candidate'}
    ouest={**common,'dataset':'ouestcharge-44-49-official-pdl','operator':'Ouest Charge','classification':{'regionalPublicNetworkFamily':True,'exactDirectTariffByDepartment':True,'subscriberAndNonSubscriber':True,'energyPlusConnectionTime':True,'roamingSeparate':True},'departments':{
      'Loire-Atlantique':{'authority':'Territoire d’énergie 44','tariffs':{'normal':{'energyEurPerKwh':0.35,'freeConnectedMinutes':240,'day0700To2100AfterFreeEurPerMin':0.20},'rapid':{'energyEurPerKwh':0.50,'freeConnectedMinutes':60,'day0700To2100AfterFreeEurPerMin':0.20}},'nonSubscriberSessionFeeEur':1.0},
      'Maine-et-Loire':{'authority':'Siéml','tariffs':{'normal':{'energyEurPerKwh':0.35,'freeConnectedMinutes':300,'day0700To2100AfterFreeEurPerMin':0.20},'rapid':{'energyEurPerKwh':0.45,'freeConnectedMinutes':60,'day0700To2100AfterFreeEurPerMin':0.20},'ultraRapid':{'energyEurPerKwh':0.55,'freeConnectedMinutes':45,'day0700To2100AfterFreeEurPerMin':0.20}},'nonSubscriberSessionFeeEur':1.0}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'departmentAndStationCategoryRequired':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'tariffUrl':ofinal,'tariffHttpStatus':os_,'tariffSha256':hashlib.sha256(oraw).hexdigest(),'regionalEntenteUrl':efinal,'regionalEntenteHttpStatus':es}}
    write_json(out/'ouestcharge_44_49_official_pdl.json',ouest)

    te53={**common,'dataset':'te53-mayenne-official-pdl','operator':'Territoire d’énergie Mayenne (TE53)','department':'Mayenne','serviceNetworks':['Ouest Charge','Alizé TE53'],'classification':{'departmentalPublicNetwork':True,'exactDirectTariff':True,'powerDependentTariff':True,'roamingSeparate':True,'parallelEtotemRollout':True},'directTariffs':{'normal22Kw':{'energyEurPerKwh':0.43},'rapid50Kw':{'energyEurPerKwh':0.87},'ultraRapid180Kw':{'energyEurPerKwh':0.92}},'access':{'ouestChargeOrAlizeBadge':True,'qrCode':True,'contactlessCardOnRapid':True,'otherMobilityBadgesByInteroperability':True},'parallelRollout':{'operator':'e-Totem','period':'2025-2026','plannedChargePointsMoreThan':150,'directCasualTariffResolved':False,'display':'reference_only_until_station_or_first_party_tariff_confirmation'},'tccDecision':{'operatorValidated':True,'directTariffClassableForTE53Network':True,'parallelEtotemSeparateOffer':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'guide2026Url':mfinal,'guide2026HttpStatus':ms,'guide2026Sha256':hashlib.sha256(mraw).hexdigest()}}
    write_json(out/'te53_mayenne_official_pdl.json',te53)

    sydev={**common,'dataset':'sydev-vendee-official-pdl','operator':'SYDEV','department':'Vendée','classification':{'departmentalPublicNetwork':True,'exactDirectTariff':True,'powerCategoryDependent':True,'sessionFeeOnRapidAndSuper':True,'roamingSeparate':True},'directTariffs':{'normal':{'energyEurPerKwh':0.41,'sessionFeeEur':0.0},'rapid':{'energyEurPerKwh':0.50,'sessionFeeEur':2.0},'super':{'energyEurPerKwh':0.59,'sessionFeeEur':2.0}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'stationCategoryRequired':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'guide2026Url':yfinal,'guide2026HttpStatus':ys,'guide2026Sha256':hashlib.sha256(yraw).hexdigest(),'guideTlsVerifiedByRunner':ytls,'mobilityUrl':ymfinal,'mobilityHttpStatus':yms,'mobilityTlsVerifiedByRunner':ymtls,'transportNote':'Official SYDEV host currently presents an incomplete certificate chain to some Linux runners; content is still validated by official hostname, expected PDF/text markers and SHA-256.'}}
    write_json(out/'sydev_vendee_official_pdl.json',sydev)

    sarthe={**common,'dataset':'sarthe-irve-official-pdl','operator':'Sarthe IRVE','serviceOperator':'Alizé','department':'Sarthe','classification':{'departmentalPublicNetwork':True,'exactDirectTariff':True,'subscriberAndNonSubscriber':True,'roamingSeparate':True},'badgeIssueFeeEur':10.0,'directTariffs':{'normal':{'subscriberEnergyEurPerKwh':0.20,'nonSubscriberSessionFeeEur':1.0,'nonSubscriberEnergyEurPerKwh':0.20},'rapid':{'subscriberEnergyEurPerKwh':0.30,'nonSubscriberSessionFeeEur':1.0,'nonSubscriberEnergyEurPerKwh':0.30}},'access':{'alizeApp':True,'contactlessCardOnSomeStations':True,'roamingPartners':True},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'stationCategoryRequired':True,'roamingSeparate':True},'sourceEvidence':{'operatorFirstParty':True,'partnerUrl':sfinal,'partnerHttpStatus':ss,'partnerSha256':hashlib.sha256(sraw).hexdigest()}}
    write_json(out/'sarthe_irve_official_pdl.json',sarthe)

    nantes={**common,'dataset':'nantes-etotem-official-pdl','operator':'e-Totem','authority':'Nantes Métropole','department':'Loire-Atlantique','classification':{'metropolitanPublicNetwork':True,'directCasualEnergyTariffExactPubliclyResolved':False,'exactOccupationFee':True,'professionalPackagesSeparate':True,'roamingSeparate':True},'network':{'plannedChargers':1250,'communes':24,'eCityPowerKw':[3,22],'eFastPowerKw':[50,150]},'occupationFee':{'afterChargeGraceMinutes':10,'billingBlockMinutes':15,'eCityEurPerBlock':1.0,'eFastEurPerBlock':3.0},'professionalPackagesHt':[{'priceEur':35,'energyKwh':100},{'priceEur':65,'energyKwh':200},{'priceEur':150,'energyKwh':500}],'tccDecision':{'operatorValidated':True,'directEnergyTariffClassable':False,'occupationFeeMustBeModeled':True,'defaultDisplay':'reference_only_for_energy_until_station_or_first_party_casual_price_confirmation','roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'nantesMetropoleUrl':nfinal,'nantesMetropoleHttpStatus':ns,'nantesMetropoleSha256':hashlib.sha256(nraw).hexdigest()}}
    write_json(out/'nantes_etotem_official_pdl.json',nantes)

    departments=[
      {'department':'Loire-Atlantique','publicNetworkFamilies':['Territoire d’énergie 44 / Ouest Charge','Nantes Métropole / e-Totem'],'researchStatus':'accounted_for','pricingRuleStatus':'mixed','notes':['Ouest Charge direct rules are exact by station category.','Nantes e-Totem occupation fees are exact; casual energy price remains station/first-party confirmation dependent.']},
      {'department':'Maine-et-Loire','publicNetworkFamilies':['Siéml / Ouest Charge'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_station_category'},
      {'department':'Mayenne','publicNetworkFamilies':['TE53 / Ouest Charge-Alizé','e-Totem AIP rollout 2025-2026'],'researchStatus':'accounted_for','pricingRuleStatus':'mixed','notes':['TE53 22/50/180 kW prices are exact from the 2026 guide.','Parallel e-Totem rollout is identified but its casual direct energy price is not inferred.']},
      {'department':'Sarthe','publicNetworkFamilies':['Sarthe IRVE / Alizé'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_station_category','transitionNote':'Le Mans Métropole public IRVE concession rollout is tracked as a local transition project; no universal operator/tariff is invented without current first-party confirmation.'},
      {'department':'Vendée','publicNetworkFamilies':['SYDEV'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_station_category'}]
    regional={**common,'dataset':'pays-de-la-loire-regional-coverage','departmentsTotal':5,'departmentCoverage':departments,'coverage':{'departmentsAccountedFor':5,'regionalPublicNetworkResearchCoverageComplete':True,'allEstablishedPublicNetworkFamiliesAccountedFor':True,'singleUniversalRegionalTariff':False,'allIdentifiedLiveTariffsResolved':False,'referenceOnlyEnergyFamilies':['Nantes Métropole / e-Totem','Mayenne e-Totem parallel rollout'],'transitionProjectsIdentified':True},'tccDecision':{'regionalCoverageValidated':True,'doNotInventDepartmentDefaults':True,'preserveNetworkAndStationCategory':True,'roamingSeparate':True,'nextStep':'station-level matching and source-offer comparison can proceed after the national regional pass'},'sourceEvidence':{'validatedOperatorFiles':['ouestcharge_44_49_official_pdl.json','te53_mayenne_official_pdl.json','sydev_vendee_official_pdl.json','sarthe_irve_official_pdl.json','nantes_etotem_official_pdl.json'],'regionalEntenteUrl':efinal,'regionalEntenteHttpStatus':es}}
    write_json(out/'pays_de_la_loire_regional_coverage.json',regional)
    (out/'SUMMARY.md').write_text('# Pays de la Loire coverage\n\nAll five departments are accounted for at public-network research level. Exact direct rules are validated for Ouest Charge in Loire-Atlantique and Maine-et-Loire, TE53 in Mayenne, Sarthe IRVE/Alizé and SYDEV in Vendée. Nantes Métropole e-Totem and the parallel Mayenne e-Totem rollout are explicitly preserved as separate families; their casual energy price is not invented when current first-party public evidence does not expose one. Roaming/eMSP prices remain separate.\n')

if __name__=='__main__': main()
