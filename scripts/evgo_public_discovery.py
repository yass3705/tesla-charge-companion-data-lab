#!/usr/bin/env python3
"""Focused, sanitized reconnaissance for the Moroccan EVGO Android client.

Public-repository rules:
- public Android package only
- read-only extraction
- no login, mutation, charging, payment, credential guessing or account data
- raw APK/XAPK, keys, JWTs, cookies and query strings are never persisted
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

PACKAGE = "ma.evgo.cp.app"
OUT = Path("artifacts/evgo-public-discovery")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

URL_RX = re.compile(r"https?://[^\s\x00\"'<>\\]{5,500}", re.I)
JWT_RX = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
LONG_RX = re.compile(r"\b[A-Za-z0-9_-]{48,}\b")
EMAIL_RX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

KEYWORDS = (
    "station", "charger", "connector", "evse", "location", "latitude", "longitude",
    "availability", "available", "occupied", "status", "power", "kw", "tariff", "price",
    "free", "session", "startcharging", "start_charging", "chargepoint", "ocpi", "ocpp",
    "api", "graphql", "firebase", "supabase", "websocket", "socket", "nareva", "evgo"
)

SENSITIVE = re.compile(
    r"(password|secret|token|authorization|cookie|email|phone|wallet|invoice|payment|card|account|customer|user_id|bearer)",
    re.I,
)


def download(dest: Path) -> tuple[str | None, int]:
    for fmt in ("XAPK", "APK"):
        url = f"https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=120) as res:
                data = res.read()
            if len(data) > 100_000:
                dest.write_bytes(data)
                return fmt, len(data)
        except Exception:
            pass
    return None, 0


def unzip(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as zf:
            for info in zf.infolist():
                if ".." in Path(info.filename).parts or info.file_size > 180 * 1024 * 1024:
                    continue
                zf.extract(info, dst)
    except Exception:
        pass


def extract_tree(pkg: Path, root: Path) -> None:
    unzip(pkg, root)
    for idx, apk in enumerate(list(root.rglob("*.apk"))[:30]):
        unzip(apk, root / f"apk_{idx}")


def strings(path: Path) -> list[str]:
    try:
        if path.name in {"libapp.so", "index.android.bundle", "main.jsbundle"}:
            p = subprocess.run(["strings", "-a", "-n", "3", str(path)], capture_output=True, text=True, errors="replace", timeout=240)
            return p.stdout.splitlines()
        return path.read_text(errors="replace").splitlines()
    except Exception:
        return []


def collect(root: Path) -> list[str]:
    out: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > 150 * 1024 * 1024:
            continue
        if p.name in {"libapp.so", "index.android.bundle", "main.jsbundle", "app.config"} or p.suffix.lower() in {".json", ".xml", ".txt", ".js"}:
            out.extend(strings(p))
    return out


def clean_url(value: str) -> str | None:
    value = JWT_RX.sub("[REDACTED]", value)
    value = EMAIL_RX.sub("[REDACTED]", value)
    value = LONG_RX.sub("[REDACTED]", value)
    try:
        u = urlsplit(value)
    except Exception:
        return None
    if u.scheme not in {"http", "https"} or not u.hostname:
        return None
    host = u.hostname.lower()
    # persist host/path only; never userinfo, query or fragment
    path = u.path or "/"
    if len(path) > 240:
        path = path[:240]
    return f"{u.scheme}://{host}{path}"


def endpoint_candidates(lines: list[str]) -> tuple[list[str], list[str]]:
    urls: list[str] = []
    hosts: list[str] = []
    for line in lines:
        if SENSITIVE.search(line) and not any(k in line.lower() for k in ("station", "charger", "connector", "location")):
            continue
        for raw in URL_RX.findall(line):
            cleaned = clean_url(raw.rstrip(".,;:)]}"))
            if not cleaned:
                continue
            low = cleaned.lower()
            if any(k in low for k in KEYWORDS):
                if cleaned not in urls:
                    urls.append(cleaned)
                h = urlsplit(cleaned).hostname
                if h and h not in hosts:
                    hosts.append(h)
    return hosts[:80], urls[:160]


def keyword_counts(lines: list[str]) -> dict[str, int]:
    joined = "\n".join(lines).lower()
    return {k: joined.count(k) for k in KEYWORDS if joined.count(k)}


def main() -> None:
    result = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "package": PACKAGE,
        "policy": {
            "read_only": True,
            "no_login": True,
            "no_mutations": True,
            "raw_package_persisted": False,
            "raw_credentials_persisted": False,
            "query_strings_persisted": False,
        },
    }
    with tempfile.TemporaryDirectory(prefix="evgo-public-") as tmp:
        root = Path(tmp)
        pkg = root / "evgo.pkg"
        fmt, size = download(pkg)
        result["download_format"] = fmt
        result["download_bytes"] = size
        result["download_ok"] = bool(fmt)
        if fmt:
            tree = root / "tree"
            extract_tree(pkg, tree)
            lines = collect(tree)
            hosts, urls = endpoint_candidates(lines)
            result["candidate_hosts"] = hosts
            result["candidate_urls"] = urls
            result["keyword_counts"] = keyword_counts(lines)
            result["client_technology_signals"] = {
                "flutter": any("package:flutter" in x for x in lines),
                "react_native": any("reactnative" in x.lower() or "index.android.bundle" in x for x in lines),
                "firebase": any("firebase" in x.lower() for x in lines),
                "supabase": any("supabase" in x.lower() for x in lines),
                "graphql": any("graphql" in x.lower() for x in lines),
                "websocket": any("websocket" in x.lower() for x in lines),
            }
    target = OUT / "summary.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"download_ok": result.get("download_ok"), "hosts": result.get("candidate_hosts", []), "tech": result.get("client_technology_signals", {})}, ensure_ascii=False))


if __name__ == "__main__":
    main()
