#!/usr/bin/env python3
"""Validate and consolidate current public charging network evidence for Bretagne."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
OUEST='https://ouestcharge.fr/tarifs-borne-ouest-charge/'
SDE22='https://www.sde22.fr/missions/mobilites-durables/bornes-de-recharge-pour-vehicules-electriques/'
SDEF='https://www.sdef.fr/transition-energetique/mobilite-durable/electrique/'
SDE35='https://www.sde35.fr/mobilite-electrique-bea-ouestcharge'
MORBIHAN='https://morbihan-energies.fr/particulier/reseau-departemental-de-bornes-de-recharge/'
RENNES='https://transport.metropole.rennes.fr/stationnement-rennes/'
BREST='https://brest.fr/gerer-mon-quotidien/transports/se-deplacer-et-stationner-brest-metropole'


def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=90) as r:
        return int(getattr(r,'status',200)),r.read(),r.geturl()


def norm(value):
    import unicodedata
    if isinstance(value,bytes): value=value.decode('utf-8',errors='replace')
    value=unescape(value or '')
    value=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>',' ',value,flags=re.I|re.S)
    value=re.sub(r'<[^>]+>',' ',value)
    value=unicodedata.normalize('NFKD',value)
    value=''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',value.lower().replace('\xa0',' ')).strip()


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
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/bretagne'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)

    os_,oraw,ofinal=fetch(OUEST)
    cs,craw,cfinal=fetch(SDE22)
    fs,fraw,ffinal=fetch(SDEF)
    is_,iraw,ifinal=fetch(SDE35)
    ms,mraw,mfinal=fetch(MORBIHAN)
    rs,rraw,rfinal=fetch(RENNES)
    bs,braw,bfinal=fetch(BREST)
    if min(os_,cs,fs,is_,ms,rs,bs)!=200:
        raise RuntimeError(f'HTTP failure ouest={os_} sde22={cs} sdef={fs} sde35={is_} morbihan={ms} rennes={rs} brest={bs}')

    sec35=section(oraw,'Ille-et-Vilaine (35)','Finistère (29)')
    require(sec35,'borne normale','0,40','5eme heure','0,20','7h','21h','borne rapide','0,55','1ere heure','borne ultra rapide','1€','non abonnes','50€',label='Ouest Charge Ille-et-Vilaine')
    sec29=section(oraw,'Finistère (29)',"Côtes d'Armor (22)")
    require(sec29,'borne normale','0,40','borne rapide','0,55','1ere heure','borne ultra rapide','1€','non abonnes','50€',label='Ouest Charge Finistère')
    sec22=section(oraw,"Côtes d'Armor (22)",'Vous souhaitez')
    require(sec22,'borne normale','0,40','5eme heure','0,20','7h','21h','borne rapide','0,55','borne ultra rapide','1€','non abonnes','50€',label="Ouest Charge Côtes-d'Armor")

    require(craw,'Ouest Charge','202 bornes accélérées','8 bornes rapides','4 bornes','0,33','0,44','0,55',label='SDE22 current page')
    require(fraw,'OuestCharge','Côtes','Ille et Vilaine','2 800 bornes','badge Ouest Charge','10 €',label='SDEF current page')
    require(iraw,'Béa','Ouest Charge','344 points de charge','Ille-et-Vilaine',label='SDE35 current page')
    require(mraw,'Morbihan Énergies','0,40','0,025','0,55','0,10','20 €','8h','4h','5€','FreshMile','24h/24','7j/7',label='Morbihan Energies')
    require(rraw,'C-Park','308 bornes','7 à 22 kW','1 €','0,40 €/kWh','coût du stationnement','parcs-relais','gratuits','200 places',label='Rennes C-Park')
    require(braw,'Easy Charge Service','15 stations','72 points','été 2026','mi 2027','carte bancaire','QR Code',label='Brest Easy Charge')

    common={'schemaVersion':'1.0.0','generatedAt':now(),'country':'FR','region':'Bretagne','publicationStatus':'validated_candidate'}

    ouest={**common,'dataset':'ouestcharge-bretagne-official','operator':'Ouest Charge','classification':{'regionalPublicNetworkFamily':True,'departmentDependentTariff':True,'subscriberAndNonSubscriber':True,'energyPlusConnectionTime':True,'roamingSeparate':True,'sourceConflictDetectedForCotesArmor':True},'departments':{
      "Côtes-d'Armor":{'authority':'SDE22','centralCurrentDisplayedTariff':{'normal':{'energyEurPerKwh':0.40,'freeConnectedMinutes':300,'day0700To2100AfterFreeEurPerMin':0.20},'rapid':{'energyEurPerKwh':0.55,'freeConnectedMinutes':60,'afterFreeEurPerMin':0.20},'ultraRapid':{'energyEurPerKwh':0.55,'freeConnectedMinutes':60,'afterFreeEurPerMin':0.20},'nonSubscriberSessionFeeEur':1.0,'timeSurchargeCapEur':50.0},'localOwnerPageDisplayedTariff':{'normalEnergyEurPerKwh':0.33,'rapidEnergyEurPerKwh':0.44,'ultraRapidEnergyEurPerKwh':0.55},'pricingRuleStatus':'first_party_source_conflict','directTariffClassable':False,'resolutionNeeded':'manual station/app check or latest SDE22 tariff deliberation before ranking direct offer'},
      'Finistère':{'authority':'SDEF / Brest Métropole','tariffs':{'normal':{'energyEurPerKwh':0.40},'rapid':{'energyEurPerKwh':0.55,'freeConnectedMinutes':60,'afterFreeEurPerMin':0.20},'ultraRapid':{'energyEurPerKwh':0.55,'freeConnectedMinutes':60,'afterFreeEurPerMin':0.20}},'nonSubscriberSessionFeeEur':1.0,'timeSurchargeCapEur':50.0,'pricingRuleStatus':'exact_current_central_grid','directTariffClassable':True},
      'Ille-et-Vilaine':{'authority':'SDE35 / Béa','tariffs':{'normal':{'energyEurPerKwh':0.40,'freeConnectedMinutes':300,'day0700To2100AfterFreeEurPerMin':0.20},'rapid':{'energyEurPerKwh':0.55,'freeConnectedMinutes':60,'afterFreeEurPerMin':0.20},'ultraRapid':{'energyEurPerKwh':0.55,'freeConnectedMinutes':60,'afterFreeEurPerMin':0.20}},'nonSubscriberSessionFeeEur':1.0,'timeSurchargeCapEur':50.0,'pricingRuleStatus':'exact_current_central_grid','directTariffClassable':True}},'access':{'ouestChargeBadgeIssueEur':10.0,'mobileApp':True,'qrCodeAdHoc':True,'otherMobilityOperatorsMayAddFees':True},'tccDecision':{'operatorValidated':True,'departmentAndStationCategoryRequired':True,'finistereDirectClassable':True,'illeEtVilaineDirectClassable':True,'cotesArmorDirectClassable':False,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'tariffUrl':ofinal,'tariffHttpStatus':os_,'tariffSha256':hashlib.sha256(oraw).hexdigest(),'sde22Url':cfinal,'sde22HttpStatus':cs,'sdefUrl':ffinal,'sdefHttpStatus':fs,'sde35Url':ifinal,'sde35HttpStatus':is_}}
    write_json(out/'ouestcharge_bretagne_official.json',ouest)

    morbihan={**common,'dataset':'morbihan-energies-official-bretagne','operator':'Morbihan Énergies','technicalPartner':'Freshmile','department':'Morbihan','classification':{'departmentalPublicNetwork':True,'exactDirectTariff':True,'annualSubscriberOffer':True,'energyPlusConnectedTimeForNonSubscriber':True,'longConnectionPenalty':True,'roamingSeparate':True},'subscription':{'annualFeeEur':20.0},'directTariffs':{'normal':{'energyEurPerKwh':0.40,'subscriberConnectedTimeEurPerMin':0.0,'nonSubscriberConnectedTimeEurPerMin':0.025,'longConnectionThresholdMinutes':480,'longConnectionStartedHourEur':5.0},'rapid':{'minimumPowerKw':50,'energyEurPerKwh':0.55,'subscriberConnectedTimeEurPerMin':0.0,'nonSubscriberConnectedTimeEurPerMin':0.10,'longConnectionThresholdMinutes':240,'longConnectionStartedHourEur':5.0}},'access':{'morbihanEnergiesBadge':True,'thirdPartyMobilityBadges':True,'qrCode':True,'contactlessCardOnSomeStations':True,'network24x7':True},'networkSnapshot':{'pointsMoreThan':450,'normalPowerUpToKw':22,'rapidPowerUpToKw':180},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'subscriberOfferSeparate':True,'connectedTimeFeeMustBeModeledForNonSubscriber':True,'longConnectionPenaltyMustBeModeled':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'morbihanUrl':mfinal,'morbihanHttpStatus':ms,'morbihanSha256':hashlib.sha256(mraw).hexdigest()}}
    write_json(out/'morbihan_energies_official_bretagne.json',morbihan)

    rennes={**common,'dataset':'rennes-cpark-official-bretagne','operator':'Rennes Métropole / C-Park','siteOperator':'Citédia','department':'Ille-et-Vilaine','classification':{'metropolitanPublicParkingNetwork':True,'exactBaseChargingTariff':True,'parkingCostSeparate':True,'parkAndRideFreeChargingSeparate':True,'roamingMayAddFees':True},'cPark':{'plannedChargePointsBySummer2026':308,'powerKwRange':[7,22],'connectionFeeEur':1.0,'energyEurPerKwh':0.40,'parkingCostSeparate':True},'parkAndRide':{'slowChargePointsApproximately':200,'chargingFree':True,'accessConditionsMustBePreserved':True},'tccDecision':{'operatorValidated':True,'cParkBaseTariffClassable':True,'parkingMustBeModeledSeparately':True,'parkAndRideFreeOfferRequiresSiteAccessMetadata':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'rennesUrl':rfinal,'rennesHttpStatus':rs,'rennesSha256':hashlib.sha256(rraw).hexdigest()}}
    write_json(out/'rennes_cpark_official_bretagne.json',rennes)

    brest={**common,'dataset':'brest-easycharge-transition-bretagne','operator':'Easy Charge Service','authority':'Brest Métropole','department':'Finistère','classification':{'metropolitanPublicSiteRollout':True,'deploymentInProgress':True,'directEnergyTariffPubliclyResolved':False,'paymentMethodsResolved':True},'rollout':{'sitesOrStationsAnnounced':15,'chargePointsTotal':72,'firstOpenings':'summer 2026','targetCompletion':'mid-2027'},'access':{'bankCard':True,'mobilityBadge':True,'qrCode':True},'tccDecision':{'operatorValidated':True,'directEnergyTariffClassable':False,'defaultDisplay':'reference_only_until_station_or_first_party_price_confirmation','keepSeparateFromOuestCharge':True},'sourceEvidence':{'officialOnly':True,'brestUrl':bfinal,'brestHttpStatus':bs,'brestSha256':hashlib.sha256(braw).hexdigest()}}
    write_json(out/'brest_easycharge_transition_bretagne.json',brest)

    departments=[
      {'department':"Côtes-d'Armor",'publicNetworkFamilies':['SDE22 / Ouest Charge'],'researchStatus':'accounted_for','pricingRuleStatus':'first_party_source_conflict','notes':['Current Ouest Charge central page displays 0.40/0.55/0.55 EUR/kWh by normal/rapid/ultra-rapid category while the current SDE22 owner page still displays 0.33/0.44/0.55. Direct ranking is intentionally blocked until manual resolution.']},
      {'department':'Finistère','publicNetworkFamilies':['SDEF + Brest Métropole / Ouest Charge','Brest Métropole / Easy Charge Service rollout'],'researchStatus':'accounted_for','pricingRuleStatus':'mixed','notes':['Ouest Charge current grid is classable by station category.','Easy Charge Service rollout is identified but the direct casual energy price is not published on the current Brest Métropole page.']},
      {'department':'Ille-et-Vilaine','publicNetworkFamilies':['SDE35 Béa / Ouest Charge','Rennes Métropole / C-Park'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_family','notes':['Rennes C-Park charging base is 1 EUR connection + 0.40 EUR/kWh plus parking; park-and-ride slow charging remains a separate free conditional offer.']},
      {'department':'Morbihan','publicNetworkFamilies':['Morbihan Énergies / Freshmile technical partner'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_subscription_and_station_type'}]

    regional={**common,'dataset':'bretagne-regional-coverage','departmentsTotal':4,'departmentCoverage':departments,'coverage':{'departmentsAccountedFor':4,'regionalPublicNetworkResearchCoverageComplete':True,'identifiedEstablishedPublicNetworkFamiliesAccountedFor':True,'singleUniversalRegionalTariff':False,'allIdentifiedLiveTariffsResolved':False,'referenceOnlyOrBlockedFamilies':["SDE22 / Ouest Charge direct tariff until first-party conflict is resolved",'Brest Métropole / Easy Charge Service direct energy tariff'],'localParkingChargingFamilyIncluded':True},'tccDecision':{'regionalCoverageValidated':True,'doNotInventDepartmentDefaults':True,'preserveNetworkStationCategorySubscriptionAndParking':True,'roamingSeparate':True,'nextStep':'continue national regional pass; manual station checks can later resolve SDE22 conflict and Brest live pricing'},'sourceEvidence':{'validatedOperatorFiles':['ouestcharge_bretagne_official.json','morbihan_energies_official_bretagne.json','rennes_cpark_official_bretagne.json','brest_easycharge_transition_bretagne.json']},'notes':['Coverage concerns identified public/local network families and metropolitan public charging offers, not every private commercial CPO in Bretagne.','Parking fees and operator roaming surcharges must remain separate from direct network charging prices.']}
    write_json(out/'bretagne_regional_coverage.json',regional)

    (out/'SUMMARY.md').write_text('# Bretagne coverage\n\nAll four departments are accounted for at public/local network research level. Ouest Charge covers the public SDE22/SDEF/SDE35 family, Morbihan Energies remains a separate direct network, Rennes C-Park has a distinct metropolitan parking tariff, and Brest Easy Charge Service is tracked as an in-progress metropolitan rollout. The current Cotes-d Armor direct Ouest Charge price is intentionally not classed because two current first-party pages disagree.\n')

if __name__=='__main__': main()
