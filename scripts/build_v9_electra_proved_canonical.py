#!/usr/bin/env python3
"""Replay archived Electra screenshot/EVSE proofs and unchanged source tariffs.

The historical Electra collector strips EVSE punctuation for identity lookup.
Original national and provider identifiers are retained; ambiguous keys fail closed.
No provider request, topology creation, or tariff inference.
"""
from __future__ import annotations
import argparse, copy, gzip, hashlib, json, re, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v9_rebuild.canonical import key, validate
SOURCE='FR:electra_emsp_exact'
def sha(raw): return hashlib.sha256(raw).hexdigest()
def identity(value): return re.sub('[^A-Z0-9]','',str(value or '').strip().upper())
def normalize(national, archive, ledger, provenance):
    if national.get('source',{}).get('id')!='FR:irve_static' or ledger.get('schemaVersion')!=1:
        raise ValueError('Electra/national identity invalid')
    by_id=defaultdict(list);locations=defaultdict(list)
    for e in national['evses']:
        if e.get('officialEvseId'): by_id[identity(e['officialEvseId'])].append(e)
    for loc in archive['locations']: locations[loc['id']].append(loc)
    stations={x['id']:x for x in national['stations']};cpos={x['id']:x for x in national['cpos']}
    used_evses={};offers=[];rejected=[];seen=set()
    for link in ledger['verifiedLinks']:
        for mapping in link.get('mappings',[]):
            token=(link.get('locationId'),mapping.get('evseId'),mapping.get('chargeTariffId'))
            if token in seen: raise ValueError('Duplicate Electra proof')
            seen.add(token);reason=None
            exact=by_id.get(identity(mapping.get('evseId')),[]);locs=locations.get(token[0],[])
            if (not re.fullmatch('[a-f0-9]{64}',str(link.get('screenshotSha256') or '')) or
                    not link.get('verifiedForPublishedSource') or link.get('requiresSourceTariffUnchanged') is not True):
                reason='proof_incomplete'
            elif len(exact)!=1 or len(locs)!=1: reason='national_or_location_identity_not_unique'
            else:
                tariffs=[t for t in locs[0].get('chargeTariffs',[]) if t.get('chargeTariffId')==token[2]]
                source_evses=[e for e in locs[0].get('evses',[]) if identity(e.get('evseId'))==identity(mapping['evseId'])]
                if len(tariffs)!=1 or len(source_evses)!=1: reason='source_evse_or_tariff_not_unique'
            if reason: rejected.append({'identity':token,'reason':reason});continue
            evse=exact[0];used_evses[evse['id']]=evse
            offers.append({'id':key('FR',SOURCE,'offer',token),'channel':'Electra',
                'scope':{'evseId':evse['id'],'connectorId':None},'officialEvseId':evse['officialEvseId'],
                'sourceOfferId':token[2],'sourceEvseId':mapping['evseId'],
                'calculationStatus':'not_evaluated','proof':'archived_screenshot_and_unique_historical_normalized_evse',
                'rawOffer':{'mapping':copy.deepcopy(mapping),'tariff':copy.deepcopy(tariffs[0]),
                    'evidence':{k:link[k] for k in ['locationId','screenshotSha256','verifiedForPublishedSource','requiresSourceTariffUnchanged']}}})
    station_ids={e['stationId'] for e in used_evses.values()};cpo_ids={stations[s]['cpoId'] for s in station_ids}
    result={'schemaVersion':1,'source':{'id':SOURCE,'artifactSha256':sha(json.dumps(provenance,sort_keys=True).encode()),
        **provenance,'rejected':rejected},'countries':[{'code':'FR'}],
        'stations':[stations[s] for s in sorted(station_ids)],'evses':sorted(used_evses.values(),key=lambda x:x['id']),
        'connectors':[c for c in national['connectors'] if c['evseId'] in used_evses],
        'cpos':[cpos[c] for c in sorted(cpo_ids)],'offers':sorted(offers,key=lambda x:x['id'])}
    validate(result);return result

def build(national_path, folder, ledger_path, output):
    root=Path(__file__).resolve().parents[1]
    if root==output.resolve() or root in output.resolve().parents or output.exists(): raise ValueError('New isolated output required')
    n=national_path.read_bytes();m=(folder/'manifest.json').read_bytes();manifest=json.loads(m)
    raw=(folder/'source-locations.json.gz').read_bytes();ledger_raw=ledger_path.read_bytes()
    if (manifest.get('country')!='FR' or manifest.get('dataset')!='electra-france-platform-national-evse-overlay' or
            manifest.get('sourceArchive',{}).get('sha256')!=sha(raw)): raise ValueError('Electra archive SHA invalid')
    archive=json.loads(gzip.decompress(raw))
    if (archive.get('country')!='FR' or len(archive.get('locations',[]))!=manifest['sourceArchive'].get('locationCount')):
        raise ValueError('Electra archive internal count invalid')
    result=normalize(json.loads(n),archive,json.loads(ledger_raw),
        {'nationalSha256':sha(n),'manifestSha256':sha(m),'archiveSha256':sha(raw),'ledgerSha256':sha(ledger_raw),'generatedAt':manifest.get('generatedAt')})
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n')
    return {'source':SOURCE,'sha256':sha(output.read_bytes()),'offers':len(result['offers']),'rejected':result['source']['rejected']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--national',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--ledger',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(a.national,a.archive,a.ledger,a.out)))
