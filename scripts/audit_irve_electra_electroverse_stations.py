#!/usr/bin/env python3
"""One-off read-only proof-based station overlap, France Data Lab.

STRICT: a station belongs to platform X ∩ IRVE if a source EVSE ID/physical
reference matches an IRVE PDC ID uniquely, either literally or after
separator/case normalization. No matching by name, position, CPO, power,
station-level crosswalk or inferred group equivalence.
All cardinalities in the report are STATIONS, not EVSEs.
"""
import collections
import datetime as dt
import gzip
import json
import pathlib
import re

ROOT=pathlib.Path(__file__).resolve().parents[1]
def load_json(path):
    path=ROOT/path
    if str(path).endswith('.gz'):
        with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)
    return json.loads(path.read_text(encoding='utf-8'))
def literal(x):
    return str(x or '').strip().upper()
def normal(x):
    return re.sub('[^A-Z0-9]','',literal(x))
def index_unique(rows):
    index=collections.defaultdict(set)
    for station,pdc in rows:
        key=normal(pdc)
        if key:index[key].add(station)
    unique={key:next(iter(stations)) for key,stations in index.items() if len(stations)==1}
    ambiguous={key for key,stations in index.items() if len(stations)>1}
    return unique,ambiguous

irve_manifest=load_json('data/national/france-irve-static-v9/manifest.json')
national=load_json('data/national/france-irve-static-v9/all.json.gz')
irve_ids=set();pairs=[]
for row in national:
    sid=str(row[0] if isinstance(row,list) and row else '')
    if not sid:continue
    irve_ids.add(sid)
    for config in row[8] if len(row)>8 and isinstance(row[8],list) else []:
        for pdc in config[6] if isinstance(config,list) and len(config)>6 and isinstance(config[6],list) else []:
            pairs.append((sid,pdc))
unique_pdc,ambiguous_pdc=index_unique(pairs)
assert len(irve_ids)==irve_manifest['stationCount'],(len(irve_ids),irve_manifest['stationCount'])

# Source archive is the full France-compatible Electra eMSP raw collection.
electra_manifest=load_json('data/platforms/electra/france/manifest.json')
electra_raw=load_json('data/platforms/electra/france/source-locations.json.gz')
electra_locations=electra_raw.get('locations') or []
electra_station_ids=set()
electra_exact_literal=set()
electra_exact_normal_only=set()
electra_locations_matched=set()
electra_locations_multi=set()
electra_refs=0
electra_unmatched=0
electra_ambiguous_refs=0
literal_index=collections.defaultdict(set)
for station,pdc in pairs:
    if literal(pdc):literal_index[literal(pdc)].add(station)
unique_literal={k:next(iter(v)) for k,v in literal_index.items() if len(v)==1}
for loc in electra_locations:
    source_id=str(loc.get('id',''))
    matches=set()
    for evse in (loc.get('evses') or []):
        key=normal(evse.get('evseId'))
        if not key:continue
        electra_refs+=1
        sid=unique_pdc.get(key)
        if sid:
            matches.add(sid)
            electra_station_ids.add(sid)
            lit=literal(evse.get('evseId'))
            if unique_literal.get(lit)==sid:electra_exact_literal.add(sid)
            else:electra_exact_normal_only.add(sid)
        elif key in ambiguous_pdc:electra_ambiguous_refs+=1
        else:electra_unmatched+=1
    if matches:
        electra_locations_matched.add(source_id)
        if len(matches)>1:electra_locations_multi.add(source_id)

