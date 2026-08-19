#!/usr/bin/env python3
"""Block obvious secrets/credentials from the intentionally public Data Lab."""
import argparse
import re
from pathlib import Path

PATTERNS = [
    (re.compile(rb"ghp_[A-Za-z0-9]{20,}"), "GitHub classic token"),
    (re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained token"),
    (re.compile(rb"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"), "private key"),
    (re.compile(rb"Authorization\s*:\s*Bearer\s+\S+", re.I), "Authorization bearer header"),
    (re.compile(rb"Cookie\s*:\s*\S+", re.I), "Cookie header"),
    (re.compile(rb"(?:client_secret|api_key|access_token|refresh_token)\s*[:=]\s*[\"'][^\"']{8,}[\"']", re.I), "embedded credential"),
]
SKIP_PARTS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}


def iter_files(root):
    for path in Path(root).rglob("*"):
        if path.is_file() and not any(part in SKIP_PARTS for part in path.parts):
            yield path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    args = ap.parse_args()
    hits = []
    for path in iter_files(args.root):
        try:
            data = path.read_bytes()
        except Exception:
            continue
        for rx, label in PATTERNS:
            if rx.search(data):
                hits.append((str(path), label))
    if hits:
        for path, label in hits:
            print(f"BLOCKED: {path}: {label}")
        raise SystemExit(2)
    print("Public safety scan: OK")


if __name__ == "__main__":
    main()
