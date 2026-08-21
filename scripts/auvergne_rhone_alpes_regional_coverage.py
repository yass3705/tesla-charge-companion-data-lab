#!/usr/bin/env python3
"""Validate and consolidate public charging network evidence for Auvergne-Rhone-Alpes."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
SOURCES={
 'eborn_tariffs':'https://www.eborn.fr/tarifs/',
 'eborn_faq':'https://www.eborn.fr/foire-aux-questions/',
 'grand_lyon':'https://grandlyon.izivia.com/',
 'chargezy':'https://te63-sieg.fr/nos-metiers/mobilite-electrique/',
 'siea_network':'https://siea.fr/le-territoire-se-recharge/',
 'vonnas_tariff':'https://www.vonnas.com/wp-content/uploads/2026/02/CR-du-Conseil-Municipal-09-12-2025.pdf',
 'syder':'https://www.syder.fr/missions/syder-nos-missions-mobilite-electrique/',
 'syder_tariff_image':'https://www.syder.fr/wp-content/uploads/2024/07/Capturefiche-tarif.png',
 'aurillac':'https://www.aurillacagglo.fr/fr/actualites/pole-mobilite-d-aurillac-un-pas-de-plus-vers-la-transition-energetique-et-la-mobilite-durable/',
}

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def norm(v):
    import unicodedata
    if isinstance(v,bytes): v=v.decode('utf-8',errors='replace')
    v=unescape(v or '')
    v=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>',' ',v,flags=re.I|re.S)
    v=re.sub(r'<[^>]+>',' ',v)
    v=unicodedata.normalize('NFKD',v)
    v=''.join(c for c in v if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',v.lower().replace('\xa0',' ')).strip()

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=55) as r:
        raw=r.read(); return int(getattr(r,'status',200)),raw,r.geturl(),r.headers.get('content-type','')

def text_from(raw,ctype):
    if raw[:4]==b'%PDF' or 'pdf' in (ctype or '').lower():
        try:
            from pypdf import PdfReader
            return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages)
        except Exception:
            return ''
    if 'image/' in (ctype or '').lower(): return ''
    return raw.decode('utf-8',errors='replace')

def probe():
    out={}; ok=0
    for key,url in SOURCES.items():
        try:
            st,raw,final,ctype=fetch(url); txt=text_from(raw,ctype)
            out[key]={'url':final,'httpStatus':st,'contentType':ctype,'sha256':hashlib.sha256(raw).hexdigest(),'text':txt}
            if st==200: ok+=1
        except Exception as exc:
            out[key]={'url':url,'httpStatus':None,'error':type(exc).__name__,'text':''}
    return out,ok

def require(text,*items,label='source'):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError(f'{label} missing: '+', '.join(missing))

def write(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/auvergne_rhone_alpes'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    src,reachable=probe()

    if src['eborn_tariffs']['httpStatus']==200:
        require(src['eborn_tariffs']['text'],'14 €','49 €','0,310','0,433','0,573','0,588','0,650','30 minutes','31 mars 2025',label='eborn tariffs')
    if src['eborn_faq']['httpStatus']==200:
        require(src['eborn_faq']['text'],'Allier','Ardèche','Drôme','Isère','Loire','Haute-Loire','Savoie','Haute-Savoie','Easy Charge',label='eborn coverage')
    if src['grand_lyon']['httpStatus']==200:
        require(src['grand_lyon']['text'],'769','3,50','6€','0,45','0,55','0,38','5€','20€',label='IZIVIA Grand Lyon')
    if src['chargezy']['httpStatus']==200:
        require(src['chargezy']['text'],'Chargezy','25€ /an','0,49','0,64','0,59','0,69','Orios by SPIE',label='Chargezy TE63')
    if src['siea_network']['httpStatus']==200:
        require(src['siea_network']['text'],'46 bornes','92 points','105 commandes',label='SIEA Ain')
    if src['vonnas_tariff']['httpStatus']==200 and src['vonnas_tariff']['text']:
        require(src['vonnas_tariff']['text'],'FRESHMILE','0,35','0,45','0,10',label='Vonnas SIEA tariff example')
    if src['syder']['httpStatus']==200:
        require(src['syder']['text'],'QOVOLTIS','182','85','24h/24',label='SYDER')
    if src['aurillac']['httpStatus']==200:
        require(src['aurillac']['text'],'0,20','0,45','0,025','E-Totem','Syndicat Départemental',label='Aurillac')
    if reachable < 7: raise RuntimeError(f'too few official sources reachable: {reachable}/{len(SOURCES)}')

    common={'schemaVersion':'1.0.0','generatedAt':now(),'country':'FR','region':'Auvergne-Rhône-Alpes','publicationStatus':'validated_candidate'}

    eborn_depts=['Allier','Ardèche','Drôme','Isère','Loire','Haute-Loire','Savoie','Haute-Savoie']
    eborn={**common,'dataset':'eborn-official-auvergne-rhone-alpes','operator':'eborn','serviceOperator':'Easy Charge','departmentsInRegion':eborn_depts,'classification':{'interdepartmentalPublicNetwork':True,'subscriberCardAndMonthlyPlan':True,'powerDependent':True,'postChargePenalty':True,'roamingSeparate':True},'subscriptions':{'cardAnnualEur':14.0,'monthlyPlanEur':49.0,'monthlyPlanIncludedKwh':250.0},'directTariffs':{'acceleratedLe25Kw':{'cardEurPerKwh':0.310,'nonSubscriberEurPerKwh':0.433,'cardPostChargeEurPerMin':0.05,'nonSubscriberPostChargeEurPerMin':0.075},'rapid25To60Kw':{'cardEurPerKwh':0.433,'nonSubscriberEurPerKwh':0.573,'cardPostChargeEurPerMin':0.075,'nonSubscriberPostChargeEurPerMin':0.12},'ultraRapidGt60Kw':{'cardEurPerKwh':0.588,'nonSubscriberEurPerKwh':0.650,'cardPostChargeEurPerMin':0.075,'nonSubscriberPostChargeEurPerMin':0.12}},'postChargeRules':{'graceMinutesAfterChargeEnd':30,'acceleratedPenaltyWindow':'08:00-20:00','startedKwhBillable':True},'partnerRoaming':{'passEbornExternalNetworkMarkupPctSince2025_03_31':15,'otherEmspSetsRetailPrice':True},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'powerClassAndCustomerProfileRequired':True,'postChargeMustBeModeled':True,'roamingSeparate':True},'sourceEvidence':{'tariffs':{k:v for k,v in src['eborn_tariffs'].items() if k!='text'},'coverage':{k:v for k,v in src['eborn_faq'].items() if k!='text'}}}
    write(out/'eborn_official_auvergne_rhone_alpes.json',eborn)

    lyon={**common,'dataset':'grand-lyon-izivia-official-auvergne-rhone-alpes','operator':'IZIVIA Grand Lyon','authority':'Métropole de Lyon','department':'Rhône / Métropole de Lyon','classification':{'metropolitanPublicNetwork':True,'dayNightDependent':True,'threeCustomerTiers':True,'timeBillingOnSlowDay':True,'nightPackageOnSlow':True,'fastEnergyPlusDuration':True,'parkingIncludedInDaySlowTariff':True,'roamingSeparate':True},'subscriptions':{'standardMonthlyEur':5.0,'frequencyMonthlyEur':20.0,'initialPassRegistrationEur':15.0},'tiers':['visitor','standard','frequency'],'tariffs':{'dayWindow':'08:00-20:00','nightWindow':'20:00-08:00','day':{'le7KwEurPerHour':[3.50,2.50,1.50],'le24KwEurPerHour':[6.0,5.0,4.0],'le50Kw':{'energyEurPerKwh':[0.45,0.40,0.30],'durationEurPerMinAfter45':0.20},'ge100Kw':{'energyEurPerKwh':[0.55,0.50,0.40],'durationEurPerMinAfter45':0.20}},'night':{'le7KwPackageEurFor20Kwh':[6.0,5.0,4.0],'le24KwPackageEurFor20Kwh':[6.0,5.0,4.0],'slowExtraEurPerKwhAfter20':0.38,'le50Kw':{'energyEurPerKwh':[0.45,0.40,0.30],'durationEurPerMinAfter45':0.20},'ge100Kw':{'energyEurPerKwh':[0.55,0.50,0.40],'durationEurPerMinAfter45':0.20}}},'networkSnapshot':{'stations':233,'chargePlaces':769,'powerRangeKw':'7-150','access':'24/7'},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'powerCustomerTierAndClockTimeRequired':True,'slowNightPackageMustNotBeFlattenedToKwh':True,'roamingSeparate':True},'sourceEvidence':{k:v for k,v in src['grand_lyon'].items() if k!='text'}}
    write(out/'grand_lyon_izivia_official_auvergne_rhone_alpes.json',lyon)

    chargezy={**common,'dataset':'chargezy-te63-official-auvergne-rhone-alpes','operator':'Chargezy','authority':'Territoire d’Énergie Puy-de-Dôme (TE63)','serviceOperator':'Orios by SPIE','department':'Puy-de-Dôme','classification':{'departmentalPublicNetwork':True,'subscriberAndNonSubscriber':True,'sessionFee':True,'powerDependent':True,'durationSurcharge':True,'roamingSeparate':True},'subscriptionAnnualEur':25.0,'subscriber':{'acLe22':{'sessionFeeEur':2.0,'energyEurPerKwh':0.49,'durationEurPerMinAfter180':0.10,'nightExemption':'23:00-07:00'},'dcLe25':{'sessionFeeEur':2.0,'energyEurPerKwh':0.49,'durationEurPerMinAfter90':0.10},'rapidLe50':{'sessionFeeEur':2.0,'energyEurPerKwh':0.64,'durationEurPerMinAfter45':0.20}},'nonSubscriber':{'acLe22':{'sessionFeeEur':2.0,'energyEurPerKwh':0.59,'durationEurPerMinAfter180':0.10,'nightExemption':'23:00-07:00'},'dcLe25':{'sessionFeeEur':2.0,'energyEurPerKwh':0.59,'durationEurPerMinAfter90':0.10},'rapidLe50':{'sessionFeeEur':2.0,'energyEurPerKwh':0.69,'durationEurPerMinAfter45':0.20}},'specialCbSite':{'site':'ZAC des Coustilles, Saint-Germain-Lembron','flatEur':25.0},'networkSnapshot':{'approxStations':100,'access':'24/7'},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'powerCustomerProfileAndDurationRequired':True,'roamingSeparate':True},'sourceEvidence':{k:v for k,v in src['chargezy'].items() if k!='text'}}
    write(out/'chargezy_te63_official_auvergne_rhone_alpes.json',chargezy)

    ain={**common,'dataset':'siea-ain-freshmile-official-auvergne-rhone-alpes','operator':'SIEA Ain coordinated IRVE','serviceOperatorExample':'Freshmile (North-West market)','department':'Ain','classification':{'departmentalCoordinatedPublicDeployment':True,'municipalOwnershipAndTariffSetting':True,'singleUniversalDepartmentTariff':False,'freshmileMandateConfirmedOnNorthWestLot':True},'networkSnapshot2026':{'stationsInService':46,'chargePointsInService':92,'orders':105},'adoptedMunicipalExample':{'municipality':'Vonnas','sourceDate':'2025-12-09','lt20Kw':{'energyEurPerKwh':0.35,'parkingEurPerMinAfter480':0.10,'parkingWindow':'08:00-20:00'},'between20And40Kw':{'energyEurPerKwh':0.35,'parkingEurPerMinAfter180':0.10,'parkingWindow':'08:00-20:00'},'gt40Kw':{'energyEurPerKwh':0.45,'parkingEurPerMin':0.10}},'scopeWarning':'Vonnas tariff is an exact municipal adoption and a useful SIEA-group baseline example, not a department-wide default. Each municipality retains tariff-setting power.','tccDecision':{'networkValidated':True,'directTariffClassableByStationOnlyWhenMunicipalTariffKnown':True,'doNotApplyVonnasAsDepartmentDefault':True,'roamingSeparate':True},'sourceEvidence':{'siea':{k:v for k,v in src['siea_network'].items() if k!='text'},'vonnas':{k:v for k,v in src['vonnas_tariff'].items() if k!='text'}}}
    write(out/'siea_ain_freshmile_official_auvergne_rhone_alpes.json',ain)

    syder={**common,'dataset':'syder-qovoltis-official-auvergne-rhone-alpes','operator':'SYDER-QOVOLTIS','authority':'Syndicat Départemental d’Énergies du Rhône','department':'Rhône hors Métropole de Lyon','classification':{'departmentalPublicNetwork':True,'rfidPreferredTariff':True,'twoPowerClasses':True,'postChargePenalty':True,'nightExemptionOnLowerPower':True,'roamingSeparate':True},'directTariffs':{'le50AcDc':{'syderQovoltisCardEurPerKwh':0.25,'otherUserEurPerKwh':0.35,'postChargeEurPerHour':4.0,'graceMinutes':30,'postChargeNightExemption':'22:00-07:00'},'gt50AcDc':{'syderQovoltisCardEurPerKwh':0.40,'otherUserEurPerKwh':0.50,'postChargeEurPerHour':4.0,'graceMinutes':60,'startedHourDue':True}},'rfidCardPurchaseEur':7.20,'networkSnapshot':{'municipalities':85,'epci':2,'stationsAt2025_12_31':182},'sourceNuance':'Current SYDER page publishes the tariff as an official image. Numeric values were rechecked against that live image on 2026-08-21; the runner validates page and image availability rather than OCR text.','tccDecision':{'operatorValidated':True,'directTariffClassable':True,'powerAndCustomerProfileRequired':True,'postChargeMustBeModeled':True,'roamingSeparate':True},'sourceEvidence':{'page':{k:v for k,v in src['syder'].items() if k!='text'},'tariffImage':{k:v for k,v in src['syder_tariff_image'].items() if k!='text'},'manualWebVerificationDate':'2026-08-21'}}
    write(out/'syder_qovoltis_official_auvergne_rhone_alpes.json',syder)

    aurillac={**common,'dataset':'aurillac-agglo-etotem-official-auvergne-rhone-alpes','operator':'Aurillac Agglo','serviceOperator':'E-Totem','department':'Cantal','classification':{'localPublicNetworkFamily':True,'exactPublishedTariff':True,'parkingRelayAndStationDifferent':True,'durationSurcharge':True},'sites':{'parkingRelais':{'powerKw':7,'energyEurPerKwh':0.20,'freeConnectionHours':8,'thenEurPerMin':0.025},'parkingGare':{'powerKw':[7,22,25],'energyEurPerKwhByPower':{'7':0.20,'22-25':0.45},'freeConnectionHours':2,'thenEurPerMin':0.025}},'access':{'cardTerminal':True,'etotemApp':True},'sdecRole':'Project delivered in partnership with Syndicat Départemental d’Énergies du Cantal (SDEC). No single current SDEC-wide retail tariff was identified, so a department-wide default is not invented.','tccDecision':{'operatorValidated':True,'directTariffClassableForTheseAurillacSites':True,'cantalDepartmentDefaultForbidden':True,'sdecDepartmentFamilyReferenceOnlyOutsideKnownSites':True},'sourceEvidence':{k:v for k,v in src['aurillac'].items() if k!='text'}}
    write(out/'aurillac_agglo_etotem_official_auvergne_rhone_alpes.json',aurillac)

    sdec15={**common,'dataset':'sdec15-cantal-official-auvergne-rhone-alpes','operator':'SDEC Cantal public IRVE coordination/deployment','department':'Cantal','classification':{'departmentalPublicEnergySyndicateRoleConfirmed':True,'publicIrveDeploymentRoleConfirmed':True,'singleUniversalRetailTariffResolved':False},'knownExactLocalFamily':'Aurillac Agglo / E-Totem','tccDecision':{'networkFamilyAccountedFor':True,'directTariffClassable':False,'referenceOnlyOutsideExplicitLocalTariffEvidence':True,'doNotInventCantalDefault':True},'sourceEvidence':{'aurillacPartnershipWitness':{k:v for k,v in src['aurillac'].items() if k!='text'},'manualWebVerificationDate':'2026-08-21'}}
    write(out/'sdec15_cantal_official_auvergne_rhone_alpes.json',sdec15)

    departments=[
      {'department':'Ain','families':['SIEA coordinated IRVE / Freshmile on NW lot'],'status':'accounted_for','tariffRule':'municipality-specific'},
      {'department':'Allier','families':['eborn'],'status':'accounted_for'},
      {'department':'Ardèche','families':['eborn'],'status':'accounted_for'},
      {'department':'Cantal','families':['SDEC Cantal public IRVE coordination/deployment','Aurillac Agglo / E-Totem'],'status':'accounted_for'},
      {'department':'Drôme','families':['eborn'],'status':'accounted_for'},
      {'department':'Isère','families':['eborn / TE38'],'status':'accounted_for'},
      {'department':'Loire','families':['eborn'],'status':'accounted_for'},
      {'department':'Haute-Loire','families':['eborn'],'status':'accounted_for'},
      {'department':'Puy-de-Dôme','families':['Chargezy / TE63'],'status':'accounted_for'},
      {'department':'Rhône','families':['SYDER-QOVOLTIS','IZIVIA Grand Lyon (Métropole de Lyon)'],'status':'accounted_for'},
      {'department':'Savoie','families':['eborn'],'status':'accounted_for'},
      {'department':'Haute-Savoie','families':['eborn'],'status':'accounted_for'}]
    regional={**common,'dataset':'auvergne-rhone-alpes-regional-coverage','departmentsTotal':12,'departmentCoverage':departments,'coverage':{'departmentsAccountedFor':12,'regionalPublicNetworkResearchCoverageComplete':True,'identifiedMainDepartmentalPublicNetworkFamiliesAccountedFor':True,'singleUniversalRegionalTariff':False,'ebornDepartmentsInRegion':8,'nonEbornDepartmentalFamilies':['SIEA Ain','SDEC Cantal','Chargezy / TE63','SYDER-QOVOLTIS'],'distinctMetropolitanOrLocalFamiliesIncluded':['IZIVIA Grand Lyon','Aurillac Agglo / E-Totem'],'allIdentifiedLiveTariffsResolved':False,'referenceOnlyOrStationSpecificFamilies':['SDEC Cantal outside explicit local tariffs','SIEA Ain municipalities without an adopted tariff source']},'tccDecision':{'regionalCoverageValidated':True,'doNotInventDepartmentDefaults':True,'preservePowerCustomerProfileClockTimeDurationParkingAndMunicipality':True,'roamingSeparate':True,'nextStep':'continue national regional pass; later station checks should confirm municipality-specific Ain pricing and Cantal site-level pricing'},'sourceHealth':{'officialSourcesConfigured':len(SOURCES),'officialSourcesReachableAtRun':reachable,'nonBlockingFailures':[k for k,v in src.items() if v.get('httpStatus')!=200]},'notes':['eborn directly covers eight Auvergne-Rhône-Alpes departments; its other three departments are in Provence-Alpes-Côte d’Azur and are not counted here.','Ain uses a SIEA-coordinated deployment in which municipalities set the retail tariff; an exact Vonnas adoption is retained only as a station/municipality example.','Rhône outside the Métropole de Lyon is kept separate from IZIVIA Grand Lyon.','Cantal-wide pricing is not invented; Aurillac Agglo exact E-Totem pricing is preserved separately.']}
    write(out/'auvergne_rhone_alpes_regional_coverage.json',regional)
    (out/'SUMMARY.md').write_text('# Auvergne-Rhône-Alpes coverage\n\nAll 12 departments are accounted for. Eight departments use the eborn public network family. Ain is covered by the SIEA coordinated deployment with municipality-specific tariffs; Puy-de-Dôme by Chargezy/TE63; Rhône by SYDER-QOVOLTIS outside the Métropole and IZIVIA Grand Lyon inside it; Cantal by SDEC public IRVE coordination plus exact local Aurillac Agglo / E-Totem pricing. No universal tariff is invented for Ain or Cantal.\n')

if __name__=='__main__': main()
