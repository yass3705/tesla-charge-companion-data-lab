#!/usr/bin/env python3
"""Targeted read-only discovery of NextCharge connector/tariff frontend symbols.

Fetches only the public map HTML and official static JS assets. It does not call
station, connector, tariff, charging, payment or reservation APIs. The goal is
to identify the UI function and path symbol used after station selection when a
user opens a connector/tariff detail.
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
    "getTariffs",
    "tariffEMP",
    "connectorsSummary",
    "idConnector",
    "idEvse",
    "connectorId",
    "tariff",
    "Tariff",
    "connector",
    "Connector",
)


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
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
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read(12_000_000)
    return raw.decode("utf-8", errors="replace")


def js_urls(text: str, base: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']", text, re.I):
        u = safe(base, m.group(1))
        if u and u not in out:
            out.append(u)
    return out


def snippets(text: str, needle: str, limit: int = 16) -> list[str]:
    out: list[str] = []
    pos = 0
    while len(out) < limit:
        pos = text.find(needle, pos)
        if pos < 0:
            break
        left = max(0, pos - 1800)
        right = min(len(text), pos + len(needle) + 2600)
        s = text[left:right]
        if s not in out:
            out.append(s)
        pos += len(needle)
    return out


def extract_candidates(text: str) -> dict[str, list[str]]:
    patterns = {
        "pathApiMembers": r"pathAPI\.([A-Za-z0-9_$]{1,80})",
        "hostApiSymbols": r"\b(hostAPI[A-Za-z0-9_$]{1,100})\b",
        "apiPathStrings": r"[\"']([A-Za-z0-9_./-]{1,120}(?:tariff|connector|evse|price)[A-Za-z0-9_./-]{0,120})[\"']",
        "functionNames": r"\b([A-Za-z_$][A-Za-z0-9_$]{0,80}(?:Tariff|tariff|Connector|connector|Evse|EVSE|Price|price)[A-Za-z0-9_$]{0,80})\s*\(",
    }
    out: dict[str, list[str]] = {}
    for name, pattern in patterns.items():
        vals: list[str] = []
        for m in re.finditer(pattern, text):
            v = m.group(1)
            if v not in vals:
                vals.append(v)
            if len(vals) >= 250:
                break
        if vals:
            out[name] = vals
    return out


def compact_context(text: str, needle: str, radius: int = 700) -> list[str]:
    vals: list[str] = []
    pos = 0
    while len(vals) < 8:
        pos = text.find(needle, pos)
        if pos < 0:
            break
        s = text[max(0, pos-radius): min(len(text), pos+len(needle)+radius)]
        s = re.sub(r"\s+", " ", s)
        if s not in vals:
            vals.append(s)
        pos += len(needle)
    return vals


def main() -> None:
    html = get(ROOT)
    parser = Parser()
    parser.feed(html)
    scripts: list[str] = []
    for raw in parser.scripts + js_urls(html, ROOT):
        u = safe(ROOT, raw)
        if u and u not in scripts:
            scripts.append(u)

    sources: list[dict[str, object]] = []
    for url, text in [(ROOT, html)] + [(u, get(u)) for u in scripts]:
        hit_counts = {n: text.count(n) for n in NEEDLES if text.count(n)}
        if not hit_counts:
            continue
        item: dict[str, object] = {
            "url": url,
            "bytes": len(text.encode("utf-8")),
            "hitCounts": hit_counts,
            "candidates": extract_candidates(text),
            "contexts": {n: snippets(text, n) for n in NEEDLES if n in text},
            "compactGetTariffs": compact_context(text, "getTariffs"),
            "compactTariffEMP": compact_context(text, "tariffEMP"),
        }
        sources.append(item)

    report = {
        "schemaVersion": 1,
        "policy": {
            "readOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "discoveredApiCallsExecuted": False,
            "chargingActionsAllowed": False,
            "paymentActionsAllowed": False,
            "reservationActionsAllowed": False,
        },
        "root": ROOT,
        "sources": sources,
    }
    out = Path("artifacts/go_electric_nextcharge_tariff_symbol_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = []
    for s in sources:
        c = s.get("candidates") or {}
        summary.append({
            "url": s["url"],
            "hitCounts": s["hitCounts"],
            "pathApiMembers": (c.get("pathApiMembers") or [])[:80],
            "hostApiSymbols": (c.get("hostApiSymbols") or [])[:80],
            "apiPathStrings": (c.get("apiPathStrings") or [])[:80],
            "functionNames": (c.get("functionNames") or [])[:120],
            "getTariffsContext": (s.get("compactGetTariffs") or [])[:3],
            "tariffEMPContext": (s.get("compactTariffEMP") or [])[:3],
        })
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
