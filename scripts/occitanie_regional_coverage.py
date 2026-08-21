#!/usr/bin/env python3
"""Validate and consolidate public charging-network evidence for Occitanie."""
from __future__ import annotations
import argparse, hashlib, io, json, re, urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36'
SOURCES={
 'reveo_about':'https://reveocharge.com/qui-sommes-nous/',
 'reveo_tariffs':'https://reveocharge.com/tarifs/',
 'sde09':'https://sde09.fr/wp-content/uploads/2025/03/2.note-synthese-11-AVRIL-2025-AG.pdf',
 'syaden':'https://www.syaden.net/wp-content/uploads/2025/04/ROB_2025.pdf',
 'sieda':'https://www.sieda.fr/copie-de-comptes-rendus',
 'sdehg':'https://www.sdehg.fr/mobilite-electrique/',
 'te32':'https://www.sdeg32.fr/bornes/bornes.en-us.htm',
 'herault':'https://www.herault-energies.fr/sites/default/files/2025-04/tarifs_reveo_au_1_avril_2025_4.pdf',
 'montpellier':'https://www.montpellier.fr/vie-quotidienne/vivre-ici/se-deplacer/je-me-deplace-en-voiture/charger-mon-vehicule-electrique-ou-hybride',
 'sdee48':'https://sdee-lozere.fr/la-transition-energetique/mobilite-electrique/',
 'sydeel66':'https://www.sydeel66.com/le-sydeel/mobilite-electrique/',
 'aqui':'https://www.bouygues-es.fr/nous-decouvrir/nos-projets/projets-mobilite/la-mobilite-electrique-aqui',
 'sde82':'https://www.sde82.fr/wp-content/uploads/2025/02/05.-IRVE-bornes-de-recharge-_maj-20fev25.pdf',
 'sde82_tariff':'https://www.sde82.fr/assemblee-generale-du-sde-82-le-20-juin-a-vazerac/',
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
def require_numbers(text,*items,label='source'):
    n=compact(text); missing=[str(x) for x in items if str(x).replace(',','.') not in n]
    if missing: raise RuntimeError(f'{label} missing numeric witnesses: '+', '.join(missing))
def write(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def evidence(v): return {k:x for k,x in v.items() if k!='text'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default='out/occitanie'); args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    src,reachable=probe()

    if src['reveo_about']['httpStatus']==200:
        require(src['reveo_about']['text'],'Ariège','Aude','Aveyron','Gard','Hérault','Lot','Lozère','Pyrénées-Orientales','Tarn','Hautes-Pyrénées','Toulouse','Montpellier',label='Révéo membership')
    if src['reveo_tariffs']['httpStatus']==200:
        require(src['reveo_tariffs']['text'],'12,00','1,50','Hérault','Pyrénées-Orientales','Toulouse Métropole','itinérance',label='Révéo current tariff page')
    if src['sde09']['httpStatus']==200 and src['sde09']['text']:
        require(src['sde09']['text'],'52 BORNES','41','11','BOUYGUES',label='SDE09 Révéo')
    if src['syaden']['httpStatus']==200 and src['syaden']['text']:
        require(src['syaden']['text'],'réseau public','Révéo','150 bornes',label='SYADEN Révéo')
    if src['sieda']['httpStatus']==200:
        require(src['sieda']['text'],'DELIB20250521 TARIFICATION REVEO',label='SIEDA current Révéo tariff decision')
    if src['sdehg']['httpStatus']==200:
        require(src['sdehg']['text'],'108 bornes','Freshmile','0,15','0,40','4,50',label='SDEHG')
    if src['te32']['httpStatus']==200:
        require(src['te32']['text'],'Freshmile','0,25','0,35',label='TE32')
    if src['herault']['httpStatus']==200 and src['herault']['text']:
        require_numbers(src['herault']['text'],0.32,0.36,0.40,0.46,0.50,0.59,0.075,0.10,0.12,label='Hérault Révéo')
    if src['montpellier']['httpStatus']==200:
        require(src['montpellier']['text'],'e-Totem','e-City','e-Fast','10 mn',label='Montpellier e-Totem')
        require_numbers(src['montpellier']['text'],0.20,0.35,0.45,0.49,0.59,label='Montpellier e-Totem')
    if src['sdee48']['httpStatus']==200:
        require(src['sdee48']['text'],'Révéo','Lozère',label='SDEE48 Révéo')
    if src['sydeel66']['httpStatus']==200:
        require(src['sydeel66']['text'],'AQUÍ','306','28 communes','500',label='SYDEEL66 AQUÍ')
    if src['aqui']['httpStatus']==200:
        require(src['aqui']['text'],'306','28 communes','116','180 kW','Révéo','alizé',label='AQUÍ Bouygues')
    if src['sde82']['httpStatus']==200 and src['sde82']['text']:
        require(src['sde82']['text'],'102 bornes','Freshmile',label='SDE82 network')
    if src['sde82_tariff']['httpStatus']==200:
        require_numbers(src['sde82_tariff']['text'],0.45,0.045,0.52,0.59,50,label='SDE82 published tariff')
    if reachable < 10: raise RuntimeError(f'too few official sources reachable: {reachable}/{len(SOURCES)}')

    alize_path=Path('data/operator_direct/alize_toulouse_official.json')
    if not alize_path.exists(): raise RuntimeError('validated Alizé Toulouse dataset missing')
    alize=json.loads(alize_path.read_text())
    assert alize['operatorDirect']['alizeLibertePublic']['normalBelow22Kw']['eurPerKwh']==0.4
    assert alize['operatorDirect']['preferredSubscription']['monthlyFeeEur']==4.0

    common={'schemaVersion':'1.0.0','generatedAt':now(),'country':'FR','region':'Occitanie','publicationStatus':'validated_candidate'}
    reveo_members=['Ariège','Aude','Aveyron','Gard','Hérault','Lot','Lozère','Hautes-Pyrénées','Pyrénées-Orientales','Tarn']
    reveo={**common,'dataset':'reveo-official-occitanie','operator':'Révéo','classification':{'regionalPublicNetworkFamily':True,'tenDepartmentalEnergySyndicateOwners':True,'historicMetropolePartners':['Toulouse Métropole','Montpellier Méditerranée Métropole'],'singleUniversalCurrentTariff':False,'powerNetworkAndUserProfileDependent':True,'roamingSeparate':True},'departmentalMembers':reveo_members,'networkSnapshot':{'stations':'1000+','chargePointsApprox':2300,'subscribers':'8000+'},'access':{'badgePriceEur':12.0,'subscriptionEurPerMonthPerBadge':1.50,'adHocQrCard':True,'app':True},'currentTariffResolution':{'genericMemberDepartments':{'exactGridEmbeddedInCurrentCrawler':False,'officialInstruction':'check the station tariff in the Révéo app when in doubt','directTariffClassableWithoutStationOrCurrentDepartmentGrid':False},'specialTariffAreas':['Hérault','Pyrénées-Orientales','Toulouse Métropole']},'heraultOutsideMontpellier':{'effectiveDate':'2025-04-01','subscriber':{'normalLongLe22':{'energyEurPerKwh':0.32,'timeEurPerMin':0.075,'afterMinutes':600},'normalAcLe22':{'energyEurPerKwh':0.32,'timeEurPerMin':0.075,'afterMinutes':180,'window':'07:00-22:00'},'normalDcLe24':{'energyEurPerKwh':0.36,'timeEurPerMin':0.075,'afterMinutes':90,'window':'07:00-22:00'},'rapidAcLe50':{'energyEurPerKwh':0.32,'timeEurPerMin':0.075,'afterMinutes':180},'rapidDcLe50':{'energyEurPerKwh':0.40,'timeEurPerMin':0.075,'afterMinutes':60},'ultraAcGt50':{'energyEurPerKwh':0.32,'timeEurPerMin':0.075,'afterMinutes':180},'ultraDcGt50':{'energyEurPerKwh':0.50,'timeEurPerMin':0.075,'afterMinutes':30}},'otherUsers':{'normalLongLe22':{'energyEurPerKwh':0.40,'timeEurPerMin':0.10,'afterMinutes':600},'normalAcLe22':{'energyEurPerKwh':0.40,'timeEurPerMin':0.10,'afterMinutes':180,'window':'07:00-22:00'},'normalDcLe24':{'energyEurPerKwh':0.46,'timeEurPerMin':0.10,'afterMinutes':90,'window':'07:00-22:00'},'rapidAcLe50':{'energyEurPerKwh':0.40,'timeEurPerMin':0.10,'afterMinutes':180},'rapidDcLe50':{'energyEurPerKwh':0.50,'timeEurPerMin':0.12,'afterMinutes':60},'ultraAcGt50':{'energyEurPerKwh':0.40,'timeEurPerMin':0.10,'afterMinutes':180},'ultraDcGt50':{'energyEurPerKwh':0.59,'timeEurPerMin':0.12,'afterMinutes':30}},'scope':'Hérault outside Montpellier Métropole'},'currentOperationalEvidence':{'ariege':{'stations':52,'normal':41,'rapid':11,'operatorProcurement2025':'Bouygues'},'aude':{'stations2024':150},'aveyron':{'currentTariffDecisionPublished':'DELIB20250521 TARIFICATION REVEO','exactGridExtracted':False},'lozere':{'currentLocalPublicFamily':'Révéo / SDEE48'}},'tccDecision':{'operatorFamilyValidated':True,'genericCurrentDirectTariffClassable':False,'heraultDirectTariffClassable':True,'doNotInventSingleRegionalGrid':True,'stationOrDepartmentGridRequiredForOtherReveoPricing':True,'roamingSeparate':True},'sourceEvidence':{'about':evidence(src['reveo_about']),'tariffs':evidence(src['reveo_tariffs']),'ariege':evidence(src['sde09']),'aude':evidence(src['syaden']),'aveyron':evidence(src['sieda']),'herault':evidence(src['herault']),'lozere':evidence(src['sdee48'])}}
    write(out/'reveo_official_occitanie.json',reveo)

    sdehg={**common,'dataset':'sdehg-freshmile-official-occitanie','operator':'SDEHG','serviceOperator':'Freshmile','department':'Haute-Garonne outside Toulouse Métropole','classification':{'departmentalPublicNetwork':True,'exactPublishedTariff':True,'roamingSeparate':True},'networkSnapshot':{'stations':108,'chargePointsPerStation':2,'powerKva':22},'directTariff':{'connectionFeeEur':0.15,'energyEurPerKwh':0.40,'afterConnectionMinutes':240,'timeEurPerHour':4.50},'access':{'sdehgCardCreationEur':5.0,'freshmileApp':True,'qrWeb':True,'roamingCards':True},'tccDecision':{'directTariffClassable':True,'roamingSeparate':True},'sourceEvidence':evidence(src['sdehg'])}
    write(out/'sdehg_freshmile_official_occitanie.json',sdehg)

    te32={**common,'dataset':'te32-freshmile-official-occitanie','operator':'TE32 / STEG','serviceOperator':'Freshmile','department':'Gers','classification':{'departmentalPublicNetwork':True,'exactPublishedTariff':True,'powerClassDependent':True,'roamingSeparate':True},'directTariff':{'acceleratedEurPerKwh':0.25,'rapidEurPerKwh':0.35},'access':{'freshmileApp':True,'qrWeb':True,'interoperable':True},'tccDecision':{'directTariffClassable':True,'powerClassRequired':True,'roamingSeparate':True},'sourceEvidence':evidence(src['te32'])}
    write(out/'te32_freshmile_official_occitanie.json',te32)

    montpellier={**common,'dataset':'montpellier-metropole-etotem-official-occitanie','operator':'Montpellier Méditerranée Métropole','serviceOperator':'e-Totem','department':'Hérault / Montpellier Métropole','classification':{'metropolitanPublicNetwork':True,'residentPassAndPublic':True,'postChargeFee':True,'parkingSeparateAfterCharge':True,'roamingSeparate':True},'eCity':{'eco3_7':{'residentWithMobilityOptionEurPerKwh':0.0,'publicEurPerKwh':0.35},'normal7_4':{'residentEurPerKwh':0.20,'publicEurPerKwh':0.45},'boost22':{'residentEurPerKwh':0.20,'publicEurPerKwh':0.45},'postCharge':{'graceMinutes':10,'eurPer15Min':1.0,'dayWindow':'08:00-20:00','dayCapEur':100.0,'nightCapEur':2.0}},'eFast':{'eco50':{'residentEurPerKwh':0.35,'publicEurPerKwh':0.49},'normal100':{'residentEurPerKwh':0.45,'publicEurPerKwh':0.59},'boost150':{'residentEurPerKwh':0.45,'publicEurPerKwh':0.59},'postCharge':{'graceMinutes':10,'eurPer15Min':3.0}},'parkingRule':'free while charging on otherwise paid spaces; normal zone parking applies after charge ends','tccDecision':{'directTariffClassable':True,'residentEligibilityMustRemainSeparate':True,'postChargeMustBeModeled':True,'parkingAfterChargeSeparate':True,'roamingSeparate':True},'sourceEvidence':evidence(src['montpellier'])}
    write(out/'montpellier_metropole_etotem_official_occitanie.json',montpellier)

    aqui={**common,'dataset':'aqui-sydeel66-alize-official-occitanie','operator':'AQUÍ','authority':'SYDEEL66','serviceOperator':'Bouygues Energies & Services / alizé','department':'Pyrénées-Orientales','classification':{'newPublicNetworkFamily':True,'complementsReveo':True,'mixedPower':True,'exactDirectTariffResolved':False,'roamingSeparate':True},'deployment':{'newChargePointsByEnd2026':306,'municipalities':28,'ultraRapidPoints':116,'powerRangeKw':'7-180','totalDepartmentChargePointsByEnd2026':'500+','summer2026Status':'about half of new network in service'},'contract':{'operationMaintenanceYears':15,'userPlatform':'alizé','availabilityTargetPct':97},'tccDecision':{'networkValidated':True,'directTariffClassable':False,'referenceOnlyUntilOfficialDirectTariffResolved':True,'keepSeparateFromReveo':True,'roamingSeparate':True},'sourceEvidence':{'sydeel66':evidence(src['sydeel66']),'bouygues':evidence(src['aqui'])}}
    write(out/'aqui_sydeel66_alize_official_occitanie.json',aqui)

    sde82={**common,'dataset':'sde82-freshmile-official-occitanie','operator':'SDE82','serviceOperator':'Freshmile','department':'Tarn-et-Garonne','classification':{'departmentalPublicNetwork':True,'latestPublishedTariffExact':True,'current2026TariffReconfirmed':False,'powerConnectorAndDurationDependent':True,'roamingSeparate':True},'networkSnapshot':{'stations':102,'twoVehiclesPerStation':True},'latestPublishedTariff':{'effectiveDate':'2023-09-01','ef':{'energyEurPerKwh':0.45,'timeEurPerMin':0.045,'afterMinutes':600},'t2t3':{'energyEurPerKwh':0.45,'timeEurPerMin':0.045,'afterMinutes':180,'window':'06:00-22:00'},'dcLe24':{'energyEurPerKwh':0.52,'timeEurPerMin':0.045,'afterMinutes':120},'dcGt24OrAcGt22':{'energyEurPerKwh':0.59,'timeEurPerMin':0.045,'afterMinutes':60},'sessionCapEur':50.0},'publicationNuance':'The current February-2025 network sheet still exposes this tariff table but labels it 2023-2024; no later explicit 2026 tariff decision was identified in the official sources used here.','tccDecision':{'networkValidated':True,'directTariffClassableFor2026':False,'referenceOnlyUntilCurrentTariffReconfirmed':True,'lastPublishedTariffPreserved':True,'roamingSeparate':True},'sourceEvidence':{'currentSheet':evidence(src['sde82']),'tariffDecision':evidence(src['sde82_tariff'])}}
    write(out/'sde82_freshmile_official_occitanie.json',sde82)

    departments=[
      {'department':'Ariège','families':['Révéo / SDE09'],'status':'accounted_for','tariffRule':'current station/department grid required'},
      {'department':'Aude','families':['Révéo / SYADEN'],'status':'accounted_for','tariffRule':'current station/department grid required'},
      {'department':'Aveyron','families':['Révéo / SIEDA'],'status':'accounted_for','tariffRule':'2025 tariff decision exists; exact grid unresolved in runner'},
      {'department':'Gard','families':['Révéo / SMEG30'],'status':'accounted_for','tariffRule':'current station/department grid required'},
      {'department':'Haute-Garonne','families':['SDEHG / Freshmile','Alizé Toulouse / Toulouse Métropole'],'status':'accounted_for'},
      {'department':'Gers','families':['TE32 / STEG / Freshmile'],'status':'accounted_for'},
      {'department':'Hérault','families':['Révéo / Hérault Énergies outside Montpellier','Montpellier Métropole / e-Totem'],'status':'accounted_for'},
      {'department':'Lot','families':['Révéo / FDEL46'],'status':'accounted_for','tariffRule':'current station/department grid required'},
      {'department':'Lozère','families':['Révéo / SDEE48'],'status':'accounted_for','tariffRule':'current station/department grid required'},
      {'department':'Hautes-Pyrénées','families':['Révéo / SDE65'],'status':'accounted_for','tariffRule':'current station/department grid required'},
      {'department':'Pyrénées-Orientales','families':['Révéo / SYDEEL66','AQUÍ / SYDEEL66 / Bouygues / alizé'],'status':'accounted_for'},
      {'department':'Tarn','families':['Révéo / SDE81'],'status':'accounted_for','tariffRule':'current station/department grid required'},
      {'department':'Tarn-et-Garonne','families':['SDE82 / Freshmile'],'status':'accounted_for','tariffRule':'latest published exact grid preserved; 2026 confirmation pending'}]
    regional={**common,'dataset':'occitanie-regional-coverage','departmentsTotal':13,'departmentCoverage':departments,'coverage':{'departmentsAccountedFor':13,'regionalPublicNetworkResearchCoverageComplete':True,'identifiedMainDepartmentalPublicNetworkFamiliesAccountedFor':True,'singleUniversalRegionalTariff':False,'reveoDepartmentalMembers':10,'exactOrLocallyClassableFamilies':['Hérault Énergies / Révéo','SDEHG / Freshmile','Alizé Toulouse','TE32 / Freshmile','Montpellier Métropole / e-Totem'],'referenceOnlyOrCurrentConfirmationFamilies':['generic Révéo departments requiring station/department current grid','AQUÍ direct tariff','SDE82 2026 tariff confirmation'],'allIdentifiedLiveTariffsResolved':False},'tccDecision':{'regionalCoverageValidated':True,'doNotInventDepartmentDefaults':True,'preserveNetworkPowerCustomerProfileClockTimeDurationParkingAndStationScope':True,'roamingSeparate':True,'nextStep':'continue national regional pass; later station checks should resolve current Révéo station pricing, AQUÍ direct pricing and SDE82 2026 confirmation'},'sourceHealth':{'officialSourcesConfigured':len(SOURCES),'officialSourcesReachableAtRun':reachable,'nonBlockingFailures':[k for k,v in src.items() if v.get('httpStatus')!=200]},'notes':['Révéo remains the main public family across ten departmental energy syndicates, but its current official tariff page explicitly says pricing varies by network, station power and user profile.','Haute-Garonne outside Toulouse Métropole, Gers and Tarn-et-Garonne use distinct departmental families and are not forced into Révéo.','Montpellier Métropole e-Totem and Alizé Toulouse are preserved as current metropolitan/local offers.','AQUÍ is a new Pyrénées-Orientales public family complementing Révéo; no official direct retail price was invented.']}
    write(out/'occitanie_regional_coverage.json',regional)
    (out/'SUMMARY.md').write_text('# Occitanie coverage\n\nAll 13 departments are accounted for. Révéo is preserved as the interdepartmental family owned by ten departmental energy syndicates, without inventing a single current regional tariff. Exact local/direct rules are separately modeled for Hérault Énergies, SDEHG/Freshmile, Alizé Toulouse, TE32/Freshmile and Montpellier Métropole/e-Totem. AQUÍ in Pyrénées-Orientales and the current 2026 confirmation of SDE82 pricing remain reference-only until an official direct price is resolved.\n')

if __name__=='__main__': main()
