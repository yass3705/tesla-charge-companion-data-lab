#!/usr/bin/env python3
"""Scan APK/XAPK/APKS/ZIP artifacts for URL/hostname candidates.

Fail-closed helper for Italy CPO research. It does not infer tariffs; it only
extracts technical discovery strings that can guide later backend inspection.

Usage:
  python scripts/italy_android_endpoint_scan.py artifact.xapk --json out.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

URL_RE = re.compile(rb"https?://[^\x00-\x20\x22\x27<>\\]{4,500}", re.I)
HOST_RE = re.compile(rb"(?<![A-Za-z0-9_-])(?:[A-Za-z0-9-]{1,63}\.)+(?:com|it|eu|net|org|io|app|cloud|energy|services|systems|dev)(?![A-Za-z0-9_-])", re.I)
INTERESTING = re.compile(r"(?:api|backend|charge|charging|mobility|station|tariff|price|ocpi|roaming|enermia|eshore|gasgas|uattzy|hera)", re.I)


def clean_bytes(raw: bytes) -> str:
    return raw.decode("utf-8", "ignore").strip("\x00\r\n\t ,;)]}")


def inspect_blob(name: str, data: bytes, out: dict) -> None:
    urls = {clean_bytes(m.group(0)) for m in URL_RE.finditer(data)}
    hosts = {clean_bytes(m.group(0)).lower() for m in HOST_RE.finditer(data)}
    for u in urls:
        try:
            h = (urlparse(u).hostname or "").lower()
            if h:
                hosts.add(h)
        except Exception:
            pass
    if urls or hosts:
        out["filesWithCandidates"] += 1
    for u in urls:
        out["urls"].add(u)
    for h in hosts:
        out["hosts"].add(h)
    for s in list(urls) + list(hosts):
        if INTERESTING.search(s):
            out["interesting"].add(s)


def scan_archive(path: Path) -> dict:
    state = {
        "artifact": str(path),
        "membersScanned": 0,
        "filesWithCandidates": 0,
        "urls": set(),
        "hosts": set(),
        "interesting": set(),
        "errors": [],
    }
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # Avoid huge media/native payloads that rarely contain useful endpoints.
                if info.file_size > 80 * 1024 * 1024:
                    continue
                state["membersScanned"] += 1
                try:
                    inspect_blob(info.filename, zf.read(info), state)
                except Exception as exc:
                    state["errors"].append(f"{info.filename}: {exc}")
    except zipfile.BadZipFile:
        # APK is ZIP, but allow a plain extracted binary/text file as fallback.
        try:
            inspect_blob(path.name, path.read_bytes(), state)
            state["membersScanned"] = 1
        except Exception as exc:
            state["errors"].append(str(exc))
    return {
        **{k: v for k, v in state.items() if not isinstance(v, set)},
        "urls": sorted(state["urls"]),
        "hosts": sorted(state["hosts"]),
        "interesting": sorted(state["interesting"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("artifact", type=Path)
    ap.add_argument("--json", dest="json_path", type=Path)
    args = ap.parse_args()
    if not args.artifact.exists():
        print(f"artifact not found: {args.artifact}", file=sys.stderr)
        return 2
    result = scan_archive(args.artifact)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.json_path:
        args.json_path.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
