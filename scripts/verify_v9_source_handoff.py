#!/usr/bin/env python3
"""Read-only verification of one successful, isolated GitHub collector job.

A different matrix job may fail. Its artifacts are never accepted here and the
whole run's actual conclusion is retained. No collection or settings mutation.
"""
import argparse, hashlib, json, stat, subprocess, sys, tempfile, zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v9_rebuild.orchestrator import artifact_digest, safe_relative, sha256
from v9_rebuild.belib import validate_output as belib
from v9_rebuild.driveco_evse import validate_output as driveco
from v9_rebuild.electra_france import validate_output as electra
from v9_rebuild.swiss_bundle import validate_output as swiss_bundle
from v9_rebuild.swiss_integration import validate_output as swiss_integration
from v9_rebuild.nl_dotnl import validate_output as nl_dotnl
from v9_rebuild.atlante_fr_it import validate_output as atlante_fr_it
REPO='yass3705/tesla-charge-companion-data-lab'
VALIDATORS={'FR:atlante_fr_it':atlante_fr_it,'NL:dotnl':nl_dotnl,'FR:belib':belib,'FR:driveco_evse':driveco,'FR:electra_platform':electra,'CH:swiss_bundle':swiss_bundle,'CH:swiss_integration':swiss_integration}
def check_execution(run,jobs,artifact,source,head):
    if (run.get('status')!='completed' or run.get('head_branch')!='rebuild/v9-20261020'
        or run.get('head_sha')!=head or len(head)!=40
        or run.get('repository',{}).get('full_name')!=REPO
        or run.get('path')!='.github/workflows/v9-tariff-restoration-pilot.yml'):
        raise ValueError('Untrusted run provenance or incomplete run')
    matches=[j for j in jobs if j.get('name')==f'collect ({source})']
    if len(matches)!=1 or matches[0].get('status')!='completed' or matches[0].get('conclusion')!='success':
        raise ValueError('Source job did not succeed')
    parent=artifact.get('workflow_run',{})
    if (artifact.get('expired') is not False or parent.get('id')!=run['id']
        or parent.get('head_sha')!=head or parent.get('head_branch')!='rebuild/v9-20261020'
        or not str(artifact.get('digest','')).startswith('sha256:')):
        raise ValueError('Artifact not bound to expected run')
    return matches[0]
def verify_files(folder,source):
    m=json.loads((folder/'manifest.json').read_bytes())
    if m.get('schema_version')!=1 or m.get('status')!='complete' or len(m.get('sources',[]))!=1:raise ValueError('Incomplete source manifest')
    r=m['sources'][0]
    if r.get('status')!='ok' or r.get('source')!=source:raise ValueError('Source identity mismatch')
    rel=safe_relative(r['artifact'])
    if rel.parts[:2]!=('objects',source.replace(':','_')) or sha256(folder/rel)!=r['sha256']:raise ValueError('Source artifact mismatch')
    state=folder/Path(*rel.parts[:3]);digest,files=artifact_digest(state)
    if digest!=r['artifact_set_sha256'] or digest!=rel.parts[2] or files!=r['files']:raise ValueError('Artifact set corruption')
    VALIDATORS[source](state)
    return state,digest,files

def verify(run_id,source,artifact_name,head,out,*,reuse_archive=False):
    root=Path(__file__).resolve().parents[1]
    if (out.exists() and not reuse_archive) or root==out.resolve() or root in out.resolve().parents:raise ValueError('New isolated output required')
    if reuse_archive and (not (out/'artifact.zip').is_file() or (out/'receipt.json').exists()):raise ValueError('Only a previously downloaded unverified ZIP can be reused')
    def api(p):return json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/{p}']))
    if api('actions/permissions')['enabled'] is not False:raise ValueError('Close controlled activation before recording handoff')
    run=api(f'actions/runs/{run_id}');jobs=api(f'actions/runs/{run_id}/jobs?per_page=100')['jobs']
    artifacts=api(f'actions/runs/{run_id}/artifacts?per_page=100')['artifacts']
    selected=[a for a in artifacts if a['name']==artifact_name]
    if len(selected)!=1:raise ValueError('Unique expected artifact missing')
    artifact=selected[0];job=check_execution(run,jobs,artifact,source,head)
    raw=(out/'artifact.zip').read_bytes() if reuse_archive else subprocess.check_output(['gh','api',f'repos/{REPO}/actions/artifacts/{artifact["id"]}/zip'])
    digest=hashlib.sha256(raw).hexdigest()
    if artifact['digest']!='sha256:'+digest or artifact['size_in_bytes']!=len(raw):raise ValueError('Downloaded ZIP integrity mismatch')
    archive=out/'artifact.zip'
    if reuse_archive:
        folder=Path(tempfile.mkdtemp(prefix='extracted-recheck-',dir=out))
    else:
        out.mkdir(parents=True);archive=out/'artifact.zip';archive.write_bytes(raw);folder=out/'extracted';folder.mkdir()
    with zipfile.ZipFile(archive) as z:
        names=set()
        for entry in z.infolist():
            safe_relative(entry.filename)
            if entry.filename in names or stat.S_ISLNK(entry.external_attr>>16):raise ValueError('Unsafe ZIP entry')
            names.add(entry.filename)
        z.extractall(folder)
    state,object_sha,files=verify_files(folder,source)
    report={'runId':run_id,'runConclusion':run['conclusion'],'runHeadSha':head,'runBranch':run['head_branch'],
        'sourceId':source,'jobId':job['id'],'jobStatus':job['status'],'jobConclusion':job['conclusion'],
        'actionsEnabledAfter':False,'artifactId':artifact['id'],'artifactZipSha256':digest,
        'artifactSetSha256':object_sha,'technicalValidation':'PASS','files':files,
        'scope':'One successful source job and downloaded immutable artifact; downstream import separately verified'}
    for name,value in [('run.json',run),('job.json',job),('artifact.json',artifact),('receipt.json',report)]:
        (out/name).write_text(json.dumps(value,indent=2)+'\n')
    (out/'state-path.txt').write_text(str(state.resolve())+'\n')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);p.add_argument('--source',choices=VALIDATORS,required=True);p.add_argument('--artifact-name',required=True);p.add_argument('--expected-head',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reuse-archive',action='store_true');a=p.parse_args()
    print(json.dumps(verify(a.run,a.source,a.artifact_name,a.expected_head,a.out,reuse_archive=a.reuse_archive)))
