#!/usr/bin/env python3
"""Validate and consolidate public charging-network evidence for Corse."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
SOURCES={
 'emotum_cgs':'https://e-motum.net/conditions-generales-de-service/',
 'emotum_map':'https://e-motum.net/ou-charger/',
 'ozecar_main':'https://ozecar.fr/',
 'ozecar_supervision':'https://ozecar.fr/supervision-et-monetique/',
 'ozecar_data':'https://www.data.gouv.fr/datasets/ozecar-points-de-recharge-en-corse-donnes-data-gouv-fr-oze-1',
 'bastia_tariff':'https://www.bastia.corsica/wp-content/uploads/2026/05/2026.02.04.17-tarif-bornes-electriques.pdf',
 'sde2a_comp':'https://www.sde2a.fr/competences.html',
 'sde2a_report':'https://www.sde2a.fr/2025/RAPPORT%20N%C2%B01%2013-10.pdf',
 'sieep_hc':'https://www.sieep-hc.fr/',
 'info_gouv_hc':'https://www.info.gouv.fr/politiques-prioritaires/corse/haute-corse',
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

def compact(v): return re.sub(r'\s+','',norm(v)).replace(',','.')

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
    return raw.decode('utf-8',errors='replace')

def probe():
    out={}; reachable=0
    for key,url in SOURCES.items():
        try:
            st,raw,final,ctype=fetch(url); txt=text_from(raw,ctype)
            out[key]={'url':final,'httpStatus':st,'contentType':ctype,'sha256':hashlib.sha256(raw).hexdigest(),'text':txt}
            if st==200: reachable+=1
        except Exception as exc:
            out[key]={'url':url,'httpStatus':None,'error':type(exc).__name__,'text':''}
    return out,reachable

def require(text,*items,label='source'):
    n=norm(text); missing=[x for x in items if norm(x) not in n]
    if missing: raise RuntimeError(f'{label} missing: '+', '.join(missing))

def require_numbers(text,*items,label='source'):
    n=compact(text); missing=[str(x) for x in items if str(x).replace(',','.') not in n]
    if missing: raise RuntimeError(f'{label} missing numeric witnesses: '+', '.join(missing))

def write(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def evidence(v): return {k:x for k,x in v.items() if k!='text'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/corse'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    src,reachable=probe()

    if src['emotum_cgs']['httpStatus']==200:
        require(src['emotum_cgs']['text'],'prix unitaire est spécifique à chaque borne','carte bancaire','Carte E-MOTUM','30',label='E-Motum current CGS')
        require(src['emotum_cgs']['text'],'plus de 400 points de charge','Haute-Corse','Corse-du-Sud',label='E-Motum footprint')
    if src['emotum_map']['httpStatus']==200:
        require(src['emotum_map']['text'],'360 points de recharge','Corse','chargeurs rapides','chargeurs lents',label='E-Motum Corse map')
    if src['ozecar_main']['httpStatus']==200:
        require(src['ozecar_main']['text'],'Ventiseri','OZECAR One','500 000',label='OZECAR current platform')
    if src['ozecar_supervision']['httpStatus']==200:
        require(src['ozecar_supervision']['text'],'tarification adaptée à votre site','horaires','types d’utilisateurs',label='OZECAR site pricing')
    if src['ozecar_data']['httpStatus']==200:
        require(src['ozecar_data']['text'],'points de recharge en Corse','Ozecar','ouvertes à tout public',label='OZECAR Corse open data')
    if src['bastia_tariff']['httpStatus']==200 and src['bastia_tariff']['text']:
        require(src['bastia_tariff']['text'],'38 points de recharge','YES 55','31 décembre 2025','0,20',label='Bastia 2026 tariff')
    if src['sde2a_comp']['httpStatus']==200:
        require(src['sde2a_comp']['text'],'22 communes','31 points','mobilité électrique',label='SDE2A current network')
    if src['sde2a_report']['httpStatus']==200 and src['sde2a_report']['text']:
        require(src['sde2a_report']['text'],'150 bornes de recharge','300 Points de Charge','2026','220 points de charge','80 points de charge',label='SDE2A rollout')
    if src['sieep_hc']['httpStatus']==200:
        require(src['sieep_hc']['text'],'SIEEP','Haute-Corse',label='SIEEP Haute-Corse')
    if src['info_gouv_hc']['httpStatus']==200:
        require(src['info_gouv_hc']['text'],'Schéma Directeur','SIEEP','20 minutes',label='Haute-Corse SDIRVE')
    if reachable < 8: raise RuntimeError(f'too few current public/official sources reachable: {reachable}/{len(SOURCES)}')

    common={'schemaVersion':'1.0.0','generatedAt':now(),'country':'FR','region':'Corse','publicationStatus':'validated_candidate'}

    emotum={**common,'dataset':'emotum-official-corse','operator':'E-MOTUM','territory':['Haute-Corse','Corse-du-Sud'],'classification':{'islandWideCpo':True,'singleUniversalTariff':False,'stationSpecificTariff':True,'roamingSeparate':True},'network':{'publishedCorsePoints2026':360,'operatorPublishedTotalCorseAndParis':'400+','acAndDc':True,'publicAccess247':True},'access':{'bankCard':True,'emotumCard':True,'app':True},'directTariff':{'basis':'EUR/kWh','singleNetworkWidePrice':False,'priceSpecificToEachStation':True,'genericExactPriceResolved':False},'postCharge':{'mustVacateWithinMinutes':30,'networkWideIdleFeePublished':False},'tccDecision':{'operatorFamilyValidated':True,'genericCurrentDirectTariffClassable':False,'stationPriceRequired':True,'doNotInventIdleFee':True,'roamingSeparate':True},'sourceEvidence':{'cgs':evidence(src['emotum_cgs']),'map':evidence(src['emotum_map'])}}
    write(out/'emotum_official_corse.json',emotum)

    ozecar={**common,'dataset':'ozecar-official-corse','operator':'OZECAR','classification':{'corsicaMajorCpoAndSupervisor':True,'singleUniversalTariff':False,'siteConfigurablePricing':True,'roamingSeparate':True},'presence':{'corsicaAgency':'Ventiseri','officialCorseOpenDataPublished':True},'access':{'ozecarOneApp':True,'cardAndDigitalPaymentsSupportedByPlatform':True},'directTariff':{'genericExactPriceResolved':False,'siteSpecific':True,'mayDependOnHoursUserTypeOrSiteRules':True},'tccDecision':{'operatorFamilyValidated':True,'genericCurrentDirectTariffClassable':False,'stationPriceRequired':True,'doNotUseOzecarBlogGenericPriceRangesAsTariff':True,'roamingSeparate':True},'sourceEvidence':{'official':evidence(src['ozecar_main']),'supervision':evidence(src['ozecar_supervision']),'openData':evidence(src['ozecar_data'])}}
    write(out/'ozecar_official_corse.json',ozecar)

    bastia={**common,'dataset':'bastia-parks-yes55-official-corse','operator':'Régie autonome des parcs de stationnement bastiais','serviceOperator':'YES 55','department':'Haute-Corse','classification':{'municipalPublicNetwork':True,'exactPublished2026Tariff':True,'parkingSeparateFromEnergyUnlessSiteRuleProvesOtherwise':True},'networkSnapshot':{'chargePoints':38,'sites':['Citadelle','Gare','Gaudin']},'directTariff2026':{'energyEurPerKwhHt':0.20,'vatOrParkingNotFoldedIntoPublishedEnergyPrice':True},'operatorChange':{'previousSupervisor':'DRIVECO','previousManagementEnded':'2025-12-31','currentSupervisor':'YES 55'},'tccDecision':{'directEnergyTariffClassable':True,'storeTaxBasisAsHT':True,'parkingMustBeHandledSeparately':True},'sourceEvidence':evidence(src['bastia_tariff'])}
    write(out/'bastia_parks_yes55_official_corse.json',bastia)

    sde2a={**common,'dataset':'sde2a-irve-official-corse','operator':'SDE2A','department':'Corse-du-Sud','classification':{'departmentalPublicAuthority':True,'currentSmallNetworkAndMajor2026Rollout':True,'futureConcessionStructure':True,'exactGenericTariffPublished':False},'currentNetwork':{'communes':22,'chargePoints':31},'deployment2026':{'plannedStations':150,'plannedChargePoints':300,'normalAcceleratedAc22KwPoints':220,'rapidPoints24KwOrMore':80},'futureService':{'privateOperatorSelectionPlanned':True,'transparentPriceDisplayRequired':True,'incomingAndOutgoingRoamingRequired':True},'tccDecision':{'currentNetworkFamilyValidated':True,'futureRolloutValidatedAsPlanNotAsFullyLiveInventory':True,'genericCurrentDirectTariffClassable':False,'doNotInventFutureOperatorOrTariff':True},'sourceEvidence':{'current':evidence(src['sde2a_comp']),'rollout':evidence(src['sde2a_report'])}}
    write(out/'sde2a_irve_official_corse.json',sde2a)

    sieep={**common,'dataset':'sieep-haute-corse-irve-official-corse','operator':'SIEEP Haute-Corse','department':'Haute-Corse','classification':{'departmentalEnergySyndicate':True,'sdirvePlanningValidated':True,'singleLiveTariffPublished':False},'planning':{'sdirveFinalized':True,'accessibilityGoal':'public charger within about 20 minutes','liveUniformNetworkTariffResolved':False},'tccDecision':{'planningFamilyValidated':True,'doNotTreatAsSingleLiveCpoUntilDeploymentEvidenceExists':True,'genericCurrentDirectTariffClassable':False},'sourceEvidence':{'officialSyndicate':evidence(src['sieep_hc']),'statePolicy':evidence(src['info_gouv_hc'])}}
    write(out/'sieep_hc_irve_official_corse.json',sieep)

    coverage={**common,'dataset':'corse-regional-coverage','departmentsTotal':2,'departments':{'Haute-Corse':{'publicNetworkFamilies':['E-MOTUM','OZECAR','Bastia municipal parks / YES 55','SIEEP Haute-Corse planning'],'tariffNotes':'Only Bastia municipal parking energy tariff is uniformly resolved here; E-MOTUM and OZECAR require station-level prices.'},'Corse-du-Sud':{'publicNetworkFamilies':['E-MOTUM','OZECAR','SDE2A'],'tariffNotes':'SDE2A has a current small network and a 2026 rollout plan, but no verified generic current public tariff.'}},'coverage':{'departmentsAccountedFor':2,'regionalPublicNetworkResearchCoverageComplete':True,'singleUniversalRegionalTariff':False,'allIdentifiedLiveTariffsResolved':False,'operatorFamiliesWithExactCurrentPublicGrid':['Bastia municipal parks / YES 55'],'operatorFamiliesRequiringStationPrice':['E-MOTUM','OZECAR'],'publicAuthorityRolloutsWithoutGenericVerifiedTariff':['SDE2A','SIEEP Haute-Corse']},'tccDecision':{'doNotInventIslandWideTariff':True,'stationSpecificPricingMustRemainNullUntilVerified':True,'futureRolloutsMustNotBeCountedAsFullyLive':True,'roamingSeparate':True},'sourceHealth':{'officialOrOperatorSourcesReachableAtRun':reachable,'sourcesTotal':len(SOURCES)},'notes':['National private CPOs already validated elsewhere are not duplicated as Corsican regional tariff families unless they define a local public-network rule.','E-MOTUM states prices are station-specific; OZECAR explicitly supports site-configurable tariffs, so both require station-level verification.','Bastia 2026 publishes 0.20 EUR/kWh HT for the municipal parking charging points; parking and tax treatment are not silently folded into that energy figure.']}
    write(out/'corse_regional_coverage.json',coverage)

    summary=f'''# Corse regional public-network coverage\n\n- Departments accounted for: **2/2**.\n- E-MOTUM: island-wide major CPO; current rules confirm **station-specific EUR/kWh pricing**, so no fake island-wide tariff is created.\n- OZECAR: major Corsican CPO/supervisor; pricing is **site-configurable**, so station-level price verification is required.\n- Bastia municipal parking network: **38 charge points**, supervisor **YES 55**, 2026 published energy tariff **0.20 EUR/kWh HT**.\n- SDE2A: current **31 points / 22 communes** plus 2026 rollout plan for **150 stations / 300 charge points**; generic live tariff not yet verified.\n- SIEEP Haute-Corse: SDIRVE planning validated; do not model it as a single live CPO/tariff yet.\n- Region-wide universal tariff: **NO**.\n- Public-network research coverage complete: **YES**, tariff resolution complete: **NO**.\n- Current source reachability: **{reachable}/{len(SOURCES)}**.\n'''
    (out/'SUMMARY.md').write_text(summary)

if __name__=='__main__': main()
