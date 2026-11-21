"""Bind renewed location identities and tariff content to an immutable job window."""
from datetime import datetime
import hashlib
import json

from v9_rebuild.electroverse import CACHE, MAPPING, read_json


def timestamp(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Electroverse renewal timestamp lacks timezone")
    return stamp


def job_window(state, started_at, completed_at):
    start, end = timestamp(started_at), timestamp(completed_at)
    if end < start:
        raise ValueError("Reversed renewal job window")
    mapped = [str(row["electroverseLocationPk"]) for row in read_json(state / MAPPING)["mappings"]]
    if len(set(mapped)) != len(mapped):
        raise ValueError("Duplicate mapped location")
    checked = read_json(state / CACHE / "checked-at.json")["checkedAt"]
    selected = {pk for pk in mapped if pk in checked and start <= timestamp(checked[pk]) <= end}
    rows = []
    for index in range(128):
        stations = read_json(state / CACHE / f"shard-{index:03d}.json")["stations"]
        for pk in selected.intersection(stations):
            row = stations[pk]
            if str(row["electroverseLocationPk"]) != pk or not isinstance(row.get("tariff"), dict):
                raise ValueError("Checked location missing tariff content")
            rows.append([pk, checked[pk], row["tariffHash"], row["tariff"]])
    if len(rows) != len(selected) or {row[0] for row in rows} != selected:
        raise ValueError("Checked identities and tariff shards differ")
    content = json.dumps(sorted(rows, key=lambda r: r[0]), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode()
    return selected, {
        "locations": len(selected),
        "mappingSHA256": hashlib.sha256((state / MAPPING).read_bytes()).hexdigest(),
        "rowsSHA256": hashlib.sha256(content).hexdigest(),
    }