# Electroverse raw tariff station cache (128 JSON shards).
ev_manifest=load_json('data/electroverse/tariff_cache/manifest.json')
ev_station_ids=set()
ev_exact_literal=set()
ev_exact_normal_only=set()
ev_locations_matched=set()
ev_locations_multi=set()
ev_cache_location_ids=set()
ev_refs=0
ev_unmatched=0
ev_ambiguous_refs=0
for shard in ev_manifest['shards']:
    raw=load_json('data/electroverse/tariff_cache/'+shard['file'])
    for cache_id,row in (raw.get('stations') or {}).items():
        source_id=str(row.get('electroverseLocationPk') or cache_id)
        ev_cache_location_ids.add(source_id)
        matches=set()
        for evse in (row.get('tariff') or {}).get('evses') or []:
            key=normal(evse.get('physicalReference'))
            if not key:continue
            ev_refs+=1
            sid=unique_pdc.get(key)
            if sid:
                matches.add(sid)
                ev_station_ids.add(sid)
                lit=literal(evse.get('physicalReference'))
                if unique_literal.get(lit)==sid:ev_exact_literal.add(sid)
                else:ev_exact_normal_only.add(sid)
            elif key in ambiguous_pdc:ev_ambiguous_refs+=1
            else:ev_unmatched+=1
        if matches:
            ev_locations_matched.add(source_id)
            if len(matches)>1:ev_locations_multi.add(source_id)

both=electra_station_ids&ev_station_ids
result={
  'definition':'IRVE station counted only when Electroverse physicalReference / Electra evseId equals a globally unique IRVE PDC identifier (case/separators normalized). No geospatial/manual matches.',
  'generatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
  'sourceVersions':{
    'IRVE':irve_manifest.get('generatedAt'),
    'ElectraEMSP':electra_manifest.get('generatedAt'),
    'ElectroverseRawTariffCache':ev_manifest.get('generatedAt')
  },
  'stationCounts':{
    'IRVE':len(irve_ids),
    'ElectraEMSPFranceCompatibleSourceLocations':len(electra_locations),
    'ElectroverseRawCachedLocations':len(ev_cache_location_ids)
  },
  'exactMatchStationCounts':{
    'IRVE_and_ElectraEMSP':len(electra_station_ids),
    'IRVE_and_Electroverse':len(ev_station_ids),
    'ElectraEMSP_and_Electroverse_via_the_same_IRVE_station':len(both),
    'IRVE_and_ElectraEMSP_and_Electroverse':len(both),
    'IRVE_only':len(irve_ids-(electra_station_ids|ev_station_ids)),
    'IRVE_and_Electra_only':len(electra_station_ids-ev_station_ids),
    'IRVE_and_Electroverse_only':len(ev_station_ids-electra_station_ids),
    'exact_literal_IRVE_Electra':len(electra_exact_literal),
    'exact_literal_IRVE_Electroverse':len(ev_exact_literal),
    'normalized_only_IRVE_Electra':len(electra_station_ids-electra_exact_literal),
    'normalized_only_IRVE_Electroverse':len(ev_station_ids-ev_exact_literal),
  },
  'platformSourceLocationProofCounts':{
    'ElectraLocationsWithAtLeastOneExactNationalPdc':len(electra_locations_matched),
    'ElectraLocationsReferringToMultipleIrveStationIds':len(electra_locations_multi),
    'ElectroverseLocationsWithAtLeastOneExactNationalPdc':len(ev_locations_matched),
    'ElectroverseLocationsReferringToMultipleIrveStationIds':len(ev_locations_multi)
  },
  'diagnostics':{
    'ambiguousIrvePdcKeysAcrossStationIds':len(ambiguous_pdc),
    'ElectraSourceEvseRefsPresent':electra_refs,'ElectraSourceRefsNotFound':electra_unmatched,
    'ElectraSourceRefsAmbiguousNational':electra_ambiguous_refs,
    'ElectroverseSourcePhysicalRefsPresent':ev_refs,'ElectroverseSourceRefsNotFound':ev_unmatched,
    'ElectroverseSourceRefsAmbiguousNational':ev_ambiguous_refs,
    'ElectraRawLocationsVsManifest':len(electra_locations)==electra_manifest['stats']['sourceLocationCount'],
    'ElectroverseRawLocationsVsManifest':len(ev_cache_location_ids)==ev_manifest['totalStations'],
  }
}
print('TCC_STATION_OVERLAP_RESULT='+json.dumps(result,ensure_ascii=False,separators=(',',':')))
out=ROOT/'reports'/'station-overlap-irve-electra-electroverse-20261009.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
