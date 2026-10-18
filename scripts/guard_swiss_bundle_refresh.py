"""Validate Swiss national coverage against the last accepted bundle."""


def validate_refresh(previous, candidate):
    counts = candidate["counts"]
    evses = candidate["evses"]
    if not evses or len(evses) != counts["nationalEvseCount"]:
        raise ValueError("Swiss national EVSE inventory is empty or inconsistent")
    ids = [row.get("evseId") for row in evses]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Swiss national EVSE inventory contains missing or duplicate identifiers")
    if sum(counts[key] for key in (
        "directTariffResolvedEvseCount",
        "noPublicDirectTariffEvseCount",
        "directTariffUnresolvedEvseCount",
    )) != len(evses):
        raise ValueError("Swiss tariff classifications do not cover every EVSE")
    stations = {row.get("stationId") for row in evses if row.get("stationId")}
    if len(stations) == 0 or any(not row.get("stationId") for row in evses):
        raise ValueError("Swiss national station inventory is empty or incomplete")
    if not previous:
        return None
    if candidate.get("country") != previous.get("country") or candidate.get("nationalSource") != previous.get("nationalSource"):
        raise ValueError("Swiss coverage scope differs from last validated bundle")
    old_evses = previous["evses"]
    old_stations = {row.get("stationId") for row in old_evses if row.get("stationId")}
    if not old_evses or not old_stations:
        raise ValueError("Previous Swiss coverage is invalid")
    if counts["directTariffResolvedEvseCount"] == 0 and previous["counts"]["directTariffResolvedEvseCount"] > 0:
        raise ValueError("Swiss direct tariffs disappeared; preserve last-good bundle")
    changes = {
        "stations": (old_stations, stations),
        "evses": ({row["evseId"] for row in old_evses}, set(ids)),
    }
    details = {}
    warning_needed = False
    for kind, (old, new) in changes.items():
        decrease = max(0, len(old) - len(new)) / len(old) * 100
        if decrease > 30:
            raise ValueError(f"Swiss {kind} coverage fell {decrease:.2f}%; preserve last-good bundle")
        if decrease > 5:
            warning_needed = True
        details[kind] = {
            "previous": len(old), "current": len(new), "decreasePercent": decrease,
            "disappearedIds": sorted(old - new),
        }
    return {"snapshotDate": candidate.get("generatedAt"), "source": candidate.get("nationalSource"), **details} if warning_needed else None
