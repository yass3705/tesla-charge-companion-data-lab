#!/usr/bin/env python3
"""Focused read-only public reconnaissance for the Moroccan EVGO Android app.

Downloads the publicly distributed Android package into a temporary directory, mines only
non-sensitive backend/station signals, performs conservative GET probes against discovered
EVGO/Nareva-looking HTTP(S) endpoints, and persists only sanitized metadata. No login,
credentials, charging/payment calls, account data, cookies or raw packages are retained.
"""
from __future__ import annotations
import json, re, subprocess, tempfile, urllib.error, urllib.parse, urllib.request, zipfile
from pathlib import Path

PACKAGE = "ma.evgo.cp.app"
OUT = Path("artifacts/morocco-evgo-public")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.1)"
URL_RX = re.compile(r"https?://[^\s\x00\"'<>\\]{5,500}", re.I)
JWT_RX = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
TOKEN_RX = re.compile(r"\b[A-Za-z0-9_-]{48,}\b")
PATH_RX = re.compile(r"/(?:api|app|public|v1|v2|stations?|chargers?|connectors?)[A-Za-z0-9_./?=&{}$:-]{0,180}", re.I)
INTEREST = re.compile(r"(station|charger|connector|evse|tariff|price|rate|power|status|available|occupied|session|location|latitude|longitude|nareva|evgo)", re.I)


def redact(s: str) -> str:
    s = JWT_RX.sub("[REDACTED_JWT]", s)
    s = re.sub(r"(?i)(bearer\s+)[^\s,;\"']+", r"\1[REDACTED]", s)
    s = TOKEN_RX.sub("[REDACTED_LONG_TOKEN]", s)
    return s[:2000]


def get(url: str, maxbytes: int = 80000) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(maxbytes).decode("utf-8", "replace")
            return {"url": redact(url), "status": r.status, "content_type": r.headers.get("content-type", ""), "body_excerpt": redact(body[:4000])}
    except urllib.error.HTTPError as e:
        try: body = e.read(maxbytes).decode("utf-8", "replace")
        except Exception: body = ""
        return {"url": redact(url), "status": e.code, "body_excerpt": redact(body[:2000])}
    except Exception as e:
        return {"url": redact(url), "status": None, "error": f"{type(e).__name__}: {e}"}


def download(dest: Path):
    for fmt in ("XAPK", "APK"):
        url = f"https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=120) as r: data = r.read()
            if len(data) > 100000:
                dest.write_bytes(data)
                return fmt, len(data)
        except Exception:
            pass
    return None, 0


def unpack(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as z:
            for i in z.infolist():
                if ".." not in Path(i.filename).parts and i.file_size < 180 * 1024 * 1024:
                    z.extract(i, dst)
    except Exception:
        pass


def lines(path: Path):
    try:
        if path.name in {"libapp.so", "index.android.bundle", "main.jsbundle"}:
            p = subprocess.run(["strings", "-a", "-n", "3", str(path)], capture_output=True, text=True, errors="replace", timeout=180)
            return p.stdout.splitlines()
        return path.read_text(errors="replace").splitlines()
    except Exception:
        return []


def main():
    result = {"package": PACKAGE, "policy": {"read_only": True, "no_login": True, "raw_package_persisted": False, "raw_tokens_persisted": False}}
    with tempfile.TemporaryDirectory(prefix="evgo-public-") as td:
        root = Path(td); pkg = root / "evgo.pkg"
        fmt, size = download(pkg)
        result.update({"download_format": fmt, "download_bytes": size, "download_ok": bool(fmt)})
        if not fmt:
            (OUT / "summary.json").write_text(json.dumps(result, indent=2) + "\n"); return
        tree = root / "unpacked"; unpack(pkg, tree)
        for n, apk in enumerate(list(tree.rglob("*.apk"))[:25]): unpack(apk, tree / f"apk_{n}")
        all_lines = []
        for p in tree.rglob("*"):
            if not p.is_file(): continue
            try: sz = p.stat().st_size
            except OSError: continue
            if sz > 150 * 1024 * 1024: continue
            if p.name in {"libapp.so", "index.android.bundle", "main.jsbundle", "app.config"} or p.suffix.lower() in {".json", ".xml", ".txt", ".js"}:
                all_lines.extend(lines(p))
        urls, paths, contexts = [], [], []
        for i, line in enumerate(all_lines):
            for u in URL_RX.findall(line):
                u = u.rstrip(".,;:)]}")
                host = urllib.parse.urlsplit(u).netloc.lower()
                if any(k in (u + host).lower() for k in ("evgo", "nareva", "charge", "station", "ocpp")) and u not in urls:
                    urls.append(redact(u))
            for pth in PATH_RX.findall(line):
                if INTEREST.search(pth) and pth not in paths: paths.append(redact(pth))
            if INTEREST.search(line) and any(k in line.lower() for k in ("http", "api", "station", "connector", "tariff", "price", "status")) and len(contexts) < 120:
                contexts.append(redact(line.strip()))
        result["urls"] = urls[:120]
        result["candidate_paths"] = paths[:160]
        result["signal_lines"] = contexts
        # Only harmless GETs to discovered URLs; skip obvious auth/payment/session mutation routes.
        probes = []
        for u in urls[:40]:
            low = u.lower()
            if any(x in low for x in ("login", "auth", "payment", "wallet", "invoice", "start", "stop", "session", "register", "signup")): continue
            if not any(x in low for x in ("station", "charger", "connector", "location", "api", "evgo", "nareva")): continue
            probes.append(get(u))
            if len(probes) >= 12: break
        result["safe_get_probes"] = probes
    (OUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"download_ok": result.get("download_ok"), "url_count": len(result.get("urls", [])), "path_count": len(result.get("candidate_paths", [])), "probe_count": len(result.get("safe_get_probes", []))}))

if __name__ == "__main__": main()
