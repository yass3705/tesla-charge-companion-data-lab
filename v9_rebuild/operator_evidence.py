"""Bind the preserved public evidence collector output to its reviewed manifest."""
import hashlib
import json
import re
from datetime import datetime


def validate(output, manifest_path):
    manifest = json.loads(manifest_path.read_bytes())
    payload = json.loads(output.read_bytes())
    evidence = payload["sourceEvidence"]
    expected = [(s["key"], s["url"]) for s in manifest["sources"]]
    rows = evidence["sources"]
    observed = [(s["key"], s["url"]) for s in rows]
    facts = manifest["facts"]
    fingerprint = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True,
                                            separators=(",", ":")).encode()).hexdigest()
    if (not expected or len(set(expected)) != len(expected) or observed != expected
            or evidence["officialOnly"] is not True
            or evidence["relevantTariffFingerprintSha256"] != fingerprint
            or any(row["httpStatus"] != 200 or not re.fullmatch(r"[0-9a-f]{64}", row["rawSha256"]) for row in rows)
            or any(payload.get(k) != manifest[k] for k in ("dataset", "operator", "country"))
            or any(k not in payload or payload[k] != v for k, v in facts.items())
            or datetime.fromisoformat(payload["generatedAt"].replace("Z", "+00:00")).tzinfo is None):
        raise ValueError("Official evidence differs from the reviewed source manifest")
    return payload
