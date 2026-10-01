#!/usr/bin/env python3
"""Compare completed Mac countries against one pinned GitHub SuC snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from core import compare, now, read, render_html, write


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        # Credential-bearing remotes/errors must not be copied to reports/logs.
        raise RuntimeError('Git operation failed. Use the authenticated updater checkout on the Mac.')
    return result.stdout


def get_github_snapshot(repo):
    """Read an immutable commit without checkout/reset, FETCH_HEAD or working-file edits."""
    refs = git(repo, 'ls-remote', 'origin', 'refs/heads/main').split()
    if len(refs) != 2 or len(refs[0]) != 40 or any(c not in '0123456789abcdef' for c in refs[0]):
        raise RuntimeError('Cannot resolve GitHub main')
    sha = refs[0]
    git(repo, 'fetch', '--no-write-fetch-head', 'origin', sha)
    files = {}
    for filename in ('tesla_stations.json', 'europe.json', 'metadata.json'):
        files[filename] = json.loads(git(repo, 'show', sha + ':data/suc-tracker/' + filename))
    return sha, files


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def resolve_codes(cfg, countries=None, report_paths=None):
    """Never infer updated countries from the full Mac catalogue or price-change counts."""
    selected = set(countries or [])
    for path in report_paths or []:
        report = read(path)
        if report.get('status') != 'ready':
            raise ValueError('Mac export report is not ready: ' + str(path))
        if report.get('perCountry'):
            for item in report['perCountry']:
                if item.get('status') != 'ready':
                    raise ValueError('Incomplete country in global Mac export')
                selected.add(item.get('countryCode') or item.get('country'))
        else:
            selected.add(report.get('countryCode') or report.get('country'))
    mapping = {k: v['countryCode'] for k, v in cfg.items()}
    codes = set(mapping.values())
    result = set()
    for value in selected:
        if value in mapping:
            result.add(mapping[value])
        elif isinstance(value, str) and value.upper() in codes:
            result.add(value.upper())
        else:
            raise ValueError('Unrecognized country in completed Mac scope: ' + repr(value))
    if not result:
        raise ValueError('Specify --countries or a validated --mac-report; full-catalogue inference is disabled')
    return result


def completed_lot(summary_path, cfg):
    summary_path = Path(summary_path)
    summary = read(summary_path)
    selected, rows, skipped = set(), [], []
    for item in summary.get('countries', []):
        country = item.get('country')
        if country not in cfg:
            raise ValueError('Invalid lot country')
        if item.get('status') not in ('published', 'validated_not_published'):
            skipped.append(country)
            continue
        code = cfg[country]['countryCode']
        folder = summary_path.parent / country
        ready_codes = resolve_codes(cfg, report_paths=[folder / 'export-report.json'])
        if ready_codes != {code} or code in selected:
            raise ValueError('Country/export-report mismatch or duplicate')
        country_rows = [s for s in read(folder / 'publish-candidate.json') if s.get('countryCode') == code]
        if not country_rows:
            raise ValueError('Empty completed country: ' + country)
        rows.extend(country_rows)
        selected.add(code)
    if not selected:
        raise ValueError('No completed Mac country; no comparison generated')
    return selected, rows, skipped


def compare_files(mac_path, snapshot, out, codes, label, sha):
    catalogue, source, meta = (snapshot[k] for k in ('tesla_stations.json', 'europe.json', 'metadata.json'))
    if digest(catalogue) != meta.get('catalogueSha256') or digest(source) != meta.get('sourceSha256'):
        raise ValueError('GitHub snapshot integrity mismatch')
    if set(codes) - set(meta['countries']):
        raise ValueError('Requested country not covered by GitHub SuC catalogue')
    mac_path, out = Path(mac_path).resolve(), Path(out).resolve()
    if out == mac_path.parent and mac_path.name in ('tesla_stations_suc_tracker.json', 'tesla_stations_mac.json'):
        raise ValueError('Comparison output must not overwrite its Mac input')
    _, report = compare(read(mac_path), source, label, codes, normalized=catalogue)
    report['githubCommit'] = sha
    report['githubCataloguePath'] = 'data/suc-tracker/tesla_stations.json'
    report['githubCheckedAt'] = meta['checkedAt']
    report['inputSha256'] = {'mac': hashlib.sha256(mac_path.read_bytes()).hexdigest(), 'githubCatalogue': meta['catalogueSha256']}
    out.mkdir(parents=True, exist_ok=True)
    write(out / 'comparaison_mac_suc.json', report)
    (out / 'comparaison_mac_suc.html').write_text(render_html(report), encoding='utf-8')
    write(out / 'github-snapshot.json', {'commit': sha, 'retrievedAt': now(), 'metadata': meta, 'comparedCountries': sorted(codes)})
    # Keep the exact country slice from GitHub for offline inspection/import.
    write(out / 'tesla_stations_suc_tracker.json', [s for s in catalogue if s['countryCode'] in codes])
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', default=str(Path(__file__).resolve().parents[2]), help='Authenticated updater checkout')
    inputs = p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--mac-json')
    inputs.add_argument('--lot-summary', help='Lot summary: only completed country candidates are compared')
    p.add_argument('--countries', help='Only countries updated by this Mac pass, e.g. france or BE,NL,LU')
    p.add_argument('--mac-report', action='append', help='Validated country/global export report; repeatable')
    p.add_argument('--out', default='runtime/suc-comparison')
    args = p.parse_args()
    cfg = read(Path(args.repo) / 'config/countries.json')
    skipped = []
    if args.lot_summary:
        if args.countries or args.mac_report:
            p.error('Lot scope is taken only from completed countries in its summary')
        codes, rows, skipped = completed_lot(args.lot_summary, cfg)
        mac_path = Path(args.out).resolve() / 'mac-completed-countries.json'
        write(mac_path, rows)
    else:
        codes = resolve_codes(cfg, args.countries.split(',') if args.countries else None, args.mac_report)
        mac_path = args.mac_json
    sha, snapshot = get_github_snapshot(args.repo)
    report = compare_files(mac_path, snapshot, args.out, codes, 'Export Mac des pays terminés : ' + ', '.join(sorted(codes)) + (' ; pays incomplets exclus : ' + ', '.join(skipped) if skipped else ''), sha)
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    print('Rapport : ' + str(Path(args.out).resolve() / 'comparaison_mac_suc.html'))


if __name__ == '__main__':
    main()
