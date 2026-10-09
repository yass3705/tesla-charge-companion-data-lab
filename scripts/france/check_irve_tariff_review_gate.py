#!/usr/bin/env python3
"""Gate a post-IRVE tariff coverage review on a *newly published* dynamic snapshot.

For the France IRVE upstream workflow and the daily safety-net only:
- require a fresh, valid dynamic source and positive en_service list;
- compare source fingerprint against latest successfully archived snapshot;
- skip old/reused IRVE data (e.g. PAN 503) rather than claim a new review.
Other explicit reviews (CPO/eMSP/new code/manual) remain eligible to run.
"""
import argparse,datetime as dt,gzip,json,pathlib,os,sys
def decide(dynamic,latest,trigger,upstream,now):
    if not isinstance(dynamic,dict):return 'skip','missing_or_invalid_dynamic'
    ids=dynamic.get('enServicePdcIds')
    states=dynamic.get('states') or {}
    if not isinstance(ids,list) or not ids or len(ids)!=int(states.get('en_service') or 0):
        return 'skip','invalid_positive_status_cardinality'
    sha=dynamic.get('sourceSha256')
    generated=dynamic.get('generatedAt')
    if not sha or not generated:return 'skip','missing_dynamic_fingerprint_or_timestamp'
    try:
        ts=dt.datetime.fromisoformat(generated.replace('Z','+00:00'))
        age=(now-ts.astimezone(dt.timezone.utc)).total_seconds()
        if age< -900 or age>72*3600:return 'skip','dynamic_too_old_or_future'
    except (TypeError,ValueError):return 'skip','invalid_dynamic_generatedAt'
    upstream_is_irve=(trigger=='workflow_run' and upstream=='France IRVE static refresh and residual audit')
    if trigger in ('schedule',) or upstream_is_irve:
        prior=(latest or {}).get('provenance',{}).get('irveDynamic',{})
        if prior.get('sourceSha256')==sha and prior.get('generatedAt')==generated:
            return 'skip','dynamic_already_reviewed'
    return 'run','new_dynamic_or_nonirve_source_verification'

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--dynamic',required=True)
 p.add_argument('--latest',required=True)
 p.add_argument('--trigger',default=os.environ.get('GITHUB_EVENT_NAME') or 'manual')
 p.add_argument('--upstream',default='')
 p.add_argument('--github-output',default=os.environ.get('GITHUB_OUTPUT'))
 args=p.parse_args()
 try:
  with gzip.open(args.dynamic,'rt',encoding='utf8') as f:dynamic=json.load(f)
 except (FileNotFoundError,OSError,json.JSONDecodeError):dynamic=None
 try:latest=json.loads(pathlib.Path(args.latest).read_text(encoding='utf8'))
 except (FileNotFoundError,OSError,json.JSONDecodeError):latest=None
 result,why=decide(dynamic,latest,args.trigger,args.upstream,dt.datetime.now(dt.timezone.utc))
 print('IRVE_COVERAGE_REVIEW_GATE='+json.dumps({'decision':result,'reason':why,'trigger':args.trigger,'upstream':args.upstream,
   'dynamicGeneratedAt':(dynamic or {}).get('generatedAt'),
   'dynamicSha':(dynamic or {}).get('sourceSha256')}))
 if args.github_output:
  with open(args.github_output,'a',encoding='utf8') as f:f.write('run='+('true' if result=='run' else 'false')+'\nreason='+why+'\n')
 if result=='skip':print('::notice title=IRVE review not re-run::'+why)

if __name__=='__main__':main()
