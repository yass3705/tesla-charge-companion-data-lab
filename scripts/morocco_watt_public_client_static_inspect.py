#!/usr/bin/env python3
"""Static, GET-only inspection of WATT.ma public HTML/JS for data-source routes.

The script fetches only same-origin public pages/assets referenced by the map HTML.
It never logs in, sends cookies, follows command/session routes, or invokes discovered
API candidates. Output is a sanitized list of literal route/asset candidates only.
"""
from __future__ import annotations

import html.parser
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ORIGIN = 'https://map.watt.ma'
PAGES = ['/', '/docs/']
OUT = Path('artifacts/morocco-watt-public-client-static/summary.json')
UA = 'TeslaChargeCompanion-PublicStaticInspector/1.0'
MAX_ASSETS = 40
MAX_BYTES = 2_000_000

ROUTE_PATTERNS = [
    re.compile(r'''["'](\/api\/[A-Za-z0-9_?&=./{}:-]+)["']'''),
    re.compile(r'''["'](\/[A-Za-z0-9_.-]*(?:station|location|tariff|charger|ocpi)[A-Za-z0-9_?&=./{}:-]*)["']''', re.I),
    re.compile(r'''fetch\(\s*["']([^"']+)["']'''),
]


class AssetParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        value = None
        if tag == 'script':
            value = attrs.get('src')
        elif tag == 'link' and attrs.get('rel') in {'stylesheet', 'preload', 'modulepreload'}:
            value = attrs.get('href')
        if value:
            self.assets.append(value)


def get_text(url: str):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/javascript,text/javascript,*/*;q=0.5'})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raw = raw[:MAX_BYTES]
            truncated = True
        else:
            truncated = False
        return {
            'url': url,
            'status': r.status,
            'content_type': r.headers.get('content-type', ''),
            'bytes_scanned': len(raw),
            'truncated': truncated,
            'text': raw.decode('utf-8', errors='replace'),
        }


def same_origin_url(base_url: str, value: str):
    full = urllib.parse.urljoin(base_url, value)
    parsed = urllib.parse.urlparse(full)
    if parsed.scheme != 'https' or parsed.netloc != 'map.watt.ma':
        return None
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', parsed.query, ''))


def route_candidates(text: str):
    out = set()
    for pattern in ROUTE_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1).strip()
            if value.startswith(('http://', 'https://')):
                parsed = urllib.parse.urlparse(value)
                if parsed.netloc != 'map.watt.ma':
                    continue
                value = parsed.path + (('?' + parsed.query) if parsed.query else '')
            if not value.startswith('/'):
                continue
            lowered = value.lower()
            if any(x in lowered for x in ('start_session', 'stop_session', '/commands/', '/auth', '/login', '/account')):
                continue
            out.add(value)
    return sorted(out)


def main():
    pages = []
    assets = set()
    all_candidates = set()

    for path in PAGES:
        doc = get_text(ORIGIN + path)
        parser = AssetParser()
        parser.feed(doc['text'])
        page_assets = []
        for value in parser.assets:
            full = same_origin_url(doc['url'], value)
            if full:
                assets.add(full)
                page_assets.append(full)
        candidates = route_candidates(doc['text'])
        all_candidates.update(candidates)
        pages.append({
            'url': doc['url'],
            'status': doc['status'],
            'content_type': doc['content_type'],
            'bytes_scanned': doc['bytes_scanned'],
            'truncated': doc['truncated'],
            'same_origin_asset_count': len(page_assets),
            'literal_route_candidates': candidates,
        })

    asset_reports = []
    for url in sorted(assets)[:MAX_ASSETS]:
        try:
            doc = get_text(url)
            candidates = route_candidates(doc['text'])
            all_candidates.update(candidates)
            asset_reports.append({
                'url': url,
                'status': doc['status'],
                'content_type': doc['content_type'],
                'bytes_scanned': doc['bytes_scanned'],
                'truncated': doc['truncated'],
                'literal_route_candidates': candidates,
            })
        except Exception as exc:
            asset_reports.append({'url': url, 'error_type': type(exc).__name__})

    # Categorize only; do not invoke any discovered candidate here.
    likely_data = [x for x in sorted(all_candidates) if any(k in x.lower() for k in ('station', 'location', 'tariff', 'charger', 'ocpi', 'status'))]
    out = {
        'schema_version': 1,
        'origin': ORIGIN,
        'policy': {
            'read_only': True,
            'http_methods': ['GET'],
            'same_origin_only': True,
            'credentials_used': False,
            'cookies_used': False,
            'discovered_routes_invoked': False,
            'command_or_session_routes_invoked': False,
            'raw_html_or_js_committed': False,
        },
        'pages': pages,
        'assets_inspected': asset_reports,
        'all_literal_readonly_candidate_paths': sorted(all_candidates),
        'likely_data_candidate_paths': likely_data,
        'next_step': 'Review candidates and invoke only clearly public GET data routes in a separate isolated probe.',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'pages': len(pages),
        'assets': len(asset_reports),
        'candidate_paths': len(all_candidates),
        'likely_data_candidates': likely_data,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
