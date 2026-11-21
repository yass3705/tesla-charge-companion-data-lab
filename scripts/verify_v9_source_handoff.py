#!/usr/bin/env python3
"""Read-only verification of one successful, isolated GitHub collector job.

A different matrix job may fail. Its artifacts are never accepted here and the
whole run's actual conclusion is retained. No collection or settings mutation.
"""
import argparse, hashlib, json, stat, subprocess, sys, tempfile, zipfile
from functools import partial
from pathlib import Path
from datetime import datetime, timedelta
import re
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v9_rebuild.orchestrator import artifact_digest, safe_relative, sha256
from v9_rebuild.bump_official import validate_output as bump_official
from v9_rebuild.allego_official import validate_output as allego_official
from v9_rebuild.soregies_official import validate_output as soregies_official
from v9_rebuild.evadea_official import validate_output as evadea_official
from v9_rebuild.powerdot_official import validate_output as powerdot_official
from v9_rebuild.shell_official import validate_output as shell_official
from v9_rebuild.totalenergies_official import validate_output as totalenergies_official
from v9_rebuild.mobisdec_official import validate_output as mobisdec_official
from v9_rebuild.izivia_official import validate_output as izivia_official
from v9_rebuild.belib import validate_output as belib
from v9_rebuild.driveco_evse import validate_output as driveco
from v9_rebuild.electra_france import validate_output as electra
from v9_rebuild.swiss_bundle import validate_output as swiss_bundle
from v9_rebuild.swiss_integration import validate_output as swiss_integration
from v9_rebuild.nl_dotnl import validate_output as nl_dotnl
from v9_rebuild.atlante_fr_it import validate_output as atlante_fr_it
from v9_rebuild.uk_midhope import validate_output as uk_midhope
from v9_rebuild.belgium_gap_archive import validate_output as belgium_gap_archive
from v9_rebuild.france_canonical import validate_output as france_canonical
from v9_rebuild.france_irve import validate_output as france_irve
from v9_rebuild.orchestrator import validate_belgium_output
from v9_rebuild.allego_stations import validate_output as allego_stations
from v9_rebuild.bump_tariffs import validate_output as bump_tariffs
from v9_rebuild.uk_pcpr import validate_output as uk_pcpr
from v9_rebuild.uk_blink import validate_output as uk_blink
from v9_rebuild.uk_gridserve import validate_output as uk_gridserve
from v9_rebuild.zephyre import validate_output as zephyre
from v9_rebuild.zewatt import validate_output as zewatt
from v9_rebuild.fastned import validate_output as fastned
from v9_rebuild.energyvision import validate_output as energyvision
from v9_rebuild.uk_evyve import validate_output as uk_evyve
from v9_rebuild.ozecar import validate_output as ozecar
from v9_rebuild.izivia_fast import validate_output as izivia_fast
from v9_rebuild.cwd_script import validate_output as cwd_output
from v9_rebuild.official_rules import RULES, validate_output as official_rules
from v9_rebuild.tesla_mac import validate_output as tesla_mac
from v9_rebuild.morocco_evgo import validate_output as morocco_evgo
from v9_rebuild.spain_fixed_core import validate_output as spain_fixed_core
from v9_rebuild.spain_fixed_secondary import validate_output as spain_fixed_secondary
from v9_rebuild.ionity import validate_output as ionity
from v9_rebuild.electroverse import validate_state as electroverse
from v9_rebuild import electra_residual_audit, france_treated_audit, france_fixed_core, france_fixed_secondary, greenspot, morocco_inventory
ARCHIVED_REPLAYS = {'FR:electra_residual_audit', 'FR:treated_reliability','CH:ail_emoti', 'CH:ebs_ecarup', 'CH:iwb_basel', 'FR:canonical', 'GB:midhope_verified', 'BE:final_gap_archive'}
REPO='yass3705/tesla-charge-companion-data-lab'
def verify_full_tariff_renewal(state, started_at, completed_at):
    """Every currently mapped location must have been checked in this run.

    Old unmapped cache rows remain retained, not counted as renewed. This is
    execution completeness, not equality with any historical station volume.
    """
    parse = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))
    start, end = parse(started_at), parse(completed_at) + timedelta(seconds=120)
    mapping = json.loads((state/'data/electroverse/irve_location_mapping.json').read_bytes())
    checked = json.loads((state/'data/electroverse/tariff_cache/checked-at.json').read_bytes()).get('checkedAt')
    if not isinstance(checked, dict):raise ValueError('Electroverse checked-at ledger missing')
    ids = [str(row['electroverseLocationPk']) for row in mapping['mappings']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate mapped location')
    for pk in ids:
        if pk not in checked or not start <= parse(checked[pk]) <= end:
            raise ValueError('Mapped location was not renewed in the source job')
    return {'mappedLocationsCheckedThisJob':len(ids),'checkedLedgerEntries':len(checked),
            'allMappedLocationsRenewed':True,'historicalVolumeGate':False}
def verified_window_chain(head):
    """Follow only immutable checkpoint receipts pinned by the actual collector workflow."""
    evidence = Path(__file__).resolve().parents[1] / "docs/v9-rebuild/evidence/restoration-20261121"
    receipts = []
    visited = set()
    while True:
        if not re.fullmatch(r"[0-9a-f]{40}", head) or head in visited:
            raise ValueError("Invalid Electroverse checkpoint ancestry")
        visited.add(head)
        workflow = subprocess.check_output(["git", "show",
            f"{head}:.github/workflows/v9-tariff-restoration-pilot.yml"], cwd=evidence, text=True)
        if "--incoming" not in workflow:
            break
        pins = re.findall(r"--expected-sha ([a-f0-9]{64}) --expected-head ([a-f0-9]{40}) --expected-run (\d+)", workflow)
        if len(pins) != 1:
            raise ValueError("Unrecognized checkpoint recovery contract")
        sha, parent, run = pins[0]
        file = evidence / f"electroverse-checkpoint-{run}.json"
        if run == "43599593600":
            file = evidence / "electroverse-checkpoint.json"
        receipt = json.loads(file.read_bytes())
        if (str(receipt["runId"]) != run or receipt["head"] != parent or receipt["fileSetSHA256"] != sha
                or receipt["complete"] is not False or receipt["source"] != "FR:electroverse_full"
                or f'/artifacts/{receipt["artifactId"]}/zip' not in workflow
                or receipt["zipSHA256"] + "  retained.zip" not in workflow):
            raise ValueError("Checkpoint lineage and recovery workflow disagree")
        if "renewalWindow" in receipt:
            receipts.append(receipt)
        elif run != "43599593600":
            raise ValueError("Ancestor lacks verified tariff row fingerprints")
        head = parent
    return receipts


def verify_tariff_generation(state, started_at, completed_at, receipts):
    from v9_rebuild.electroverse import MAPPING, read_json
    from v9_rebuild.electroverse_renewal import job_window, timestamp

    renewed, current = job_window(state, started_at, completed_at)
    boundary = timestamp(started_at)
    for receipt in receipts:
        if timestamp(receipt["jobCompletedAt"]) > boundary:
            raise ValueError("Overlapping checkpoint jobs")
        ids, actual = job_window(state, receipt["jobStartedAt"], receipt["jobCompletedAt"])
        if actual != receipt["renewalWindow"] or renewed.intersection(ids):
            raise ValueError("Historical tariff renewal rows or mapping changed")
        renewed.update(ids)
        boundary = timestamp(receipt["jobStartedAt"])
    mapped = {str(row["electroverseLocationPk"]) for row in read_json(state / MAPPING)["mappings"]}
    if mapped != renewed:
        raise ValueError("Incomplete renewal generation")
    return {"mappedLocationsCheckedThisJob": current["locations"], "verifiedLocations": len(renewed),
            "ancestorRunIds": [r["runId"] for r in receipts], "allMappedLocationsRenewed": True,
            "historicalVolumeGate": False}


def belgium_nap(state):
    manifest = json.loads((state / 'data/belgium/nap-belgium-manifest.json').read_bytes())
    if not validate_belgium_output(state, manifest):
        raise ValueError('Belgium national pagination or integrity contract invalid')
    return manifest
VALIDATORS={'FR:irve_national':france_irve,'BE:nap':belgium_nap,'GB:midhope_verified':uk_midhope,'BE:final_gap_archive':belgium_gap_archive,'FR:canonical':france_canonical,'FR:atlante_fr_it':atlante_fr_it,'NL:dotnl':nl_dotnl,'FR:belib':belib,'FR:driveco_evse':driveco,'FR:electra_platform':electra,'CH:swiss_bundle':swiss_bundle,'CH:swiss_integration':swiss_integration}
VALIDATORS.update({
    "FR:bump_official": bump_official,
    "FR:allego_official": allego_official,
    "FR:soregies_mobilites_official": soregies_official,
    "FR:evadea_official": evadea_official,
    "FR:powerdot_official": powerdot_official,
    "FR:shell_recharge_official": shell_official,
    "FR:totalenergies_official": totalenergies_official,
    "FR:mobisdec_official": mobisdec_official,
    "FR:izivia_official": izivia_official,
})
VALIDATORS.update({f'FR:{name}_official':partial(official_rules,source=name) for name in RULES})
VALIDATORS.update({"GL:tesla_mac": tesla_mac, "MA:evgo": morocco_evgo, "ES:fixed_tariff_core": spain_fixed_core,
                   "ES:fixed_tariff_secondary": spain_fixed_secondary, "FR:ionity_direct_family": ionity})
VALIDATORS.update({"FR:electra_residual_audit": electra_residual_audit.validate_output,
                   "FR:treated_reliability": france_treated_audit.validate_output,
                   "FR:fixed_tariff_core": france_fixed_core.validate_output,
                   "FR:fixed_tariff_secondary": france_fixed_secondary.validate_output,
                   "FR:greenspot": greenspot.validate_output,
                   "MA:fastvolt_inventory": partial(morocco_inventory.validate_output, method="fastvolt")})
VALIDATORS.update({'FR:zephyre':zephyre,'FR:zewatt':zewatt})
VALIDATORS.update({'FR:fastned_inventory_family':fastned,'BE:energyvision':energyvision,'GB:evyve_pcpr':uk_evyve})
VALIDATORS.update({'FR:ozecar':ozecar,'FR:izivia_fast':izivia_fast})
VALIDATORS.update({'FR:electroverse_full':electroverse,'FR:electroverse_daily':electroverse})
VALIDATORS.update({'FR:allego_stations': allego_stations, 'FR:bump_tariffs': bump_tariffs})
VALIDATORS.update({'GB:blink_pcpr':uk_blink,'GB:gridserve_pcpr':uk_gridserve})
VALIDATORS.update({'GB:allego_uk_pcpr': partial(uk_pcpr, provider='allego_uk'),
                   'GB:source_ev_pcpr': partial(uk_pcpr, provider='source_ev')})
def manifest_evidence(folder, *, manifest_path):
    from v9_rebuild.operator_evidence import validate
    manifest = json.loads(manifest_path.read_bytes())
    return validate(folder / safe_relative(manifest["outputFile"]), manifest_path)

_registry_root = Path(__file__).resolve().parents[1]
for _spec in json.loads((_registry_root / 'v9_rebuild/sources.json').read_bytes())['sources']:
    if _spec['module'] == 'cwd_script':
        VALIDATORS[_spec['id']] = partial(cwd_output, method=_spec['method'])
    if _spec['module'] == 'operator_manifest':
        VALIDATORS[_spec['id']] = partial(manifest_evidence, manifest_path=_registry_root / safe_relative(_spec['manifest']))

def check_execution(run,jobs,artifact,source,head):
    scheduled = run.get('path') == '.github/workflows/v9-scheduled.yml'
    branch = 'main' if scheduled else 'rebuild/v9-20261020'
    direct_schedule = scheduled and source != "FR:ionity_direct_family"
    if scheduled:
        from scripts.check_v9_neutralized_main import reviewed_scheduled_source
        if not reviewed_scheduled_source(source, head, run.get("workflow_id"), run.get("event")):
            raise ValueError("Untrusted scheduled collection")
    if (run.get('status')!='completed' or run.get('head_branch')!=branch
        or run.get('head_sha')!=head or len(head)!=40
        or run.get('repository',{}).get('full_name')!=REPO
        or (not scheduled and run.get('path')!='.github/workflows/v9-tariff-restoration-pilot.yml')):
        raise ValueError('Untrusted run provenance or incomplete run')
    slug = source.replace(':', '_')
    job_name = f'collect ({source}, {slug})' if scheduled else f'collect ({source})'
    if direct_schedule:
        job_name = f'direct-evidence ({source}, {slug})'
    matches=[j for j in jobs if j.get('name') == job_name]
    if len(matches)!=1 or matches[0].get('status')!='completed' or matches[0].get('conclusion')!='success':
        raise ValueError('Source job did not succeed')
    parent=artifact.get('workflow_run',{})
    if (artifact.get('expired') is not False or parent.get('id')!=run['id']
        or parent.get('head_sha')!=head or parent.get('head_branch')!=branch
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
    enabled = api('actions/permissions')['enabled']
    active = []
    if enabled:
        pages = json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/actions/workflows?per_page=100','--paginate','--slurp']))
        active = [w['id'] for page in pages for w in page['workflows'] if w['state']=='active']
        if active != [425938005]:
            raise ValueError('Unexpected enabled workflow during permanent operation')
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
    renewal = verify_tariff_generation(state,job['started_at'],job['completed_at'],verified_window_chain(head)) if source=='FR:electroverse_full' else None
    report={'runId':run_id,'runConclusion':run['conclusion'],'runHeadSha':head,'runBranch':run['head_branch'],'workflowId':run.get('workflow_id'),'event':run.get('event'),
        'acquisitionKind':('archived_replay' if source in ARCHIVED_REPLAYS else 'mac_catalogue_import' if source=='GL:tesla_mac' else 'source_execution'),
        'sourceId':source,'jobId':job['id'],'jobStatus':job['status'],'jobConclusion':job['conclusion'],
        'jobStartedAt':job.get('started_at'),'jobCompletedAt':job.get('completed_at'),
        'artifactCreatedAt':artifact.get('created_at'),
        'actionsEnabledAfter':enabled,'activeWorkflowIdsAfter':active,'artifactId':artifact['id'],'artifactZipSha256':digest,
        'artifactSetSha256':object_sha,'technicalValidation':'PASS','files':files,
        'scope':'One successful source job and downloaded immutable artifact; downstream import separately verified'}
    if renewal is not None:report['renewalCompleteness']=renewal
    for name,value in [('run.json',run),('job.json',job),('artifact.json',artifact),('receipt.json',report)]:
        (out/name).write_text(json.dumps(value,indent=2)+'\n')
    (out/'state-path.txt').write_text(str(state.resolve())+'\n')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);p.add_argument('--source',choices=VALIDATORS,required=True);p.add_argument('--artifact-name',required=True);p.add_argument('--expected-head',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reuse-archive',action='store_true');a=p.parse_args()
    print(json.dumps(verify(a.run,a.source,a.artifact_name,a.expected_head,a.out,reuse_archive=a.reuse_archive)))
