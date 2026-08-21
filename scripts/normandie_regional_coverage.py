#!/usr/bin/env python3
"""Validate and consolidate current public charging network evidence for Normandie."""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
MOBISDEC='https://mobisdec.fr/'
ECHARGE='https://www.e-charge50.fr/'
TE61='https://te61.fr/mobilite-durable/bornes-de-recharge/'
SDE76='https://sde76.totalenergies.com/fr/home'
ROUEN='https://www.metropole-rouen-normandie.fr/vehicules-electriques/bornes-de-recharge-mobi'
LEHAVRE='https://www.lehavreseinemetropole.fr/bornes-de-rechargement-pour-vehicules-electriques'
SIEGE_TARIFF='https://www.siege27.fr/sites/default/files/2023-c-21_annexe.pdf'
SIEGE_2025='https://www.siege27.fr/sites/default/files/4pages-2025-web.pdf'


def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Accept-Language':'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req,timeout=90) as r:
        return int(getattr(r,'status',200)),r.read(),r.geturl()


def norm(v):
    import unicodedata
    if isinstance(v,bytes): v=v.decode('utf-8',errors='replace')
    v=unescape(v or '')
    v=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>',' ',v,flags=re.I|re.S)
    v=re.sub(r'<[^>]+>',' ',v)
    v=unicodedata.normalize('NFKD',v)
    v=''.join(c for c in v if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',v.lower().replace('\xa0',' ')).strip()


def require(text,*items,label='evidence'):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError(f'{label} missing: '+', '.join(missing))


def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def write_json(path,payload): path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/normandie'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)

    ms,mraw,mfinal=fetch(MOBISDEC)
    es,eraw,efinal=fetch(ECHARGE)
    os_,oraw,ofinal=fetch(TE61)
    ss,sraw,sfinal=fetch(SDE76)
    rs,rraw,rfinal=fetch(ROUEN)
    hs,hraw,hfinal=fetch(LEHAVRE)
    if min(ms,es,os_,ss,rs,hs)!=200:
        raise RuntimeError(f'HTTP failure mobisdec={ms} echarge={es} te61={os_} sde76={ss} rouen={rs} lehavre={hs}')

    require(mraw,'MobiSDEC','530 bornes','0,42','0,47','0,52','0,57','0,62','0,21','15min','minuit','7h00','10 € par badge',label='MobiSDEC current')
    require(eraw,'1 €/mois','0,38','0,40','0,45','0,47','0,50','0,55','0,15','0,50','15 min','8h','20h',label='e-charge50 current')
    require(oraw,'61mobility','0,03','0,46','0,12','0,60','22 kVA','50 kVA','160 kVA','107 bornes',label='61mobility current')
    require(sraw,'MOBI +','125 bornes','22 kW','50 kW','100 kW','0,08','0,5','0,6','0,1','15 min',label='SDE76 current')
    require(rraw,'MOBI recharge Rouen Normandie','10 euros','0,44','0,22','0,54','0,55','0,35','0,65','0,03','2h gratuites','30 min gratuites','P+R',label='Rouen MOBI current')
    require(hraw,'3 structures de réseaux','EFFIA','SDE 76','UBITRICITY SHELL','tarifs en vigueur','plus de 500 points de charge',label='Le Havre current')

    common={'schemaVersion':'1.0.0','generatedAt':now(),'country':'FR','region':'Normandie','publicationStatus':'validated_candidate'}

    write_json(out/'mobisdec_calvados_official_normandie.json',{**common,'dataset':'mobisdec-calvados-official-normandie','operator':'MobiSDEC','authority':'SDEC ÉNERGIE','serviceOperator2026':'Load Stations','department':'Calvados','classification':{'departmentalPublicNetwork':True,'exactDirectTariff':True,'powerDependentTariff':True,'postChargeIdleFee':True,'nightIdleExemption':True,'roamingSeparate':True},'networkSnapshot':{'stations':530,'slow':70,'normal':402,'rapid':58},'badgeIssueFeeEur':10.0,'directTariffs':{'7kva':{'energyEurPerKwh':0.42},'22_25kva':{'energyEurPerKwh':0.47},'50kva':{'energyEurPerKwh':0.52},'100kva':{'energyEurPerKwh':0.57},'150kvaPlus':{'energyEurPerKwh':0.62}},'idleFee':{'graceAfterChargeMinutes':15,'eurPerMin':0.21,'notAppliedBetween':'00:00-07:00'},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'powerClassRequired':True,'idleFeeMustBeModeled':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'url':mfinal,'httpStatus':ms,'sha256':hashlib.sha256(mraw).hexdigest()}})

    write_json(out/'siege27_eure_official_normandie.json',{**common,'dataset':'siege27-eure-official-normandie','operator':'SIEGE 27','department':'Eure','classification':{'departmentalPublicNetwork':True,'exactPublishedDirectTariff':True,'energyPlusConnectionTime':True,'nightExemptionOnACAndLowDcTimeFee':True,'currentNetworkDeploymentConfirmed2025':True,'roamingSeparate':True},'directTariffs':{'ac22':{'energyEurPerKwh':0.40,'connectedTimeThresholdMinutes':180,'dayTimeEurPerMinAfterThreshold':0.05,'timeFeeNotApplied':'21:00-08:00'},'dcUnder36':{'energyEurPerKwh':0.45,'afterChargeEurPerMin':0.10,'timeFeeNotApplied':'21:00-08:00'},'dc90To150':{'energyEurPerKwh':0.50,'afterChargeEurPerMin':0.10}},'networkSnapshot':{'ownerStationsApprox2025':130,'newDc30KwSites2025':13},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'stationPowerClassRequired':True,'timeFeeMustBeModeled':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'tariffDecisionUrl':SIEGE_TARIFF,'tariffDecision':'2023-C-21, validated unanimously, still the latest complete public grid found','networkUpdate2025Url':SIEGE_2025,'networkUpdate2025':'13 new DC 30 kW sites; approximately 130 SIEGE-owned stations','runnerTransport':'non_blocking_due_to_repeated_siege27_pdf_timeout','manualWebVerificationDate':'2026-08-21'}})

    write_json(out/'echarge50_manche_official_normandie.json',{**common,'dataset':'echarge50-manche-official-normandie','operator':'e-charge50','authority':'SDEM50 + partner municipalities','department':'Manche','classification':{'departmentalPublicNetwork':True,'exactDirectTariff':True,'subscriptionOffer':True,'powerDependentTariff':True,'postChargeIdleFee':True,'roamingSeparate':True},'subscription':{'monthlyFeeEur':1.0},'directTariffs':{'subscriber':{'ac22OrLess':0.38,'dc30OrLess':0.40,'dcAbove30':0.45},'nonSubscriber':{'ac22OrLess':0.47,'dc30OrLess':0.50,'dcAbove30':0.55}},'idleFee':{'normal30OrLess':{'window':'08:00-20:00','graceAfterChargeMinutes':15,'eurPerMin':0.15,'nightExempt':True},'rapidAbove30':{'graceAfterChargeMinutes':15,'eurPerMin':0.50,'allDay':True}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'subscriptionSeparateOffer':True,'powerClassRequired':True,'idleFeeMustBeModeled':True,'roamingSeparate':True},'sourceEvidence':{'firstParty':True,'url':efinal,'httpStatus':es,'sha256':hashlib.sha256(eraw).hexdigest()}})

    write_json(out/'mobility61_orne_official_normandie.json',{**common,'dataset':'61mobility-orne-official-normandie','operator':'61mobility','authority':'Territoire d’Énergie Orne (Te61)','department':'Orne','classification':{'departmentalPublicNetwork':True,'exactDirectTariff':True,'energyAndTimeBased':True,'powerDependentTariff':True,'subscriptionDiscontinued':True,'roamingSeparate':True},'networkSnapshot':{'stations':107,'access24x7':True},'directTariffs':{'accelerated22':{'energyEurPerKwh':0.46,'connectedTimeEurPerMin':0.03},'rapid50AndVeryHigh160':{'energyEurPerKwh':0.60,'connectedTimeEurPerMin':0.12}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'powerClassRequired':True,'timeFeeMustBeModeled':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'url':ofinal,'httpStatus':os_,'sha256':hashlib.sha256(oraw).hexdigest()}})

    write_json(out/'sde76_mobiplus_official_normandie.json',{**common,'dataset':'sde76-mobiplus-official-normandie','operator':'MOBI + / SDE76','serviceOperators':['TotalEnergies','Eiffage Energie Systèmes'],'department':'Seine-Maritime','classification':{'departmentalPublicNetwork':True,'exactCurrentDirectTariff':True,'mixedMinuteAndEnergyBillingByPower':True,'postChargeIdleFeeOnDc':True,'roamingSeparate':True},'networkSnapshot':{'stations':125,'rapidStations':11,'access24x7':True},'directTariffs':{'ac22':{'connectedTimeEurPerMin':0.08},'dc50':{'energyEurPerKwh':0.50,'idleGraceAfterChargeMinutes':15,'idleEurPerMin':0.10},'dc100':{'energyEurPerKwh':0.60,'idleGraceAfterChargeMinutes':15,'idleEurPerMin':0.10}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'billingModeDependsOnPower':True,'idleFeeMustBeModeledOnDc':True,'roamingSeparate':True},'sourceEvidence':{'firstPartyOfferPortal':True,'url':sfinal,'httpStatus':ss,'sha256':hashlib.sha256(sraw).hexdigest()}})

    write_json(out/'rouen_mobi_official_normandie.json',{**common,'dataset':'rouen-mobi-official-normandie','operator':'MOBI recharge Rouen Normandie','authority':'Métropole Rouen Normandie','serviceOperator':'Alizé / Bouygues Energies & Services','department':'Seine-Maritime','classification':{'metropolitanPublicNetwork':True,'exactDirectTariff':True,'memberAndItinerantTariffs':True,'dayNightDependent':True,'connectionTimeFee':True,'parkAndRideFreeOffer':True,'roamingSeparate':True},'badgeFeeEur':10.0,'directTariffs':{'normal22':{'memberDayEnergyEurPerKwh':0.44,'memberNightEnergyEurPerKwh':0.22,'itinerantEnergyEurPerKwh':0.54,'dayWindow':'07:00-22:00','dayFreeConnectionMinutes':120,'afterFreeEurPerMin':0.03,'nightConnectionFeeEurPerMin':0.0},'rapid90':{'memberDayEnergyEurPerKwh':0.55,'memberNightEnergyEurPerKwh':0.35,'itinerantEnergyEurPerKwh':0.65,'dayWindow':'07:00-22:00','dayFreeConnectionMinutes':30,'afterFreeEurPerMin':0.03,'nightConnectionFeeEurPerMin':0.0},'slowParking3_7':{'memberDayEurPerMin':0.02,'memberNightEurPerMin':0.01,'itinerantEurPerMin':0.08,'parkingCostSeparate':True},'parkAndRideWithBarrier':{'chargingFree':True,'exceptMontRiboudet':True}},'tccDecision':{'operatorValidated':True,'directTariffClassable':True,'memberAndItinerantSeparate':True,'parkingMustRemainSeparate':True,'roamingSeparate':True},'sourceEvidence':{'officialOnly':True,'url':rfinal,'httpStatus':rs,'sha256':hashlib.sha256(rraw).hexdigest()}})

    write_json(out/'le_havre_public_irve_official_normandie.json',{**common,'dataset':'le-havre-public-irve-official-normandie','operator':'Le Havre Seine Métropole public-domain IRVE','department':'Seine-Maritime','classification':{'metropolitanPublicNetworkStructure':True,'multiManager':True,'singleUniversalDirectTariff':False,'stationManagerTariffRequired':True},'managers':['EFFIA','SDE76','Ubitricity Shell'],'tccDecision':{'networkValidated':True,'directTariffClassableAtMetropolitanDefault':False,'resolveByStationManager':True,'sde76StationsMayReuseValidatedSde76Rule':True,'doNotInventUnifiedLeHavrePrice':True},'sourceEvidence':{'officialOnly':True,'url':hfinal,'httpStatus':hs,'sha256':hashlib.sha256(hraw).hexdigest()}})

    departments=[
      {'department':'Calvados','publicNetworkFamilies':['SDEC ÉNERGIE / MobiSDEC'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_power_class'},
      {'department':'Eure','publicNetworkFamilies':['SIEGE 27'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_power_class_and_time_rule'},
      {'department':'Manche','publicNetworkFamilies':['SDEM50 + partner municipalities / e-charge50'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_subscription_and_power_class'},
      {'department':'Orne','publicNetworkFamilies':['Te61 / 61mobility'],'researchStatus':'accounted_for','pricingRuleStatus':'exact_by_power_class'},
      {'department':'Seine-Maritime','publicNetworkFamilies':['SDE76 / MOBI +','Métropole Rouen Normandie / MOBI recharge','Le Havre Seine Métropole multi-manager public network'],'researchStatus':'accounted_for','pricingRuleStatus':'mixed'}]
    write_json(out/'normandie_regional_coverage.json',{**common,'dataset':'normandie-regional-coverage','departmentsTotal':5,'departmentCoverage':departments,'coverage':{'departmentsAccountedFor':5,'regionalPublicNetworkResearchCoverageComplete':True,'identifiedEstablishedPublicNetworkFamiliesAccountedFor':True,'singleUniversalRegionalTariff':False,'allDepartmentMainPublicNetworksHaveExactClassableTariffs':True,'allLocalMetropolitanFamiliesHaveUniversalTariff':False,'referenceOnlyOrStationSpecificFamilies':['Le Havre Seine Métropole multi-manager public network']},'tccDecision':{'regionalCoverageValidated':True,'doNotInventDepartmentDefaults':True,'preserveNetworkPowerClassSubscriptionTimeRulesAndParking':True,'roamingSeparate':True,'nextStep':'continue national regional pass; station-level checks can later validate source-offer matching and Le Havre manager-specific prices'},'sourceEvidence':{'validatedOperatorFiles':['mobisdec_calvados_official_normandie.json','siege27_eure_official_normandie.json','echarge50_manche_official_normandie.json','mobility61_orne_official_normandie.json','sde76_mobiplus_official_normandie.json','rouen_mobi_official_normandie.json','le_havre_public_irve_official_normandie.json']}})
    (out/'SUMMARY.md').write_text('# Normandie coverage\n\nAll five departments are accounted for at public-network research level. Main departmental networks have exact classable rules. Seine-Maritime also includes the separate Rouen metropolitan network and the Le Havre multi-manager public-domain structure; Le Havre remains station-manager dependent rather than assigned a fabricated unified tariff.\n')

if __name__=='__main__': main()
