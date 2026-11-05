#!/usr/bin/env python3
"""Recover already compiled UK offers from identical archived OCPI inputs, offline.

The historical compiler's pure grid/rules functions are reused. Its main() and
PAYG requests are never called. Missing compiled identities retain raw offers.
"""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v9_rebuild.canonical import validate
from v9_rebuild.canonical_uk_ocpi_pair import normalize_uk_ocpi_pair

COMPILER = ROOT / 'scripts/uk_ubitricity_pcpr_validate.py'
spec = importlib.util.spec_from_file_location('historical_uk_ubi', COMPILER)
historical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(historical)
sha = lambda data: hashlib.sha256(data).hexdigest()


def restore(canonical, raw, compiled, raw_sha, compiled_sha):
    expected = normalize_uk_ocpi_pair(raw, artifact_sha256=raw_sha,
                                    source_id='GB:ubitricity_pcpr_direct')
    if canonical != expected or compiled.get('collectedAt') != raw.get('collectedAt'):
        raise ValueError('Canonical/compiled archive does not use identical raw input')
    sources = compiled.get('sources', [])
    if (len(sources) != 1 or sources[0].get('id') != 'ubitricity-pcpr-payg' or
            sources[0].get('pricingScope') != 'cpo_direct_pcpr_verified' or sources[0].get('tariffs') != []):
        raise ValueError('Historical compiled source contract invalid')
    by_identity = {}
    for loc in sources[0]['locations']:
        for evse in loc.get('evses', []):
            for connector in evse.get('connectors', []):
                offer = connector.get('validatedV9Offer')
                if not offer:
                    continue
                identity = (str(loc['id']), evse.get('evse_id'), str(connector['id']))
                if identity in by_identity:
                    raise ValueError('Duplicate compiled connector identity')
                if (loc.get('country_code') != 'GB' or loc.get('party_id') != 'UBI' or
                        loc.get('publish') is not True or loc.get('time_zone') != 'Europe/London'):
                    raise ValueError('Compiled location scope invalid')
                by_identity[identity] = (offer, connector)
    out = copy.deepcopy(canonical)
    stations = {s['id']: s for s in out['stations']}
    evses = {e['id']: e for e in out['evses']}
    connectors = {c['id']: c for c in out['connectors']}
    rules = {}; restored = 0; used = set()
    for offer in out['offers']:
        evse = evses[offer['scope']['evseId']]; connector = connectors[offer['scope']['connectorId']]
        station = stations[evse['stationId']]
        identity = (str(station['sourceStationId']), evse.get('officialEvseId'), str(connector['sourceConnectorId']))
        proven = by_identity.get(identity)
        if not proven:
            offer['calculationHold'] = 'no_archived_compiled_exact_connector_offer'
            continue
        compiled_offer, physical = proven; meta = compiled_offer.get('metadata', {})
        tariff = offer['rawOffer']; tid = offer['sourceTariffKey']
        if (set(compiled_offer) != {'id','provider','kind','subscriptionId','countries','currency','stationIds','evseIds','pricing','metadata'} or
                set(meta) != {'connectorId','tariffId','scope','collectedAt','vatIncluded','paygVerification','pricingSource','idleFeeSource'} or
                compiled_offer.get('provider') != 'Ubitricity' or compiled_offer.get('kind') != 'direct' or
                compiled_offer.get('currency') != 'GBP' or compiled_offer.get('countries') != ['GB'] or
                compiled_offer.get('subscriptionId') is not None or
                compiled_offer.get('stationIds') != [identity[0]] or compiled_offer.get('evseIds') != [identity[1]] or
                meta.get('connectorId') != identity[2] or meta.get('tariffId') != tid or
                meta.get('collectedAt') != raw['collectedAt'] or meta.get('vatIncluded') is not True or
                meta.get('scope') != 'cpo_direct_pcpr_verified' or meta.get('pricingSource') != 'PCPR OCPI first-match' or
                connector['rawSourceFields'].get('tariff_ids') != [tid] or
                physical.get('max_electric_power') != connector['rawSourceFields'].get('max_electric_power') or
                set(tariff) - {'country_code','currency','elements','id','last_updated','party_id','tariff_alt_text','tariff_alt_url'} or
                any(set(el) != {'price_components','restrictions'} or
                    any(set(pc) != {'price','step_size','type','vat'} for pc in el['price_components']) for el in tariff['elements'])):
            raise ValueError('Compiled offer identity, component or provenance mismatch')
        if tid not in rules:
            rules[tid] = historical.rules_for([historical.grid(tariff['elements'], d,
                              allow_parking=tid == historical.NEW_PARKING_TARIFF_ID) for d in range(7)])
        expected_pricing = {'type':'rules','timeZone':'Europe/London','rules':rules[tid]}
        watts = physical.get('max_electric_power')
        if isinstance(watts, (int, float)) and 7000 <= watts <= 22000:
            if meta.get('idleFeeSource') != 'https://ubitricity.com/en/driver/pricing/':
                raise ValueError('Historical idle fee evidence missing')
            expected_pricing['postChargeFee'] = {'eurPerMinute':0.05,'graceMinutes':60,
                                               'exemptLocalWindows':[{'start':'20:00','end':'08:00'}]}
        if compiled_offer.get('pricing') != expected_pricing:
            raise ValueError('Archived calculation differs from historical pure compiler')
        offer['archivedCompiledOffer'] = compiled_offer
        offer['proof'] = 'identical_archived_ocpi_and_compiled_uk_connector'
        used.add(identity); restored += 1
    if used != set(by_identity):
        raise ValueError('Compiled connector lost from canonical archive')
    out['source'].update(rawArtifactSha256=raw_sha, compiledArtifactSha256=compiled_sha,
                         compilerSha256=sha(COMPILER.read_bytes()),
                         artifactSha256=sha((raw_sha + compiled_sha + sha(COMPILER.read_bytes())).encode()))
    validate(out)
    return out, {'source':out['source'], 'compiledOffersRestored':restored,
                 'rawOffersPreserved':len(out['offers']) - restored,
                 'identicalHistoricalInputs':True,'providerRequests':0}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('canonical','raw','compiled','out'): p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    if a.out.exists() or a.out.resolve() == ROOT or ROOT in a.out.resolve().parents:
        raise ValueError('New isolated output required')
    raw_bytes, compiled_bytes = a.raw.read_bytes(), a.compiled.read_bytes()
    out, report = restore(json.loads(a.canonical.read_bytes()), json.loads(gzip.decompress(raw_bytes)),
                          json.loads(gzip.decompress(compiled_bytes)), sha(raw_bytes), sha(compiled_bytes))
    a.out.mkdir(parents=True)
    target = a.out/'GB__ubitricity_pcpr_direct.json'
    target.write_text(json.dumps(out, sort_keys=True, separators=(',',':'),ensure_ascii=False)+'\n')
    report['canonicalSha256'] = sha(target.read_bytes())
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
