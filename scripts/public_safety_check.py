#!/usr/bin/env python3
"""Block obvious secrets, credentials and raw app packages from the public Data Lab.

Credential placeholders used in source code (for example ``$TOKEN`` or
``${GH_TOKEN}``) are allowed. Static credential values are still blocked.
"""
import argparse
import re
from pathlib import Path

ALWAYS_PATTERNS = [
    (re.compile(rb"ghp_[A-Za-z0-9]{20,}"), "GitHub classic token"),
    (re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained token"),
    (re.compile(rb"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"), "private key"),
    (re.compile(rb"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "JWT-like token"),
    (re.compile(rb"sb_(?:publishable|anon)_[A-Za-z0-9_-]{12,}", re.I), "Supabase public client key"),
]

VALUE_PATTERNS = [
    (re.compile(rb"Authorization\s*:\s*Bearer\s+(?P<value>\S+)", re.I), "Authorization bearer header"),
    (re.compile(rb"Cookie\s*:\s*(?P<value>\S+)", re.I), "Cookie header"),
    (
        re.compile(
            rb"(?:client_secret|api_key|access_token|refresh_token)\s*[:=]\s*[\"'](?P<value>[^\"']{8,})[\"']",
            re.I,
        ),
        "embedded credential",
    ),
]

SKIP_PARTS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}
FORBIDDEN_SUFFIXES = {".apk", ".xapk", ".aab", ".ipa"}
PLACEHOLDER_WORDS = {
    "redacted",
    "[redacted]",
    "placeholder",
    "example",
    "dummy",
    "changeme",
    "token",
    "secret",
    "your_token",
    "your-token",
}


def iter_files(root):
    for path in Path(root).rglob("*"):
        if path.is_file() and not any(part in SKIP_PARTS for part in path.parts):
            yield path


def is_placeholder(value: bytes) -> bool:
    text = value.decode("utf-8", errors="ignore").strip().strip('"\'').lower()
    if not text:
        return True
    if any(ch in text for ch in ("$", "{", "}", "<", ">")):
        return True
    if text in PLACEHOLDER_WORDS:
        return True
    if text.startswith("***") or text.endswith("***"):
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    hits = []

    for path in iter_files(args.root):
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            hits.append((str(path), "raw mobile application package"))
            continue
        try:
            data = path.read_bytes()
        except Exception:
            continue

        for rx, label in ALWAYS_PATTERNS:
            if rx.search(data):
                hits.append((str(path), label))

        for rx, label in VALUE_PATTERNS:
            for match in rx.finditer(data):
                if not is_placeholder(match.group("value")):
                    hits.append((str(path), label))
                    break

    if hits:
        for path, label in hits:
            print(f"BLOCKED: {path}: {label}")
        raise SystemExit(2)

    print("Public safety scan: OK")


if __name__ == "__main__":
    main()
