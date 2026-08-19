#!/usr/bin/env python3
"""Sanitized, read-only Morocco EV charging reconnaissance.

This script is designed for an intentionally public repository.
It downloads publicly distributed Android packages into a temporary directory,
extracts only charging-infrastructure signals, and never persists APK/XAPK files,
raw client keys, JWTs, cookies, credentials, account data, or payment data.

Network requests are limited to explicit read-only station/configuration endpoints.
No login, credential guessing, charging/payment operation, or mutation is performed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

OUT = Path("artifacts/morocco-public-probe")
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.0)"

APPS = {
    "fastvolt": "ma.fastgo",
    "kilowatt": "ma.kilowatt.app",
    "evone": "ma.evplug",
    "total_club_ev": "com.namp.totalev",
    "shell_vivo": "com.shell.shell_loyalty_app.morocco",
    "evgo": "ma.evgo.cp.app",
}

JWT_RX = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
SB_RX = re.compile(r"sb_(?:publishable|anon)_[A-Za-z0-9_-]{12,}", re.I)
URL_RX = re.compile(r"https?://[^\s\x00\"'<>\\]{5,500}", re.I)
PATH_RX = re.compile(r"/(?:api|app|user)/(?:[A-Za-z0-9_.?=&{}$:-]+/?){1,8}", re.I)
EMAIL_RX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
LONG_TOKEN_RX = re.compile(r"\b[A-Za-z0-9_-]{48,}\b")

INTERESTING_FIELDS = {
    "station", "stations", "charging_station", "charging_stations", "station_id",
    "charger", "chargers", "charger_id", "charger_name", "connector", "connectors",
    "connector_id", "connector_type", "evse", "evse_id", "location", "locations",
    "latitude", "longitude", "lat", "lng", "address", "city", "status", "availability",
    "available", "power", "power_kw", "max_power", "rate", "price", "tariff", "tariffs",
    "currency", "idle_price", "fixed_starting_fee", "session_fee", "time_fee", "energy_fee",
    "free", "operator", "cpo", "network", "tenant", "organisation", "organization",
}
SENSITIVE_FIELDS = re.compile(
    r"(password|secret|token|authorization|cookie|email|phone|mobile|wallet|invoice|payment|card|account|user_id|customer)",
    re.I,
)


def request(url: str, headers: dict[str, str] | None = None, maxbytes: int = 120_000) -> dict:
    h = {"User-Agent": UA, "Accept": "application/json,text/plain,*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            body = res.read(maxbytes).decode("utf-8", "replace")
            return {"url": url, "status": res.status, "content_type": res.headers.get("content-type", ""), "body": body}
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(maxbytes).decode("utf-8", "replace")
        except Exception:
            body = ""
        return {"url": url, "status": exc.code, "content_type": exc.headers.get("content-type", "") if exc.headers else "", "body": body}
    except Exception as exc:
        return {"url": url, "status": None, "error": f"{type(exc).__name__}: {exc}"}


def redact_text(text: str) -> str:
    text = JWT_RX.sub("[REDACTED_JWT]", text)
    text = SB_RX.sub("[REDACTED_PUBLIC_CLIENT_KEY]", text)
    text = EMAIL_RX.sub("[REDACTED_EMAIL]", text)
    text = re.sub(r"(?i)(bearer\s+)[^\s,;\"']+", r"\1[REDACTED]", text)
    text = LONG_TOKEN_RX.sub("[REDACTED_LONG_TOKEN]", text)
    return text[:4000]


def public_json_shape(value, depth: int = 0):
    """Keep only charging-infrastructure fields from successful JSON responses."""
    if depth > 5:
        return None
    if isinstance(value, list):
        return [public_json_shape(x, depth + 1) for x in value[:8]]
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            k = str(key)
            kl = k.lower()
            if SENSITIVE_FIELDS.search(kl):
                continue
            if kl in INTERESTING_FIELDS or any(part in kl for part in ("station", "charger", "connector", "evse", "tariff", "price", "rate", "power", "status", "availab", "location", "address", "operator", "network")):
                out[k] = public_json_shape(item, depth + 1)
            elif isinstance(item, (dict, list)):
                nested = public_json_shape(item, depth + 1)
                if nested not in (None, {}, []):
                    out[k] = nested
        return out
    if isinstance(value, str):
        return redact_text(value)[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:200]


def safe_response(res: dict) -> dict:
    out = {k: v for k, v in res.items() if k != "body"}
    body = res.get("body", "")
    if not body:
        return out
    try:
        obj = json.loads(body)
    except Exception:
        out["body_excerpt"] = redact_text(body)
        return out
    if res.get("status") == 200:
        out["public_json"] = public_json_shape(obj)
        if isinstance(obj, list):
            out["row_count_sampled"] = min(len(obj), 8)
        elif isinstance(obj, dict):
            out["top_level_keys"] = [k for k in obj.keys() if not SENSITIVE_FIELDS.search(str(k))][:50]
    else:
        out["body_excerpt"] = redact_text(body)
    return out


def download_package(package: str, dest: Path) -> tuple[str | None, int]:
    for fmt in ("XAPK", "APK"):
        url = f"https://d.apkpure.com/b/{fmt}/{package}?version=latest"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=120) as res:
                data = res.read()
            if len(data) > 100_000:
                dest.write_bytes(data)
                return fmt, len(data)
        except Exception:
            continue
    return None, 0


def unpack_zip(source: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                if ".." in Path(info.filename).parts or info.file_size > 180 * 1024 * 1024:
                    continue
                archive.extract(info, dest)
    except Exception:
        return


def extract_tree(package_file: Path, root: Path) -> None:
    unpack_zip(package_file, root)
    for idx, apk in enumerate(list(root.rglob("*.apk"))[:30]):
        unpack_zip(apk, root / f"apk_{idx}")


def file_lines(path: Path) -> list[str]:
    try:
        if path.name in {"libapp.so", "index.android.bundle", "main.jsbundle"}:
            proc = subprocess.run(
                ["strings", "-a", "-n", "3", str(path)],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=240,
            )
            return proc.stdout.splitlines()
        return path.read_text(errors="replace").splitlines()
    except Exception:
        return []


def collect_lines(root: Path) -> list[str]:
    lines: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > 150 * 1024 * 1024:
            continue
        if path.name in {"libapp.so", "index.android.bundle", "main.jsbundle", "app.config"} or path.suffix.lower() in {".json", ".txt", ".js", ".xml"}:
            lines.extend(file_lines(path))
    return lines


def non_sensitive_signals(lines: list[str]) -> dict:
    joined = "\n".join(lines)
    urls = []
    for line in lines:
        for url in URL_RX.findall(line):
            url = url.rstrip(".,;:)]}")
            if any(x in url.lower() for x in ("fastvolt", "bornerecharge", "supabase", "numocity", "kilowatt", "total", "shell", "vivo", "evgo")) and url not in urls:
                urls.append(redact_text(url))
    paths = []
    for path in PATH_RX.findall(joined):
        if re.search(r"(station|charger|connector|status|location|tariff|price)", path, re.I) and path not in paths:
            paths.append(path)
    fields = sorted({field for field in INTERESTING_FIELDS if re.search(rf"(?i)(?:^|[^A-Za-z0-9_]){re.escape(field)}(?:$|[^A-Za-z0-9_])", joined)})
    jwt_candidates = JWT_RX.findall(joined)
    sb_candidates = SB_RX.findall(joined)
    return {
        "urls": urls[:100],
        "candidate_paths": paths[:120],
        "charging_fields": fields,
        "embedded_client_material": {
            "jwt_count": len(jwt_candidates),
            "supabase_key_count": len(sb_candidates),
            "raw_values_persisted": False,
        },
        "_runtime_jwts": jwt_candidates,
        "_runtime_sb_keys": sb_candidates,
    }


def inspect_app(name: str, package: str, temp_root: Path) -> dict:
    pkg_file = temp_root / f"{name}.pkg"
    fmt, size = download_package(package, pkg_file)
    rec = {"package": package, "download_format": fmt, "download_bytes": size}
    if not fmt:
        rec["download_ok"] = False
        return rec
    rec["download_ok"] = True
    unpacked = temp_root / f"{name}-unpacked"
    extract_tree(pkg_file, unpacked)
    lines = collect_lines(unpacked)
    sig = non_sensitive_signals(lines)
    runtime_jwts = sig.pop("_runtime_jwts", [])
    runtime_sb_keys = sig.pop("_runtime_sb_keys", [])
    rec.update(sig)

    if name == "fastvolt":
        rec["anonymous_read_probes"] = [
            safe_response(request("https://mobile.ev.fastvolt.ma/app/charging_stations/")),
            safe_response(request("https://mobile.ev.fastvolt.ma/user/get_charging_station_details/")),
        ]
    elif name == "evone":
        rec["anonymous_read_probes"] = [
            safe_response(request("https://mobile.evplugv2.bornerecharge.ma/app/charging_stations/")),
            safe_response(request("https://mobile.evplugv2.bornerecharge.ma/user/get_charging_station_details/")),
        ]
    elif name == "kilowatt":
        host = "https://jmrgknphxsviooizyilj.supabase.co"
        candidates = []
        for key in runtime_sb_keys + runtime_jwts:
            if key not in candidates:
                candidates.append(key)
        rec["supabase_project"] = host
        rec["supabase_public_key_present"] = bool(candidates)
        rec["supabase_probe"] = None
        for key in candidates[:8]:
            # Public client material is used transiently and never written to disk or stdout.
            headers = {"apikey": key, "Authorization": "Bearer " + key}
            result = request(host + "/rest/v1/", headers=headers, maxbytes=180_000)
            safe = safe_response(result)
            safe["client_key_fingerprint"] = hashlib.sha256(key.encode()).hexdigest()[:12]
            rec["supabase_probe"] = safe
            if result.get("status") == 200:
                break
    elif name == "total_club_ev":
        base = "https://csmstotalenergiesma.numocity.com"
        rec["numocity_read_probes"] = [
            safe_response(request(base + "/api/qr-connector-list")),
            safe_response(request(base + "/api/get-connector-status")),
        ]
    return rec


def main() -> None:
    result = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy": {
            "read_only": True,
            "no_login": True,
            "no_mutations": True,
            "raw_android_packages_persisted": False,
            "raw_client_keys_persisted": False,
            "successful_json_is_field_whitelisted": True,
        },
        "apps": {},
    }
    with tempfile.TemporaryDirectory(prefix="tcc-morocco-public-") as tmp:
        root = Path(tmp)
        for name, package in APPS.items():
            result["apps"][name] = inspect_app(name, package, root)
    target = OUT / "summary.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({name: {"download_ok": rec.get("download_ok"), "package": rec.get("package")} for name, rec in result["apps"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
