#!/usr/bin/env python3
"""Sanitized, read-only probe of the public Kilowatt Morocco web map.

Policy:
- public GET requests only
- no login/authentication
- no mutation/session/charging actions
- no raw HTML/JS or credentials persisted
- only schema/marker/API-shape evidence is written
"""
from __future__ import annotations

import hashlib
import json
import re
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

BASE = "https://kilowatt.ma/"
OUT = Path("reports/morocco/kilowatt/latest-public-map-probe.json")
UA = "Mozilla/5.0 (compatible; TCC-DataLab-PublicReadOnly/1.0)"
MAX_ASSETS = 40
MAX_BYTES = 6_000_000


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts: list[str] = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        d = dict(attrs)
        src = d.get("src")
        if src:
            self.scripts.append(src)


def get(url: str) -> tuple[int, str, bytes]:
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/javascript,application/json;q=0.9,*/*;q=0.8"})
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=25, context=ctx) as r:
        body = r.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            body = body[:MAX_BYTES]
        return int(getattr(r, "status", 200)), r.headers.get("Content-Type", ""), body


def clean_url(u: str) -> str:
    p = urlparse(u)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def safe_text(b: bytes) -> str:
    return b.decode("utf-8", "ignore")


def main() -> None:
    report: dict = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": BASE,
        "policy": {
            "read_only": True,
            "public_get_only": True,
            "no_login": True,
            "no_mutations": True,
            "raw_bodies_persisted": False,
            "query_strings_persisted": False,
        },
        "page": {},
        "assets": [],
        "summary": {},
        "candidate_public_data_paths": [],
        "external_hosts": [],
    }

    status, ctype, body = get(BASE)
    text = safe_text(body)
    report["page"] = {
        "status": status,
        "content_type": ctype,
        "bytes_sampled": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "mentions_91": bool(re.search(r"\b91\b", text)),
        "mentions_38": bool(re.search(r"\b38\b", text)),
        "keyword_hits": {k: len(re.findall(k, text, re.I)) for k in ["recharge", "location", "marker", "map", "kilowatt", "supabase", "geo_coordinates", "latitude", "longitude"]},
    }

    parser = ScriptParser()
    parser.feed(text)
    scripts = []
    for src in parser.scripts:
        u = urljoin(BASE, src)
        if u not in scripts:
            scripts.append(u)
    scripts = scripts[:MAX_ASSETS]

    path_candidates: set[str] = set()
    external_hosts: set[str] = set()
    host = urlparse(BASE).netloc
    url_re = re.compile(r"https?://[^\s\"'<>\\)]+", re.I)
    rel_re = re.compile(r"[\"']((?:/api/|/wp-json/|/graphql|/rest/v1/|/functions/v1/)[^\"']*)[\"']", re.I)
    key_re = re.compile(r"\b(chargers?|stations?|locations?|markers?|points?|lat(?:itude)?|lng|lon(?:gitude)?|power|connector|status|tariff|price|supabase)\b", re.I)

    for u in scripts:
        item = {"url": clean_url(u)}
        try:
            s, ct, b = get(u)
            t = safe_text(b)
            item.update({
                "status": s,
                "content_type": ct,
                "bytes_sampled": len(b),
                "sha256": hashlib.sha256(b).hexdigest(),
                "keyword_counts": {},
            })
            for k in ["charger", "station", "location", "marker", "latitude", "longitude", "supabase", "tariff", "status", "price"]:
                n = len(re.findall(k, t, re.I))
                if n:
                    item["keyword_counts"][k] = n
            for m in rel_re.finditer(t):
                path_candidates.add(m.group(1).split("?")[0])
            for raw in url_re.findall(t):
                cu = clean_url(raw.rstrip(".,;"))
                p = urlparse(cu)
                if p.netloc:
                    if p.netloc == host and key_re.search(p.path):
                        path_candidates.add(p.path)
                    elif p.netloc != host:
                        external_hosts.add(p.netloc.lower())
        except Exception as e:
            item["error_type"] = type(e).__name__
        report["assets"].append(item)

    # Only public route shapes / hosts; no query params, tokens, or raw values.
    report["candidate_public_data_paths"] = sorted(path_candidates)[:100]
    report["external_hosts"] = sorted(external_hosts)[:100]
    report["summary"] = {
        "script_asset_count": len(report["assets"]),
        "candidate_public_data_path_count": len(report["candidate_public_data_paths"]),
        "external_host_count": len(report["external_hosts"]),
        "map_data_route_identified": bool(report["candidate_public_data_paths"]),
        "note": "A candidate route is only a static public-client lead until validated by a separate GET-only probe.",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
