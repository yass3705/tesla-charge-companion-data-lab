#!/usr/bin/env python3
"""Validate a downloaded bounded renewal and extend the immutable last-good bundle."""
import argparse,gzip,hashlib,json
from pathlib import Path
from v9_rebuild.orchestrator import artifact_digest,safe_relative,sha256
from v9_rebuild.canonical import normalize_ionity,validate
from v9_rebuild.snapshot import prepare,verify
from v9_rebuild.fx import validate_output as validate_fx
from v9_rebuild.morocco_inventory import validate_output as validate_morocco
from v9_rebuild.ionity import validate_output as validate_ionity

def verify_downloads(download,receipt,expected_head):
 run=json.loads(receipt.read_bytes())
 if run.get('head_branch')!='rebuild/v9-20261020' or run.get('head_sha')!=expected_head or run.get('conclusion')!='success' or run.get('status')!='completed' or run.get('name')!='V9 bounded renewal pilot':raise ValueError('Untrusted renewal execution')
 states={};proof=[]
 for folder in sorted(download.iterdir()):
  if folder.is_symlink() or any(p.is_symlink() for p in folder.rglob('*')):raise ValueError('Symlink in downloaded artifact')
  manifest=json.loads((folder/'manifest.json').read_bytes())
  if manifest.get('status')!='complete' or manifest.get('schema_version')!=1:raise ValueError('Partial manifest')
  for row in manifest['sources']:
   if row['status']!='ok' or row['source'] in states:raise ValueError('Failed/duplicate source')
   rel=safe_relative(row['artifact']);state=folder/Path(*rel.parts[:3])
   if rel.parts[:2]!=('objects',row['source'].replace(':','_')) or sha256(folder/rel)!=row['sha256']:raise ValueError('Source artifact mismatch')
   digest,files=artifact_digest(state)
   if digest!=row['artifact_set_sha256'] or rel.parts[2]!=digest or files!=row['files']:raise ValueError('Artifact set corruption')
   states[row['source']]=state;proof.append({'source':row['source'],'artifactSetSha256':digest,'files':files})
 if set(states)!={'FR:ionity_direct_family','GL:fx','MA:kilowatt_inventory'}:raise ValueError('Pilot source set differs')
 validate_ionity(states['FR:ionity_direct_family']);validate_fx(states['GL:fx']);validate_morocco(states['MA:kilowatt_inventory'],'kilowatt')
 return run,states,proof

def build(download,receipt,expected_head,previous,out):
 if out.exists() or Path(__file__).resolve().parents[1] in out.resolve().parents:raise ValueError('New isolated output required')
 run,states,proof=verify_downloads(download,receipt,expected_head)
 old=verify(previous);inputs={r['source']:previous/r['path'] for r in old['sources']}
 out.mkdir(parents=True);canonical=out/'canonical';canonical.mkdir()
 for file in (states['FR:ionity_direct_family']/'data/national').glob('ionity_direct_stations_*.json.gz'):
  raw=file.read_bytes();data=normalize_ionity(json.loads(gzip.decompress(raw)),artifact_sha256=hashlib.sha256(raw).hexdigest());validate(data)
  name=data['source']['id'];target=canonical/(name.replace(':','__')+'.json');target.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n');inputs[name]=target
 bundle=prepare(inputs,out/'bundles')
 report={'status':'renewal_import_prepared','run':run,'bundleId':bundle.name,'sources':proof,'fxPath':str(states['GL:fx']/'data/fx/exchange_rates.json'),'kilowatt':'Transport and technical validation only; canonical UI integration not claimed'}
 (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for x in ['download','receipt','previous','out']:p.add_argument('--'+x,type=Path,required=True)
 p.add_argument('--expected-head',required=True);a=p.parse_args();print(json.dumps(build(a.download,a.receipt,a.expected_head,a.previous,a.out)))
