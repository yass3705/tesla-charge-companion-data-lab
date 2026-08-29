#!/usr/bin/env python3
"""Apply validated direct-CPO tariff evidence to the staged German catalog.

Direct CPO evidence takes precedence over AFIR in the staging preferred-tariff
view. EWE Go has one scalar own-network price. EnBW intercharge direct has
connector-class-specific AC/DC pricing, so no unsafe site scalar is invented.
Production pricing.rankable remains false.
"""
from __future__ import annotations
import argparse,gzip,json
from collections import Counter
from pathlib import Path

def load_gz(path:Path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)
def save_gz(path:Path,data:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt',encoding='utf-8',compresslevel=9) as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
def load_json(path:Path):return json.loads(path.read_text(encoding='utf-8'))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--catalog',type=Path,default=Path('data/germany/germany_non_tesla_catalog_staging_tariff_classified.json.gz'))
    ap.add_argument('--ewe',type=Path,default=Path('data/germany/ewe_go_direct_tariff.json'))
    ap.add_argument('--enbw',type=Path,default=Path('data/germany/enbw_direct_tariff.json'))
    ap.add_argument('--output',type=Path,default=Path('data/germany/germany_non_tesla_catalog_staging_direct_cpo.json.gz'))
    ap.add_argument('--manifest',type=Path,default=Path('data/germany/germany_non_tesla_catalog_staging_direct_cpo_manifest.json'))
    args=ap.parse_args()
    catalog=load_gz(args.catalog);ewe=load_json(args.ewe);enbw=load_json(args.enbw)
    if catalog.get('dataset')!='germany-national-non-tesla-catalog-staging-tariff-classified':raise RuntimeError('unexpected catalog dataset')
    if ewe.get('dataset')!='germany-ewe-go-direct-tariff':raise RuntimeError('unexpected EWE dataset')
    if enbw.get('dataset')!='germany-enbw-direct-tariff':raise RuntimeError('unexpected EnBW dataset')

    ewe_ops=set(ewe['operator']['bnetzaExactOperators']);enbw_ops=set(enbw['operator']['bnetzaExactOperators'])
    ewe_own=ewe['directOwnNetwork'];enbw_own=enbw['directOwnNetwork']
    if ewe_own.get('rankableCandidate') is not True:raise RuntimeError('EWE not eligible')
    if enbw.get('scope',{}).get('siteScalarPriceSafe') is not False:raise RuntimeError('EnBW scalar safety contract changed')

    provider_counts=Counter();scalar_sites=0;connector_class_sites=0;afir_candidates_overridden=0;direct_without_afir=0
    afir_deltas=Counter();afir_price_pairs=Counter();outside_exact=0
    exact_all=ewe_ops|enbw_ops

    for site in catalog.get('sites') or []:
        pricing=site.setdefault('pricing',{});pricing['rankable']=False;pricing['stagingPreferredTariff']=None;pricing['directCpo']=None
        op=site.get('operator')
        if op in ewe_ops:
            provider_counts['EWE Go']+=1;scalar_sites+=1
            pricing['directCpo']={
                'provider':'EWE Go','operatorExactMatch':op,'sourceDataset':ewe['dataset'],'sourceUrl':ewe['source']['url'],'sourceSha256':ewe['source']['sha256'],
                'tariffModel':'site_scalar','currency':ewe_own['currency'],'eurPerKwh':ewe_own['eurPerKwh'],'taxIncluded':ewe_own['taxIncluded'],
                'monthlyFeeEur':ewe_own['monthlyFeeEur'],'blockingFee':ewe_own['blockingFee'],'acDcSamePrice':ewe_own['acDcSamePrice'],
                'scope':'operator-own-network','stagingRankableCandidate':True,'requiresConnectorClass':False
            }
            pricing['stagingPreferredTariff']={'sourceType':'direct_cpo','provider':'EWE Go','selectionMode':'site_scalar','currency':'EUR','eurPerKwh':ewe_own['eurPerKwh'],'taxIncluded':True,'reason':'direct_cpo_precedes_afir','productionRankable':False}
            afir_candidate=bool(pricing.get('stagingRankableCandidate'));afir_price=pricing.get('stagingEffectiveEurPerKwh')
            if afir_candidate and afir_price is not None:
                afir_candidates_overridden+=1;delta=round(float(afir_price)-float(ewe_own['eurPerKwh']),6);afir_deltas[delta]+=1
                afir_price_pairs[(round(float(afir_price),6),round(float(ewe_own['eurPerKwh']),6))]+=1
                pricing['directVsAfir']={'afirEurPerKwh':afir_price,'directEurPerKwh':ewe_own['eurPerKwh'],'afirMinusDirectEurPerKwh':delta,'preferred':'direct_cpo'}
            else:direct_without_afir+=1
        elif op in enbw_ops:
            provider_counts['EnBW mobility+']+=1;connector_class_sites+=1;direct_without_afir+=int(not pricing.get('stagingRankableCandidate'))
            tariffs=enbw_own['connectorClassTariffs']
            pricing['directCpo']={
                'provider':'EnBW mobility+','operatorExactMatch':op,'sourceDataset':enbw['dataset'],'sourceUrl':enbw['source']['url'],'sourceSha256':enbw['source']['sha256'],
                'tariffModel':'connector_class','accessMethod':enbw_own['accessMethod'],'monthlyFeeEur':enbw_own['monthlyFeeEur'],
                'connectorClassTariffs':tariffs,'scope':'operator-own-network','stagingRankableCandidate':False,'requiresConnectorClass':True
            }
            pricing['stagingPreferredTariff']={
                'sourceType':'direct_cpo','provider':'EnBW mobility+','selectionMode':'connector_class','connectorClassTariffs':tariffs,
                'reason':'direct_cpo_precedes_afir_but_connector_class_required','productionRankable':False
            }

    for site in catalog.get('sites') or []:
        if (site.get('pricing') or {}).get('directCpo') and site.get('operator') not in exact_all:outside_exact+=1

    total_direct=sum(provider_counts.values())
    catalog['schemaVersion']='0.4.0';catalog['dataset']='germany-national-non-tesla-catalog-staging-direct-cpo'
    catalog['scope'].update({'directCpoTariffsIncluded':True,'directCpoPrecedesAfirInStaging':True,'connectorClassDirectTariffsSupported':True,'tariffsRankable':False,'publishesToTcc':False})
    s=catalog['stats'];s['directCpoSites']=total_direct;s['directCpoProviders']=dict(provider_counts);s['directCpoSiteScalarSites']=scalar_sites;s['directCpoConnectorClassRequiredSites']=connector_class_sites
    s['directCpoAfirCandidatesOverridden']=afir_candidates_overridden;s['directCpoSitesWithoutRankableAfirCandidate']=direct_without_afir;s['directCpoAppliedOutsideExactOperator']=outside_exact
    s['eweGoDirectVsAfirDeltaDistribution']=[{'afirMinusDirectEurPerKwh':d,'sites':n} for d,n in afir_deltas.most_common()]
    s['eweGoAfirDirectPricePairs']=[{'afirEurPerKwh':p[0],'directEurPerKwh':p[1],'sites':n} for p,n in afir_price_pairs.most_common()]
    catalog.setdefault('sources',{})['eweGoDirectTariff']={'generatedAt':ewe.get('generatedAt'),'source':ewe.get('source'),'ownNetwork':ewe_own,'roamingPartnerStoredNotApplied':ewe.get('roamingPartner')}
    catalog['sources']['enbwDirectTariff']={'generatedAt':enbw.get('generatedAt'),'source':enbw.get('source'),'ownNetwork':enbw_own}
    save_gz(args.output,catalog)
    manifest={'schemaVersion':'0.4.0','dataset':catalog['dataset'],'countryCode':'DE','stagedOnly':True,'publishesToTcc':False,'productionRankingEnabled':False,'catalogFile':args.output.name,'stats':s,'scope':catalog['scope']}
    args.manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('TCC_GERMANY_DIRECT_CPO_OVERLAY='+json.dumps({'directCpoSites':total_direct,'providers':dict(provider_counts),'scalarSites':scalar_sites,'connectorClassSites':connector_class_sites,'afirCandidatesOverridden':afir_candidates_overridden,'outsideExactOperator':outside_exact,'pricePairs':s['eweGoAfirDirectPricePairs'][:20]},ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
