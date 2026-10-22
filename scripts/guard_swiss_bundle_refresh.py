"""Validate technical integrity of a Swiss bundle and its source scope."""


def validate_refresh(previous, candidate):
    counts = candidate["counts"]
    evses = candidate["evses"]
    if len(evses) != counts["nationalEvseCount"]:
        raise ValueError("Swiss national EVSE inventory count is inconsistent")
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
    if any(not row.get("stationId") for row in evses):
        raise ValueError("Swiss national station inventory is incomplete")
    if not previous:
        return None
    if candidate.get("country") != previous.get("country") or candidate.get("nationalSource") != previous.get("nationalSource"):
        raise ValueError("Swiss coverage scope differs from last validated bundle")
    return None
