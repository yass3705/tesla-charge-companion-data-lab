#!/usr/bin/env python3
"""Independent Allego UK PCPR V9 audit: fail-closed exact connector prices."""
import collections
import gzip
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'data/national/uk_allego_uk_pcpr_v9.json.gz'
REPORT = ROOT / 'reports/uk/allego_uk-pcpr-latest.json'
OUT = ROOT / 'reports/uk/allego_uk-pcpr-validation-latest.json'

def require(value, message):
    if not value:
        raise AssertionError(message)

def main():
    with gzip.open(SRC, 'rt', encoding='utf-8') as f:
        doc = json.load(f)
    report = json.loads(REPORT.read_text(encoding='utf-8'))
    sources = doc.get('sources') or []
    require(len(sources)==1 and sources[0].get('id')=='allego-uk-pcpr-direct', 'Allego CPO source identity mismatch')
    require(doc.get('country')=='GB' and doc.get('collectedAt')==report.get('collectedAt'), 'Snapshot/audit timestamp mismatch')
    require(doc.get('integrationStatus')=='cpo_direct_exact_connector_vat_inclusive_staged', 'Unexpected feed status')
    require(report.get('provider')=='Allego UK', 'Unexpected provider')
    src = sources[0]
    tariffs = src.get('tariffs') or []
    byid = {}
    for t in tariffs:
        tid = str(t.get('id') or '')
        require(tid and tid not in byid, 'Missing/duplicate tariff identifier')
        require(t.get('currency')=='GBP' and t.get('country_code')=='GB', 'Non-UK tariff')
        require(t.get('tccPriceBasis')=='GBP_including_public_UK_VAT', 'Price basis not VAT-gross')
        require(t.get('tccSourcePriceBasis')=='OCPI_2.2.1_excluding_VAT', 'Unexpected tariff source basis')
        require(isinstance(t.get('elements'), list) and t['elements'], 'Missing pricing elements')
        for el in t['elements']:
            require(bool(el.get('price_components')), 'Empty tariff components')
            for pc in el['price_components']:
                require(pc.get('type') in {'ENERGY','TIME','FLAT','PARKING_TIME'}, 'Unsupported billing dimension')
                require(pc.get('vat') is None, 'VAT might be applied twice')
                old,vat,new = [Decimal(str(pc[k])) for k in ('sourcePriceExVat','tccVatRateAppliedPct','price')]
                expected = (old*(1+vat/100)).quantize(Decimal('0.000001'))
                require(new == expected and old >= 0 and 0 <= vat <= 100, 'VAT amount or tax metadata mismatch')
        byid[tid] = t
    locations=src.get('locations') or []
    require(locations and tariffs, 'Empty Allego source')
    seenloc=set()
    seenconn=set()
    operator_counts=collections.Counter()
    referenced=set()
    public_connectors=0
    priced=0
    missing=collections.Counter()
    for loc in locations:
        op=(loc.get('operator') or {}).get('name', '')
        operator_counts[op] += 1
        require(op.strip().lower().startswith('allego'), 'CPO scope contamination')
        require(loc.get('publish') is True and loc.get('country_code')=='GB', 'Non-public/non-GB location')
        assert str(loc.get('country') or '').upper() in ('GB','GBR')
        for field in ('access','access_type','parking_type'):
            require(not any(k in str(loc.get(field) or '').upper() for k in ('PRIVATE','STAFF','EMPLOYEE','FLEET','RESIDENT_ONLY')), 'Non-public access')
        point=loc.get('coordinates') or {}
        try: lat,lon=float(point['latitude']),float(point['longitude'])
        except (KeyError,TypeError,ValueError): raise AssertionError('Invalid coordinates')
        require(49 <= lat <= 61 and -9 <= lon <= 3, 'Outside UK coordinates')
        lkey=(loc.get('country_code'),loc.get('party_id'),str(loc.get('id') or ''))
        require(lkey not in seenloc and all(lkey), 'Duplicate/invalid location')
        seenloc.add(lkey)
        for evse in loc.get('evses') or []:
            require(str(evse.get('status') or '').upper()!='REMOVED', 'Removed EVSE')
            eid=str(evse.get('evse_id') or evse.get('uid') or '')
            require(bool(eid), 'Missing EVSE key')
            for c in evse.get('connectors') or []:
                ckey=(lkey,eid,str(c.get('id') or ''))
                require(ckey not in seenconn and ckey[2], 'Missing/duplicate exact connector')
                seenconn.add(ckey)
                public_connectors += 1
                ids=[str(x) for x in c.get('tariff_ids') or []]
                source_ids=[str(x) for x in c.get('sourceTariffIds') or []]
                require(len(ids)==len(set(ids)), 'Duplicated connector tariff reference')
                require(all(t in byid and byid[t].get('party_id')==loc.get('party_id') for t in ids), 'Missing or cross-CPO tariff reference')
                require(set(ids).issubset(source_ids), 'Invented connector price reference')
                priced += bool(ids)
                if not ids:missing['unpriced_or_ambiguous_connector'] += 1
                referenced.update(ids)
    require(len(locations)==report['publicCpoLocations'] and
            public_connectors==report['publicConnectors'] and
            priced==report['pricedExactConnectors'] and
            public_connectors-priced==report['unpricedPublicConnectors'], 'Collection report count mismatch')
    require(len(referenced)==len(byid), 'Unreferenced/unsafely preserved tariff')
    require(priced>0, 'No connector has a verified Allego CPO tariff')
    output={'provider':'Allego UK', 'country':'GB','collectedAt':doc['collectedAt'],
            'publicLocations':len(locations), 'publicConnectors':public_connectors,
            'exactPricedConnectors':priced, 'unpricedPublicConnectors':public_connectors-priced,
            'distinctTariffs':len(byid), 'operators':dict(operator_counts),
            'unpricedReasons':dict(missing), 'sourceDataset':'data/national/uk_allego_uk_pcpr_v9.json.gz',
            'sourceId':'allego-uk-pcpr-direct','scope':'strict_declared_Allego_CPO_public_only',
            'tariffScope':'first_party_CPO_OCPI_exact_connector_adhoc_candidate',
            'vatPolicy':'GBP inclusive; original OCPI excluding VAT and explicit tax provenance checked per component',
            'validatedForV9':True, 'status':'validated_public_exact_connector'}
    OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
