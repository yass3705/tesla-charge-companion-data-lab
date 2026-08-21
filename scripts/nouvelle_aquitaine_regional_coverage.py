#!/usr/bin/env python3
"""Validate and consolidate public charging network evidence for Nouvelle-Aquitaine."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
SOURCES={
 'mobive_who':'https://mobive.fr/qui-sommes-nous/',
 'mobive_tariffs':'https://mobive.fr/nos-offres-et-tarifs/',
 'sdeg16_2025':'https://sdeg16.fr/wp-content/uploads/2025/04/2025090cs0111-irve-grille-tarifaire-5-mai-2025.pdf',
 'te64_sdirve':'https://www.te64.fr/wp-content/uploads/2024/03/sdirve-64_rapport-public_final.pdf',
 'alterbase':'https://www.seolis.net/alterbase/nos-tarifs/',
 'soregies_2026':'https://www.soregies.fr/wp-content/uploads/sites/10/2026/05/Tarifs-soregies-mobilites-TTC-01-05-26.pdf',
 'soregies_public':'https://www.soregies.fr/professionnels/soregies-mobilites-pro/',
 'limoges_2026':'https://www.limoges-metropole.fr/services/mobilites/bornes-de-recharges-pour-vehicules-electriques/pdf',
 'bordeaux':'https://sedeplacer.bordeaux-metropole.fr/sites/MET-BXMETRO-DRUPAL/files/2024-01/A4%20Affiches%20adh%C3%A9sive%20bornes%20recharge%20Tarifs%202024_0.pdf',
 'larochelle':'https://www.larochelle.fr/vie-quotidienne/stationnement/stationner-dans-les-rues',
 'port_lr_2026':'https://www.larochelle.port.fr/media/20260113-prestations-de-services-2026-version-1bis.pdf',
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
        return int(getattr(r,'status',200)),r.read(),r.geturl(),r.headers.get('content-type','')

def text_from(raw,ctype):
    if raw[:4]==b'%PDF' or 'pdf' in (ctype or '').lower():
        try:
            from pypdf import PdfReader
            return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages)
        except Exception:
            return ''
    return raw.decode('utf-8',errors='replace')

def require(text,*items,label='source'):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError(f'{label} missing: '+', '.join(missing))

def source_probe():
    out={}; ok=0
    for key,url in SOURCES.items():
        try:
            st,raw,final,ctype=fetch(url); txt=text_from(raw,ctype)
            out[key]={'url':final,'httpStatus':st,'sha256':hashlib.sha256(raw).hexdigest(),'text':txt}
            if st==200: ok+=1
        except Exception as exc:
            out[key]={'url':url,'httpStatus':None,'error':type(exc).__name__,'text':''}
    return out,ok

def write(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/nouvelle_aquitaine'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    src,reachable=source_probe()

    # Hard checks on currently stable first-party sources; other sources remain corroborating/non-blocking.
    if src['alterbase']['httpStatus']==200:
        require(src['alterbase']['text'],'18€','0.432','0.528','0.612','0.996',label='AlterBase')
    if src['soregies_2026']['httpStatus']==200 and src['soregies_2026']['text']:
        require(src['soregies_2026']['text'],'4,99','0,42','0,34','0,59','0,47','0,39','0,16','0,01','0,99',label='Sorégies 2026')
    if src['limoges_2026']['httpStatus']==200 and src['limoges_2026']['text']:
        require(src['limoges_2026']['text'],'0,38','0,34','0,29','5€','4€','3€','0,55','2 € / 5 min',label='Limoges Métropole')
    if src['larochelle']['httpStatus']==200:
        require(src['larochelle']['text'],'2h de charge maximum','Depuis février 2023','prix du kWh selon délibération',label='La Rochelle')
    if reachable < 5: raise RuntimeError(f'too few official sources reachable: {reachable}/{len(SOURCES)}')

    common={'schemaVersion':'1.0.0','generatedAt':now(),'country':'FR','region':'Nouvelle-Aquitaine','publicationStatus':'validated_candidate'}

    standard_depts=['Charente','Charente-Maritime','Corrèze','Creuse','Dordogne','Gironde','Landes','Lot-et-Garonne','Haute-Vienne']
    mobive={**common,'dataset':'mobive-official-nouvelle-aquitaine','operator':'MObiVE','currentOperator':'Citeos','mobilityPartner':'Electromaps','classification':{'regionalPublicNetworkFamily':True,'subscriberAndAdHoc':True,'powerDependent':True,'connectionTimeSurcharge':True,'nightExemptionOnAcSurcharge':True,'department64SeparateLegacyGrid':True,'roamingSeparate':True},'subscriptionAnnualEur':18.0,'standardGridDepartments':standard_depts,'standardGridEffectiveDate':'2025-05-05','standardGrid':{
      'nonSubscriber':{
        'acLe8':{'energyEurPerKwh':0.40,'thresholdMinutes':600,'daySurchargeEurPerMin':0.10,'dayWindow':'07:00-22:00','nightSurchargeEurPerMin':0.0},
        'acGt8':{'energyEurPerKwh':0.40,'thresholdMinutes':150,'daySurchargeEurPerMin':0.10,'dayWindow':'07:00-22:00','nightSurchargeEurPerMin':0.0},
        'dc22_39':{'energyEurPerKwh':0.50,'thresholdMinutes':90,'surchargeEurPerMin':0.12},
        'dc40_60':{'energyEurPerKwh':0.55,'thresholdMinutes':60,'surchargeEurPerMin':0.12},
        'dcGt60':{'energyEurPerKwh':0.68,'thresholdMinutes':30,'surchargeEurPerMin':0.12},
        'transactionCapEur':90.0},
      'subscriber':{
        'acLe8':{'energyEurPerKwh':0.35,'thresholdMinutes':600,'daySurchargeEurPerMin':0.08,'dayWindow':'07:00-22:00','nightSurchargeEurPerMin':0.0},
        'acGt8':{'energyEurPerKwh':0.35,'thresholdMinutes':150,'daySurchargeEurPerMin':0.08,'dayWindow':'07:00-22:00','nightSurchargeEurPerMin':0.0},
        'dc22_39':{'energyEurPerKwh':0.40,'thresholdMinutes':90,'surchargeEurPerMin':0.10},
        'dc40_60':{'energyEurPerKwh':0.45,'thresholdMinutes':60,'surchargeEurPerMin':0.10},
        'dcGt60':{'energyEurPerKwh':0.57,'thresholdMinutes':30,'surchargeEurPerMin':0.10},
        'transactionCapEur':50.0}},
      'pyreneesAtlantiques64':{'department':'Pyrénées-Atlantiques','currentPageStatus':'separate 2023 grid still displayed','pageDateAmbiguity':{'tabLabel':'2023-07-05','sectionHeading':'2023-07-03'},'nonSubscriber':{
        'acLe7':{'energyEurPerKwh':0.44,'thresholdMinutes':600,'daySurchargeEurPerMin':0.09,'dayWindow':'07:00-23:00','nightSurchargeEurPerMin':0.0},
        'acGt7':{'energyEurPerKwh':0.55,'thresholdMinutes':180,'daySurchargeEurPerMin':0.09,'dayWindow':'07:00-23:00','nightSurchargeEurPerMin':0.0},
        'dc22_39':{'energyEurPerKwh':0.59,'thresholdMinutes':60,'surchargeEurPerMin':0.09},
        'dc40_60':{'energyEurPerKwh':0.64,'thresholdMinutes':60,'surchargeEurPerMin':0.09},
        'dcGt60':{'energyEurPerKwh':0.68,'thresholdMinutes':30,'surchargeEurPerMin':0.09},'transactionCapEur':50.0},
       'subscriber':{
        'acLe7':{'energyEurPerKwh':0.35,'thresholdMinutes':600,'daySurchargeEurPerMin':0.07,'dayWindow':'07:00-23:00','nightSurchargeEurPerMin':0.0},
        'acGt7':{'energyEurPerKwh':0.44,'thresholdMinutes':180,'daySurchargeEurPerMin':0.07,'dayWindow':'07:00-23:00','nightSurchargeEurPerMin':0.0},
        'dc22_39':{'energyEurPerKwh':0.48,'thresholdMinutes':60,'surchargeEurPerMin':0.07},
        'dc40_60':{'energyEurPerKwh':0.53,'thresholdMinutes':60,'surchargeEurPerMin':0.07},
        'dcGt60':{'energyEurPerKwh':0.57,'thresholdMinutes':30,'surchargeEurPerMin':0.07},'transactionCapEur':30.0}},
      'billingRules':{'startedKwhAndStartedMinuteBillable':True,'successfulChargeDefinitionPreserved':True},
      'tccDecision':{'operatorValidated':True,'standardDirectTariffClassable':True,'department64DirectTariffClassable':True,'departmentAndPowerClassRequired':True,'subscriberSeparate':True,'roamingSeparate':True},
      'sourceEvidence':{'mobiveWho':{k:v for k,v in src['mobive_who'].items() if k!='text'},'mobiveTariffs':{k:v for k,v in src['mobive_tariffs'].items() if k!='text'},'sdeg16Tariff2025':{k:v for k,v in src['sdeg16_2025'].items() if k!='text'},'te64Sdirve':{k:v for k,v in src['te64_sdirve'].items() if k!='text'},'manualWebVerificationDate':'2026-08-21'}}
    write(out/'mobive_official_nouvelle_aquitaine.json',mobive)

    alter={**common,'dataset':'alterbase-deux-sevres-official-nouvelle-aquitaine','operator':'AlterBase','serviceOperator':'SÉOLIS','authority':'SIEDS','department':'Deux-Sèvres','classification':{'departmentalPublicNetwork':True,'subscriberAndOccasional':True,'powerDependent':True,'sessionFeeForOccasional':True,'roamingSeparate':True},'subscriptionAnnualEur':18.0,'subscriberTariffs':{'acLt24':0.432,'dcLt24':0.432,'dcGt25':0.528},'occasionalTariffs':{'acLt24':0.528,'dcLt24':0.528,'dcGt25':0.612,'sessionFeeEur':0.996},'boundaryWarning':'Official wording uses <24 kW and >25 kW; do not silently interpolate exact 24-25 kW boundary cases.','tccDecision':{'operatorValidated':True,'directTariffClassable':True,'powerClassRequired':True,'subscriberSeparate':True,'roamingSeparate':True},'sourceEvidence':{k:v for k,v in src['alterbase'].items() if k!='text'}}
    write(out/'alterbase_deux_sevres_official_nouvelle_aquitaine.json',alter)

    soregies={**common,'dataset':'soregies-vienne-official-nouvelle-aquitaine','operator':'Sorégies Mobilités','authority':'Syndicat Énergies Vienne','department':'Vienne','classification':{'departmentalPublicNetwork':True,'threeAccessOffers':True,'powerAndTimeOfDayDependent':True,'overstayAfterChargeDuration':True,'sessionFee':True,'roamingSeparate':True},'sessionFeeEur':0.99,'timeWindows':{'offPeak':['11:00-18:00','22:00-07:00'],'peak':['07:00-11:00','18:00-22:00']},'publicAdHocDisplayedOnCurrentSite':{'normal22':{'offPeak':0.36,'peak':0.41},'accelerated50':{'offPeak':0.42,'peak':0.47},'rapid200':{'offPeak':0.67,'peak':0.71}},'mobilitesDirectNoSubscription':{'normal22':{'offPeak':0.27,'peak':0.38},'accelerated50':{'offPeak':0.33,'peak':0.44},'rapid200':{'offPeak':0.42,'peak':0.59}},'mobilitesPlus':{'monthlyFeeEur':4.99,'normal22':{'offPeak':0.22,'peak':0.31},'accelerated50':{'offPeak':0.26,'peak':0.36},'rapid200':{'offPeak':0.34,'peak':0.47}},'durationSurcharge':{'normal22':{'afterMinutes':420,'eurPerMin':0.01},'accelerated50':{'afterMinutes':120,'eurPerMin':0.16},'rapid200':{'afterMinutes':60,'eurPerMin':0.39}},'sourceNuance':'Current May-2026 tariff PDF defines Mobilités and Mobilités+; the live Pro page separately displays a higher Public tariff for users without a Sorégies card. Keep all three offers separate.','tccDecision':{'operatorValidated':True,'allThreeOffersSeparate':True,'directTariffsClassable':True,'publicAdHocClassable':True,'powerAndClockTimeRequired':True,'roamingSeparate':True},'sourceEvidence':{'tariffPdf':{k:v for k,v in src['soregies_2026'].items() if k!='text'},'publicPage':{k:v for k,v in src['soregies_public'].items() if k!='text'}}}
    write(out/'soregies_vienne_official_nouvelle_aquitaine.json',soregies)

    bordeaux={**common,'dataset':'bordeaux-metropole-freshmile-official-nouvelle-aquitaine','operator':'Bordeaux Métropole','serviceOperator':'Freshmile','department':'Gironde','classification':{'metropolitanPublicNetwork':True,'exactPublishedTariff':True,'energyPlusConnectionTime':True,'nightTimeFeeExemption':True,'roamingSeparate':True},'directTariff':{'energyEurPerKwh':0.38,'acConnectionSurcharge':{'afterMinutes':240,'eurPerHour':4.0},'dcConnectionSurcharge':{'afterMinutes':120,'eurPerHour':4.0},'nightWindow':'23:00-08:00','nightOnlyEnergyCharged':True,'transactionCapEurTtc':48.0},'access':{'freshmileBadgeOptional':True,'freshmileBadgePurchaseEur':4.99,'subscriptionFeeEur':0.0,'appQrWeb':True},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'acDcRequired':True,'clockTimeRequired':True,'roamingSeparate':True},'sourceEvidence':{k:v for k,v in src['bordeaux'].items() if k!='text'}}
    write(out/'bordeaux_metropole_freshmile_official_nouvelle_aquitaine.json',bordeaux)

    limoges={**common,'dataset':'limoges-metropole-izivia-official-nouvelle-aquitaine','operator':'Limoges Métropole','serviceOperator':'IZIVIA','department':'Haute-Vienne','classification':{'metropolitanPublicNetwork':True,'threeCustomerTiers':True,'dayNightDependent':True,'nightPackage':True,'postChargeFee':True,'roamingSeparate':True},'subscriptions':{'standardMonthlyEur':10.0,'frequencyMonthlyEur':20.0},'tiers':['nonSubscriber','standard','frequency'],'tariffs':{
      'ac22':{'dayWindow':'08:00-20:00','dayEnergy':[0.38,0.34,0.29],'dayPostChargeEurPerHour':[3.0,2.5,2.0],'nightWindow':'20:00-08:00','nightPackage20KwhEur':[5.0,4.0,3.0],'nightExtraEurPerKwh':[0.30,0.25,0.20]},
      'ac22_dc24':{'dayWindow':'08:00-20:00','dayEnergy':[0.42,0.38,0.34],'dayPostChargeEurPerHour':[4.0,3.5,3.0],'nightWindow':'20:00-08:00','nightPackage20KwhEur':[5.0,4.0,3.0],'nightExtraEurPerKwh':[0.30,0.25,0.20]},
      'dc100_150':{'energy':[0.55,0.53,0.49],'postChargeBillingBlockMinutes':5,'postChargeEurPerBlock':2.0}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'customerTierPowerAndClockTimeRequired':True,'nightPackageMustBeModeledAsPackage':True,'dcPostChargeMustRemainFiveMinuteBlocks':True,'roamingSeparate':True},'sourceEvidence':{k:v for k,v in src['limoges_2026'].items() if k!='text'}}
    write(out/'limoges_metropole_izivia_official_nouvelle_aquitaine.json',limoges)

    larochelle={**common,'dataset':'la-rochelle-municipal-irve-official-nouvelle-aquitaine','operator':'Ville de La Rochelle municipal IRVE','department':'Charente-Maritime','classification':{'municipalPublicChargingFamily':True,'currentServiceConfirmed':True,'currentExactKwhPriceResolved':False,'parkingTreatmentVariesBySite':True},'currentRules':{'maxChargeDurationHours':2,'paidSince':'2023-02','billingBasis':'energy delivered','sites':{'VerdunSurface':'charging price by deliberation; parking separate','Arsenal':'charging price by deliberation; parking included','ChasseloupAlbert1':'charging price by deliberation; parking free zone','PlaceFoch':'charging price by deliberation; parking included'},'underground':{'Verdun':'parking paid, charging free','VieuxPortSud':'parking paid, charging free'}},'historicalDeliberation2022':{'system1EnergyEurPerKwhTtc':0.80,'system2EnergyEurPerKwhTtc':1.00,'postChargeGraceMinutes':30,'postChargeEurPer5Min':1.0,'capEurTtc':100.0,'currentUseNotAssumedWithoutFreshConfirmation':True},'tccDecision':{'networkValidated':True,'directTariffClassable':False,'referenceOnlyUntilCurrentDeliberatedKwhPriceConfirmed':True,'parkingMustRemainSiteSpecific':True},'sourceEvidence':{k:v for k,v in src['larochelle'].items() if k!='text'}}
    write(out/'la_rochelle_municipal_irve_official_nouvelle_aquitaine.json',larochelle)

    port={**common,'dataset':'la-rochelle-port-freshmile-official-nouvelle-aquitaine','operator':'Port Atlantique La Rochelle','serviceOperator':'Freshmile','department':'Charente-Maritime','classification':{'publiclyAccessibleLocalSiteFamily':True,'exact2026Tariff':True,'energyPlusConnectedTime':True},'directTariff2026':{'powerKw':22,'energyEurPerKwh':0.48,'connectedTimeEurPerMin':0.02},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'timeFeeMustBeModeled':True,'keepSeparateFromMunicipalAndMobiveNetworks':True},'sourceEvidence':{k:v for k,v in src['port_lr_2026'].items() if k!='text'}}
    write(out/'la_rochelle_port_freshmile_official_nouvelle_aquitaine.json',port)

    departments=[
      {'department':'Charente','families':['MObiVE / SDEG16'],'status':'accounted_for'},
      {'department':'Charente-Maritime','families':['MObiVE / SDEER17','Ville de La Rochelle municipal IRVE','Port Atlantique La Rochelle / Freshmile'],'status':'accounted_for'},
      {'department':'Corrèze','families':['MObiVE / FDEE19 + Syndicat de la Diège'],'status':'accounted_for'},
      {'department':'Creuse','families':['MObiVE / SDEC23'],'status':'accounted_for'},
      {'department':'Dordogne','families':['MObiVE / SDE24'],'status':'accounted_for'},
      {'department':'Gironde','families':['MObiVE / SDEEG + Gironde Energies','Bordeaux Métropole / Freshmile'],'status':'accounted_for'},
      {'department':'Landes','families':['MObiVE / SYDEC40'],'status':'accounted_for'},
      {'department':'Lot-et-Garonne','families':['MObiVE / TE47 + AVERGIES'],'status':'accounted_for'},
      {'department':'Pyrénées-Atlantiques','families':['MObiVE / TE64'],'status':'accounted_for','pricingRule':'department-specific legacy grid'},
      {'department':'Deux-Sèvres','families':['AlterBase / SIEDS / SÉOLIS'],'status':'accounted_for'},
      {'department':'Vienne','families':['Sorégies Mobilités / Syndicat Énergies Vienne'],'status':'accounted_for'},
      {'department':'Haute-Vienne','families':['MObiVE / SEHV','Limoges Métropole / IZIVIA'],'status':'accounted_for'}]
    regional={**common,'dataset':'nouvelle-aquitaine-regional-coverage','departmentsTotal':12,'departmentCoverage':departments,'coverage':{'departmentsAccountedFor':12,'regionalPublicNetworkResearchCoverageComplete':True,'identifiedMainDepartmentalPublicNetworkFamiliesAccountedFor':True,'singleUniversalRegionalTariff':False,'mobiveDepartments':10,'nonMobiveDepartmentNetworks':['AlterBase (79)','Sorégies Mobilités (86)'],'localDistinctFamiliesIncluded':['Bordeaux Métropole / Freshmile','Limoges Métropole / IZIVIA','Ville de La Rochelle municipal IRVE','Port Atlantique La Rochelle / Freshmile'],'allIdentifiedLiveTariffsResolved':False,'referenceOnlyOrBlockedFamilies':['Ville de La Rochelle municipal IRVE current exact kWh price']},'tccDecision':{'regionalCoverageValidated':True,'doNotInventDepartmentDefaults':True,'preserveDepartmentPowerClassCustomerTierClockTimeAndParking':True,'roamingSeparate':True,'nextStep':'continue national regional pass; later station checks should verify source-offer matching and La Rochelle current municipal kWh price'},'sourceHealth':{'officialSourcesConfigured':len(SOURCES),'officialSourcesReachableAtRun':reachable,'nonBlockingFailures':[k for k,v in src.items() if v.get('httpStatus')!=200]},'notes':['MObiVE covers ten Nouvelle-Aquitaine departments; Deux-Sèvres and Vienne use distinct public network families.','Local metropolitan/municipal offers are kept separate from MObiVE and from roaming offers.']}
    write(out/'nouvelle_aquitaine_regional_coverage.json',regional)
    (out/'SUMMARY.md').write_text('# Nouvelle-Aquitaine coverage\n\nAll 12 departments are accounted for. MObiVE covers 10 departments with a common 2025 grid except Pyrénées-Atlantiques (64), which still exposes its separate 2023 grid. Deux-Sèvres is covered by AlterBase and Vienne by Sorégies Mobilités. Distinct local public offers for Bordeaux Métropole, Limoges Métropole and La Rochelle are also preserved separately. The current exact municipal La Rochelle kWh price remains reference-only until a current deliberation is reconfirmed.\n')

if __name__=='__main__': main()
