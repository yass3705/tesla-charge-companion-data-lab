"""Share the exact public OICP response between historical Swiss collectors."""
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import urllib.request

URL = "https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"


def validate(raw):
    payload = json.loads(raw)
    groups = payload.get("EVSEData")
    if not isinstance(groups, list) or any(not isinstance(g, dict) or not g.get("OperatorID")
            or not isinstance(g.get("EVSEDataRecord"), list) for g in groups):
        raise ValueError("Malformed Swiss OICP operator groups")


def open_national(request, timeout):
    path, sha = os.environ.get("TCC_CH_OICP_FILE"), os.environ.get("TCC_CH_OICP_SHA256")
    if request.full_url != URL:
        raise ValueError("Unexpected national input URL")
    if path is None and sha is None:
        return urllib.request.urlopen(request, timeout=timeout)
    if not path or not re.fullmatch(r"[a-f0-9]{64}", sha or "") or Path(path).is_symlink():
        raise ValueError("Incomplete Swiss input pin")
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("Swiss national input SHA mismatch")
    validate(raw)
    return io.BytesIO(raw)


def acquire(destination):
    destination.mkdir()  # A new acquisition cannot replace a prior snapshot.
    request = urllib.request.Request(URL, headers={"User-Agent": "Tesla-Charge-Companion/9", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 200:
            raise ValueError("Swiss national acquisition failed")
        raw = response.read()
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    validate(raw)
    sha = hashlib.sha256(raw).hexdigest()
    (destination / "national.json").write_bytes(raw)
    manifest = {"source": URL, "sha256": sha, "bytes": len(raw),
                "retrievedAt": datetime.now(timezone.utc).isoformat(), "runId": os.environ.get("GITHUB_RUN_ID")}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return sha


if __name__ == "__main__":
    print(acquire(Path(sys.argv[1])))
