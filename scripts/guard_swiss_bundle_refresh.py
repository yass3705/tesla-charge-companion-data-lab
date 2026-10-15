"""Preserve the last validated Swiss bundle when an upstream refresh regresses."""


def validate_refresh(previous, candidate):
    counts = candidate["counts"]
    evses = candidate["evses"]
    if not evses or len(evses) != counts["nationalEvseCount"]:
        raise ValueError("Swiss national EVSE inventory is empty or inconsistent")
    if len({row["evseId"] for row in evses}) != len(evses):
        raise ValueError("Swiss national EVSE inventory contains duplicate identifiers")
    if sum(counts[key] for key in (
        "directTariffResolvedEvseCount",
        "noPublicDirectTariffEvseCount",
        "directTariffUnresolvedEvseCount",
    )) != len(evses):
        raise ValueError("Swiss tariff classifications do not cover every EVSE")
    if previous:
        old = previous["counts"]
        if counts["nationalEvseCount"] < old["nationalEvseCount"]:
            raise ValueError("Swiss national EVSE count fell; review before replacing last-good bundle")
        if counts["directTariffResolvedEvseCount"] == 0 and old["directTariffResolvedEvseCount"] > 0:
            raise ValueError("Swiss direct tariffs disappeared; preserve last-good bundle")
