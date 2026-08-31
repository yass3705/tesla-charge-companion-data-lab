#!/usr/bin/env python3
"""Read-only symbol resolver for the public NextCharge web frontend.

Fetches only the public NextCharge page and its official static JavaScript bundle,
then extracts nearby source text for configuration symbols used by the station-grid
request. It never calls the discovered charging/station APIs.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = "https://nextcharge.app/map?nextcharge=only"
ALLOWED = {"nextcharge.app", "www.nextcharge.app", "nextchargeapp-542e.kxcdn.com"}
USER_AGENT = "TeslaChargeCompanion-DataLab/1.0 (+read-only public research)"
NEEDLES = (
    "hostEndpoints",
    "pathAPI",
    "hostAPIstationsGrid",
    "stationsGrid",
    "getSessionTokenForStations",
    "tokenAppSessionForStations",
    "appVersion",
    "osType",
    "owner",
)


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        src = dict(attrs).get("src")
        if src:
            self.scripts.append(src)


def safe(base: str, value: str) -> str | None:
    url = urllib.parse.urljoin(base, value)
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or p.hostname not in ALLOWED:
        return None
    return url


def get(url: str) -> str:
    checked = safe(url, url)
    if not checked:
        raise RuntimeError(f"disallowed host: {url}")
    req = urllib.request.Request(checked, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read(10_000_000)
    return raw.decode("utf-8", errors="replace")


def js_urls(text: str, base: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']", text, re.I):
        u = safe(base, m.group(1))
        if u and u not in out:
            out.append(u)
    return out


def contexts(text: str, needle: str) -> list[str]:
    out: list[str] = []
    pos = 0
    while len(out) < 30:
        pos = text.find(needle, pos)
        if pos < 0:
            break
        left = max(0, pos - 2200)
        right = min(len(text), pos + len(needle) + 3200)
        snippet = text[left:right]
        if snippet not in out:
            out.append(snippet)
        pos += len(needle)
    return out


def literal_candidates(text: str) -> dict[str, list[str]]:
    patterns = {
        "hostEndpointsAssignments": r"hostEndpoints\s*=\s*([^;]{1,6000})",
        "pathAPIAssignments": r"pathAPI\s*=\s*([^;]{1,6000})",
        "hostAPIstationsGridAssignments": r"hostAPIstationsGrid\s*[:=]\s*([^,;}]{1,1000})",
        "stationsGridAssignments": r"stationsGrid\s*[:=]\s*([^,;}]{1,1000})",
        "sessionTokenFunctionAssignments": r"getSessionTokenForStations\s*=\s*([^;]{1,5000})",
        "absoluteApiHosts": r"https://[A-Za-z0-9._:-]+(?:/[A-Za-z0-9_./?=&%:+,{}$@~-]*)?",
    }
    result: dict[str, list[str]] = {}
    for name, pattern in patterns.items():
        vals: list[str] = []
        for m in re.finditer(pattern, text, re.I):
            v = m.group(1) if m.lastindex else m.group(0)
            if name == "absoluteApiHosts" and not any(k in v.lower() for k in ("api", "nextcharge", "goelectric")):
                continue
            v = v[:7000]
            if v not in vals:
                vals.append(v)
            if len(vals) >= 100:
                break
        if vals:
            result[name] = vals
    return result


def main() -> None:
    html = get(ROOT)
    parser = Parser()
    parser.feed(html)
    scripts: list[str] = []
    for raw in parser.scripts + js_urls(html, ROOT):
        u = safe(ROOT, raw)
        if u and u not in scripts:
            scripts.append(u)

    report: dict[str, object] = {
        "schemaVersion": 1,
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "discoveredApiCallsExecuted": False,
        },
        "root": ROOT,
        "sources": [],
    }

    sources: list[dict[str, object]] = []
    for url, text in [(ROOT, html)] + [(u, get(u)) for u in scripts]:
        item: dict[str, object] = {"url": url, "bytes": len(text.encode("utf-8"))}
        ctx = {needle: contexts(text, needle) for needle in NEEDLES}
        item["contexts"] = {k: v for k, v in ctx.items() if v}
        item["literalCandidates"] = literal_candidates(text)
        sources.append(item)
    report["sources"] = sources

    out = Path("artifacts/go_electric_nextcharge_symbol_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = []
    for item in sources:
        summary.append({
            "url": item["url"],
            "symbols": sorted((item["contexts"] or {}).keys()),
            "literalGroups": sorted((item["literalCandidates"] or {}).keys()),
        })
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
