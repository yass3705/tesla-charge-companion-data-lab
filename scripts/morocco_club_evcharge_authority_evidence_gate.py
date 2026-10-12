#!/usr/bin/env python3
"""Derive the next Club EV-Charge request gate from already-published evidence only.

No network requests are performed. This intentionally refuses to compose a target URL
from non-adjacent markers or to request the remaining API-shaped path.
"""
import json
from pathlib import Path

SRC=Path('reports/morocco/totalenergies/club-ev-charge-runtime-entrypoint-2026-09-01.json')
OUT=Path('artifacts/morocco-club-evcharge-authority-evidence')
OUT.mkdir(parents=True,exist_ok=True)

d=json.loads(SRC.read_text())
f=d.get('safe_findings',{})
rel=f.get('getstationstate_marker_relations',{})
near=rel.get('marker_within_1024_chars',{})
abs_urls=f.get('safe_numocity_absolute_urls',[])
base_literals=f.get('safe_numocity_base_literals',[])
paths=f.get('safe_read_only_api_path_candidates',[])

# An exact anonymous GET may only be promoted when public evidence binds authority,
# base path and read-only route without guessed composition.
authority_proven=bool(abs_urls or base_literals)
route_locally_bound=bool(rel.get('unique_occurrence') and near.get('/api/') and near.get('/chargestation/'))
version_locally_bound=bool(near.get('/2'))
exact_target_proven=False

report={
 'schema_version':1,
 'subject':'Club EV-Charge authority/base-path evidence gate',
 'source_record':str(SRC),
 'policy':{
   'offline_evidence_only':True,
   'network_request_count':0,
   'no_path_enumeration':True,
   'no_guessed_prefix_composition':True,
   'no_discovered_route_request':True,
   'no_station_or_connector_ids':True,
   'fail_closed':True,
 },
 'evidence':{
   'numocity_absolute_urls':abs_urls,
   'numocity_base_literals':base_literals,
   'safe_read_only_api_path_candidates':paths,
   'getstationstate_route_locally_bound':route_locally_bound,
   'version_2_locally_bound':version_locally_bound,
   'authority_proven':authority_proven,
   'exact_anonymous_get_target_proven':exact_target_proven,
 },
 'decision':'blocked_no_exact_target',
 'production_decision':'no_promotion',
 'next_step':'Acquire new explicit public client evidence that binds an authority/base path to one exact anonymous read-only route. Do not request /poc/api/charge-location/info or compose getstationstate with a guessed host/version before that gate exists.'
}

assert d.get('production_decision')=='no_promotion'
assert f.get('safe_numocity_absolute_url_count')==0
assert f.get('safe_numocity_base_literal_count')==0
assert route_locally_bound is True
assert version_locally_bound is False
assert authority_proven is False
assert exact_target_proven is False
(OUT/'summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'ok':True,'decision':report['decision'],'network_request_count':0}))
