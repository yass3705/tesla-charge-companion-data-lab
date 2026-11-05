"""Isolate generated offer-ID collisions without changing acquisition or prices.

The original manifest and affected tiles are retained byte-for-byte. All rows
sharing a generated ID are withheld; none is arbitrarily chosen as the price.
"""
import collections
import gzip
import hashlib
import json
from pathlib import Path


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def isolate(folder: Path):
    manifest_path = folder / 'manifest.json'
    original = manifest_path.read_bytes()
    manifest = json.loads(original)
    if manifest.get('quarantine'):
        verify(folder, manifest)
        return
    rows, counts = {}, collections.Counter()
    for tile in manifest['tiles']:
        if Path(tile['file']).name != tile['file']:
            raise ValueError('Unsafe Electra tile')
        raw = (folder / tile['file']).read_bytes()
        if digest(raw) != tile['sha256'] or len(raw) != tile['bytes']:
            raise ValueError('Electra tile integrity before quarantine')
        payload = json.loads(gzip.decompress(raw))
        if len(payload['emspOffers']) != tile['count']:
            raise ValueError('Electra count before quarantine')
        rows[tile['file']] = (raw, payload)
        counts.update(o['id'] for o in payload['emspOffers'])
    collisions = {key for key, n in counts.items() if n > 1}
    if not collisions:
        return
    archive = folder / 'unvalidated-original'
    archive.mkdir(exist_ok=False)
    (archive / 'manifest.json').write_bytes(original)
    held, kept = [], []
    for tile in manifest['tiles']:
        raw, payload = rows[tile['file']]
        rejected = [{'tile': tile['file'], 'index': i, 'offer': o}
                    for i, o in enumerate(payload['emspOffers']) if o['id'] in collisions]
        kept.extend(o for o in payload['emspOffers'] if o['id'] not in collisions)
        if not rejected:
            continue
        held.extend(rejected)
        (archive / tile['file']).write_bytes(raw)
        payload['emspOffers'] = [o for o in payload['emspOffers'] if o['id'] not in collisions]
        raw = gzip.compress(encode(payload), mtime=0)
        (folder / tile['file']).write_bytes(raw)
        tile.update(count=len(payload['emspOffers']), bytes=len(raw), sha256=digest(raw))
    report = {'schemaVersion': 1, 'reason': 'duplicate_generated_offer_identity',
              'originalManifestSha256': digest(original), 'offerIds': sorted(collisions),
              'withheldRows': held, 'originalOfferCount': sum(counts.values()),
              'retainedOfferCount': len(kept)}
    raw = gzip.compress(encode(report), mtime=0)
    (folder / 'quarantined-offers.json.gz').write_bytes(raw)
    manifest['quarantine'] = {'file': 'quarantined-offers.json.gz', 'sha256': digest(raw),
                              'withheldRows': len(held), 'duplicateIdentities': len(collisions),
                              'originalManifestSha256': digest(original)}
    manifest['preQuarantineStats'] = dict(manifest['stats'])
    manifest['preQuarantineCpoSummary'] = manifest.pop('cpoSummary', {})
    manifest['stats']['publishedOffers'] = len(kept)
    manifest['stats']['publishedLocations'] = len({o['metadata']['electraLocationId'] for o in kept})
    manifest['stats']['publishedEvseIds'] = len({(o['metadata']['electraLocationId'], o['evseIds'][0]) for o in kept})
    manifest_path.write_bytes(encode(manifest) + b'\n')
    verify(folder, manifest)


def verify(folder, manifest):
    info = manifest.get('quarantine')
    if not info:
        return
    if info.get('file') != 'quarantined-offers.json.gz':
        raise ValueError('Invalid Electra quarantine path')
    raw = (folder / info['file']).read_bytes()
    original_raw = (folder / 'unvalidated-original/manifest.json').read_bytes()
    if digest(raw) != info['sha256'] or digest(original_raw) != info['originalManifestSha256']:
        raise ValueError('Electra quarantine integrity mismatch')
    report, original = json.loads(gzip.decompress(raw)), json.loads(original_raw)
    held, counts, retained = [], collections.Counter(), 0
    current = {t['file']: t for t in manifest['tiles']}
    if set(current) != {t['file'] for t in original['tiles']}:
        raise ValueError('Electra quarantine removed tile')
    originals = {}
    for tile in original['tiles']:
        name = tile['file']
        if Path(name).name != name:
            raise ValueError('Unsafe Electra original tile')
        path = folder / 'unvalidated-original' / name
        raw = (path if path.exists() else folder / name).read_bytes()
        if digest(raw) != tile['sha256'] or len(raw) != tile['bytes']:
            raise ValueError('Electra original tile integrity mismatch')
        payload = json.loads(gzip.decompress(raw)); originals[name] = payload
        counts.update(o['id'] for o in payload['emspOffers'])
    collisions = {key for key, n in counts.items() if n > 1}
    for name, payload in originals.items():
        expected = {**payload, 'emspOffers': [o for o in payload['emspOffers'] if o['id'] not in collisions]}
        held.extend({'tile': name, 'index': i, 'offer': o} for i, o in enumerate(payload['emspOffers']) if o['id'] in collisions)
        observed = json.loads(gzip.decompress((folder / name).read_bytes()))
        if observed != expected:
            raise ValueError('Electra quarantine altered non-conflicting offer')
        retained += len(expected['emspOffers'])
    if (report.get('reason') != 'duplicate_generated_offer_identity' or report['withheldRows'] != held
            or report['offerIds'] != sorted(collisions) or report['retainedOfferCount'] != retained
            or report['originalOfferCount'] != sum(counts.values())
            or info['withheldRows'] != len(held) or info['duplicateIdentities'] != len(collisions)
            or manifest['stats']['publishedOffers'] != retained
            or manifest['sourceArchive'] != original['sourceArchive']
            or report['originalManifestSha256'] != digest(original_raw)):
        raise ValueError('Electra quarantine ledger mismatch')
